# app/api/endpoints/applications.py

import random
import string
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select
from uuid import UUID
from typing import Any


from app.api.deps import get_db_session, get_application_or_404
from app.core.rbac import AllowRoles
from app.models.user import User, UserRole
from app.models.department import Department

# Models & Schemas
from app.models.student import Student 
from app.models.application import Application, ApplicationStatus
from app.models.application_stage import ApplicationStage 

from app.core.storage import get_signed_url
from app.schemas.application import ApplicationCreate, ApplicationRead, ApplicationResubmit
from app.services.application_service import create_application_for_student
from app.services.email_service import send_application_created_email
from app.services.pdf_service import generate_certificate_pdf

router = APIRouter(
    prefix="/api/applications",
    tags=["Applications"]
)

# ------------------------------------------------------------
# HELPER: Generate Readable ID
# ------------------------------------------------------------
def generate_display_id(roll_number: str) -> str:
    """
    Generates a clean ID: ND235ICS066A7
    Format: ND + ROLL + 2_CHAR_SUFFIX
    """
    clean_roll = roll_number.strip().upper().replace(" ", "").replace("-", "")
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=2))
    return f"ND{clean_roll}{suffix}"


# ------------------------------------------------------------
# CREATE APPLICATION
# ------------------------------------------------------------
@router.post("/create", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(AllowRoles(UserRole.Student)),
    session: AsyncSession = Depends(get_db_session),
):
    if not current_user.student_id:
        raise HTTPException(status_code=400, detail="No student profile linked to user")

    student_id = current_user.student_id

    # 1. Update Student Profile
    student_res = await session.execute(select(Student).where(Student.id == student_id))
    student = student_res.scalar_one()

    student.father_name = payload.father_name
    student.mother_name = payload.mother_name
    student.gender = payload.gender
    student.category = payload.category
    student.dob = payload.dob
    student.permanent_address = payload.permanent_address
    student.domicile = payload.domicile
    student.is_hosteller = payload.is_hosteller
    student.hostel_name = payload.hostel_name
    student.hostel_room = payload.hostel_room
    student.batch = payload.batch
    student.section = payload.section
    student.admission_year = payload.admission_year
    student.admission_type = payload.admission_type
    
    session.add(student)

    # 2. Generate Unique Display ID
    new_display_id = generate_display_id(student.roll_number)
    while True:
        existing = await session.execute(
            select(Application).where(Application.display_id == new_display_id)
        )
        if not existing.scalar_one_or_none():
            break
        new_display_id = generate_display_id(student.roll_number)

    # 3. Create Application
    try:
        new_app = await create_application_for_student(
            session=session,
            student_id=student_id,
            payload=payload 
        )

        # 4. Link Details
        new_app.proof_document_url = payload.proof_document_url
        new_app.display_id = new_display_id 
        
        session.add(new_app)
        await session.commit()
        await session.refresh(new_app)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"CRITICAL ERROR creating application: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # 5. Send Email
    if current_user.email:
        email_data = {
            "name": current_user.name,
            "email": current_user.email,
            "application_id": str(new_app.id),
            "display_id": new_display_id 
        }
        background_tasks.add_task(send_application_created_email, email_data)

    return ApplicationRead.model_validate(new_app)


# ------------------------------------------------------------
# GET MY APPLICATION
# ------------------------------------------------------------
@router.get("/my", status_code=200)
async def get_my_application(
    current_user: User = Depends(AllowRoles(UserRole.Student)),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    
    if not current_user.student_id:
        raise HTTPException(status_code=400, detail="No student linked to account")

    result = await session.execute(
        select(Application)
        .where(Application.student_id == current_user.student_id)
        .order_by(Application.created_at.desc())
        .options(
            selectinload(Application.student).selectinload(Student.school),
        )
    )
    app = result.scalars().first()

    if not app:
        return {"application": None, "message": "No application found."}

    # Fetch Stages
    stage_result = await session.execute(
        select(ApplicationStage)
        .where(ApplicationStage.application_id == app.id)
        .order_by(ApplicationStage.sequence_order.asc())
    )
    stages = stage_result.scalars().all()

    # Calculate Flags
    is_rejected = any(s.status == str(ApplicationStatus.REJECTED.value) for s in stages)
    rejected_stage = next((s for s in stages if s.status == str(ApplicationStatus.REJECTED.value)), None)
    is_completed = str(app.status) == str(ApplicationStatus.COMPLETED.value)

    signed_proof_link = None
    if app.proof_document_url:
        signed_proof_link = get_signed_url(app.proof_document_url)

    return {
        "student": {
            "full_name": app.student.full_name,
            "enrollment_number": app.student.enrollment_number,
            "roll_number": app.student.roll_number,
            "email": app.student.email,
            "mobile_number": app.student.mobile_number,
            "school_name": app.student.school.name if app.student.school else "N/A",
            "batch": app.student.batch,
            "father_name": app.student.father_name,
            "hostel_name": app.student.hostel_name,
        },
        "application": {
            "id": app.id,
            "display_id": app.display_id, 
            "status": app.status,
            "current_stage_order": app.current_stage_order,
            "remarks": app.remarks,
            "proof_document_url": signed_proof_link, 
            "proof_path": app.proof_document_url,
            "created_at": app.created_at,
            "updated_at": app.updated_at,
        },
        "stages": [
            {
                "id": s.id,
                "verifier_role": s.verifier_role,
                "status": s.status,
                "sequence_order": s.sequence_order,
                "department_id": s.department_id,
                "comments": s.comments, 
                "verified_by": s.verified_by,
                "verified_at": s.verified_at,
            }
            for s in stages
        ],
        "flags": {
            "is_rejected": is_rejected,
            "is_completed": is_completed,
            "is_in_progress": (str(app.status) == str(ApplicationStatus.IN_PROGRESS.value)),
        },
        "rejection_details": {
            "role": rejected_stage.verifier_role if rejected_stage else None,
            "remarks": rejected_stage.comments if rejected_stage else None
        } if is_rejected else None
    }

# ------------------------------------------------------------
# GET APPLICATION STATUS
# ------------------------------------------------------------
@router.get("/status", status_code=200)
async def get_application_status(
    current_user: User = Depends(AllowRoles(UserRole.Student)),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    
    if not current_user.student_id:
        raise HTTPException(status_code=400, detail="No student linked to account")

    result = await session.execute(
        select(Application)
        .where(Application.student_id == current_user.student_id)
        .order_by(Application.created_at.desc())
    )
    app = result.scalars().first()

    if not app:
        return {"application": None, "message": "No application found."}

    stage_result = await session.execute(
        select(ApplicationStage, Department.name)
        .outerjoin(Department, ApplicationStage.department_id == Department.id)
        .where(ApplicationStage.application_id == app.id)
        .order_by(ApplicationStage.sequence_order.asc())
    )
    results = stage_result.all() 
    
    stages_data = []
    current_order = app.current_stage_order
    
    active_pending_names = []
    active_approved_names = []
    active_rejected_names = []
    rejected_stage = None

    for stage, dept_name in results:
        display_name = dept_name if dept_name else stage.verifier_role.replace("_", " ").title()
        if stage.verifier_role == "dean": display_name = "School Dean"

        stages_data.append({
            "id": stage.id,
            "verifier_role": stage.verifier_role,
            "display_name": display_name,
            "status": stage.status,
            "sequence_order": stage.sequence_order,
            "comments": stage.comments,
        })

        if str(stage.status) == str(ApplicationStatus.REJECTED.value):
            rejected_stage = stage
            active_rejected_names.append(display_name)

        if stage.sequence_order == current_order:
            if str(stage.status) == str(ApplicationStatus.PENDING.value):
                active_pending_names.append(display_name)
            elif str(stage.status) == str(ApplicationStatus.APPROVED.value):
                active_approved_names.append(display_name)

    location_str = "Processing..." 
    if str(app.status) == str(ApplicationStatus.REJECTED.value):
        location_str = f"Rejected at: {', '.join(active_rejected_names)}"
    elif str(app.status) == str(ApplicationStatus.COMPLETED.value):
        location_str = "Certificate Ready for Download"
    else:
        parts = []
        if active_pending_names: parts.append(f"Pending at: {', '.join(active_pending_names)}")
        if active_approved_names: parts.append(f"Approved by: {', '.join(active_approved_names)}")
        if parts: location_str = " | ".join(parts)

    return {
        "application": {
            "id": app.id,
            "display_id": app.display_id, 
            "status": app.status,
            "current_stage_order": app.current_stage_order,
            "created_at": app.created_at,
            "updated_at": app.updated_at,
            "current_location": location_str 
        },
        "stages": stages_data,
        "flags": {
            "is_rejected": (str(app.status) == str(ApplicationStatus.REJECTED.value)),
            "is_completed": (str(app.status) == str(ApplicationStatus.COMPLETED.value)),
            "is_in_progress": (str(app.status) == str(ApplicationStatus.IN_PROGRESS.value)),
        },
        "rejection_details": {
            "role": rejected_stage.verifier_role if rejected_stage else None,
            "remarks": rejected_stage.comments if rejected_stage else None
        } if rejected_stage else None
    }
    
# ------------------------------------------------------------
# DOWNLOAD CERTIFICATE
# ------------------------------------------------------------
@router.get("/{application_id}/certificate", response_class=Response)
async def download_certificate(
    # Uses dependency to find App by UUID *OR* Display ID
    app: Application = Depends(get_application_or_404),
    current_user: User = Depends(AllowRoles(UserRole.Student, UserRole.Admin)),
    session: AsyncSession = Depends(get_db_session),
):
    # Validate User Access
    if current_user.role == UserRole.Student:
        if not current_user.student_id:
             raise HTTPException(status_code=403, detail="Student profile missing")
             
        # FIX: Verify using the resolved 'app' object directly
        if str(app.student_id) != str(current_user.student_id):
            raise HTTPException(status_code=403, detail="Not authorized")

    try:
        # Generate PDF
        pdf_bytes = await generate_certificate_pdf(session, app.id)
        
        # Use display_id in filename if available
        filename = f"No_Dues_{app.display_id or app.id}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Certificate Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ------------------------------------------------------------
# RESUBMIT APPLICATION
# ------------------------------------------------------------
@router.patch("/{application_id}/resubmit", response_model=ApplicationRead)
async def resubmit_application(
    # FIX: Resolves ND... or UUID automatically
    app: Application = Depends(get_application_or_404),
    payload: ApplicationResubmit = None, # Make payload optional in signature if needed, or required
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(AllowRoles(UserRole.Student)),
):
    if not payload:
        raise HTTPException(400, "Payload required")

    # 1. Authorization
    if app.student_id != current_user.student_id:
        raise HTTPException(403, "Not authorized to resubmit this application")

    # 2. Validation
    is_globally_rejected = str(app.status) == str(ApplicationStatus.REJECTED.value)
    
    stage_query = select(ApplicationStage).where(
        ApplicationStage.application_id == app.id,
        ApplicationStage.sequence_order == app.current_stage_order,
        ApplicationStage.status == "rejected"
    )
    stage_res = await session.execute(stage_query)
    blocked_stage = stage_res.scalar_one_or_none()

    if not is_globally_rejected and not blocked_stage:
        raise HTTPException(400, "No rejection found. Application is processing.")

    # 3. Update Student Profile
    student = await session.get(Student, app.student_id)
    if payload.father_name is not None: student.father_name = payload.father_name
    if payload.mother_name is not None: student.mother_name = payload.mother_name
    if payload.gender is not None: student.gender = payload.gender
    if payload.category is not None: student.category = payload.category
    if payload.dob is not None: student.dob = payload.dob
    if payload.permanent_address is not None: student.permanent_address = payload.permanent_address
    if payload.domicile is not None: student.domicile = payload.domicile
    if payload.is_hosteller is not None: student.is_hosteller = payload.is_hosteller
    if payload.hostel_name is not None: student.hostel_name = payload.hostel_name
    if payload.hostel_room is not None: student.hostel_room = payload.hostel_room
    if payload.batch is not None: student.batch = payload.batch
    if payload.section is not None: student.section = payload.section
    if payload.admission_year is not None: student.admission_year = payload.admission_year
    if payload.admission_type is not None: student.admission_type = payload.admission_type
    
    session.add(student)

    # 4. Reset Rejected Stage
    if blocked_stage:
        blocked_stage.status = "pending"
        blocked_stage.verified_by = None 
        blocked_stage.verified_at = None
        new_note = payload.remarks or "Resubmitted with corrections"
        blocked_stage.comments = f"Resubmission: {new_note}"
        session.add(blocked_stage)

    # 5. Update Application
    app.status = ApplicationStatus.IN_PROGRESS
    if payload.proof_document_url:
        app.proof_document_url = payload.proof_document_url

    session.add(app)
    await session.commit()
    await session.refresh(app)

    return app