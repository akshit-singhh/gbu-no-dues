# app/api/endpoints/applications.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select
from uuid import UUID
from typing import Any

from app.api.deps import get_db_session
from app.core.rbac import AllowRoles
from app.models.user import User, UserRole

# ----------------------------------------------------------------
# MODEL & SCHEMA IMPORTS
# ----------------------------------------------------------------
from app.models.student import Student 
from app.models.application import Application, ApplicationStatus
from app.models.application_stage import ApplicationStage 

from app.core.storage import get_signed_url
from app.schemas.application import ApplicationCreate, ApplicationRead
from app.services.application_service import create_application_for_student
from app.services.email_service import send_application_created_email
from app.services.pdf_service import generate_certificate_pdf

router = APIRouter(
    prefix="/api/applications",
    tags=["Applications"]
)


# ------------------------------------------------------------
# CREATE APPLICATION (Step 2: Submit Details + Proof Path)
# ------------------------------------------------------------
@router.post("/create", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,  # Receives JSON Payload (Path + Student Details)
    background_tasks: BackgroundTasks,
    current_user: User = Depends(AllowRoles(UserRole.Student)),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Creates a new application.
    - Updates the Student Profile with details.
    - Saves the Application with the internal file path (proof_document_url).
    """
    if not current_user.student_id:
        raise HTTPException(status_code=400, detail="No student profile linked to user")

    # ✅ FIX: Use UUID object directly (do not cast to str)
    student_id = current_user.student_id

    # 1. FETCH & UPDATE STUDENT PROFILE
    student_res = await session.execute(select(Student).where(Student.id == student_id))
    student = student_res.scalar_one()

    # Update profile fields
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

    # 2. CREATE APPLICATION (Service handles duplicates logic)
    try:
        new_app = await create_application_for_student(
            session=session,
            # ✅ FIX: Pass UUID object (service likely expects UUID or handles it)
            student_id=student_id,
            payload=payload 
        )

        # 3. LINK PROOF DOCUMENT
        # We save the internal path (e.g. "uuid/file.pdf") to the database
        new_app.proof_document_url = payload.proof_document_url
        session.add(new_app)

        await session.commit()
        await session.refresh(new_app)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"CRITICAL ERROR creating application: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # 4. SEND EMAIL
    if current_user.email:
        email_data = {
            "name": current_user.name,
            "email": current_user.email,
            "application_id": str(new_app.id)
        }
        background_tasks.add_task(send_application_created_email, email_data)

    return ApplicationRead.model_validate(new_app)


# ------------------------------------------------------------
# GET MY APPLICATION (With Resubmission Support)
# ------------------------------------------------------------
@router.get("/my", status_code=200)
async def get_my_application(
    current_user: User = Depends(AllowRoles(UserRole.Student)),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    
    if not current_user.student_id:
        raise HTTPException(status_code=400, detail="No student linked to account")

    # ✅ FIX: Use UUID object directly
    student_id = current_user.student_id

    # 1. Get Application
    result = await session.execute(
        select(Application)
        .where(Application.student_id == student_id)
        .order_by(Application.created_at.desc())
        .options(
            selectinload(Application.student).selectinload(Student.school),
        )
    )
    app = result.scalars().first()

    if not app:
        return {
            "application": None,
            "message": "No application found."
        }

    # 2. Fetch Stages
    stage_result = await session.execute(
        select(ApplicationStage)
        .where(ApplicationStage.application_id == app.id)
        .order_by(ApplicationStage.sequence_order.asc())
    )
    stages = stage_result.scalars().all()

    # 3. Calculate Flags
    is_rejected = any(s.status == str(ApplicationStatus.REJECTED.value) for s in stages)
    rejected_stage = next((s for s in stages if s.status == str(ApplicationStatus.REJECTED.value)), None)
    is_completed = str(app.status) == str(ApplicationStatus.COMPLETED.value)

    #  4. GENERATE SIGNED URL
    # We take the stored path and convert it to a temporary secure link for VIEWING
    signed_proof_link = None
    if app.proof_document_url:
        signed_proof_link = get_signed_url(app.proof_document_url)

    # 5. Construct Full Response
    return {
        "student": {
            "full_name": app.student.full_name,
            "enrollment_number": app.student.enrollment_number,
            "roll_number": app.student.roll_number,
            "email": app.student.email,
            "mobile_number": app.student.mobile_number,
            "school_name": app.student.school.name if app.student.school else "N/A",
            "batch": app.student.batch,
            # Return these too so frontend form can pre-fill
            "father_name": app.student.father_name,
            "hostel_name": app.student.hostel_name,
        },
        "application": {
            "id": app.id,
            "status": app.status,
            "current_stage_order": app.current_stage_order,
            "remarks": app.remarks,
            
            # FIELD 1: Clickable Link (Signed, Expiring) -> For User to VIEW
            "proof_document_url": signed_proof_link, 
            
            # FIELD 2: Raw Path (Internal) -> For Frontend to RESUBMIT logic
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
# DOWNLOAD CERTIFICATE
# ------------------------------------------------------------
@router.get("/{application_id}/certificate", response_class=Response)
async def download_certificate(
    application_id: str,
    current_user: User = Depends(AllowRoles(UserRole.Student, UserRole.Admin)),
    session: AsyncSession = Depends(get_db_session),
):
    # Validate User Access
    if current_user.role == UserRole.Student:
        if not current_user.student_id:
             raise HTTPException(status_code=403, detail="Student profile missing")
             
        # Verify ownership
        result = await session.execute(
            select(Application).where(Application.id == application_id)
        )
        app = result.scalar_one_or_none()
        
        # ✅ FIX: Compare UUID objects or convert both to str safely
        if not app or str(app.student_id) != str(current_user.student_id):
            raise HTTPException(status_code=403, detail="Not authorized")

    try:
        app_uuid = UUID(application_id)
        
        # Generate PDF
        pdf_bytes = await generate_certificate_pdf(session, app_uuid)
        
        filename = f"No_Dues_Certificate_{application_id}.pdf"
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