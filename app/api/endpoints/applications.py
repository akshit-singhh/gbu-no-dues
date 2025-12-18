from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID

from app.api.deps import get_db_session
from app.core.rbac import AllowRoles
from app.models.user import User, UserRole
from app.models.application import Application
from app.models.application_stage import ApplicationStage
from app.schemas.application import ApplicationCreate, ApplicationRead
from app.services.application_service import create_application_for_student
from app.services.email_service import send_application_created_email
from app.services.pdf_service import generate_certificate_pdf
from app.models.enums import OverallApplicationStatus

router = APIRouter(
    prefix="/api/applications",
    tags=["Applications"]
)


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

    student_id = str(current_user.student_id) # Ensure it's a string for the service

    # Optional: Fast-fail check at endpoint level
    # (The service also checks this, but this saves a service call if obvious)
    result = await session.execute(
        select(Application)
        .where(
            (Application.student_id == student_id) &
            (Application.status.in_([
                OverallApplicationStatus.Pending,
                OverallApplicationStatus.InProgress
            ]))
        )
    )
    existing_app = result.scalars().first()

    if existing_app:
        raise HTTPException(
            status_code=400,
            detail="You already have an active application."
        )

    # Call Service Layer with Error Handling
    try:
        new_app = await create_application_for_student(
            session=session,
            student_id=student_id,
            payload=payload.dict(exclude_none=True)
        )
    except ValueError as e:
        # This catches "Already completed", "Student not found", etc.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Log the actual error for debugging (print or logger)
        print(f"CRITICAL ERROR creating application: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the application."
        )

    # Send Email Notification via Background Task
    if current_user.email:
        email_data = {
            "name": current_user.name,
            "email": current_user.email,
            "application_id": str(new_app.id)
        }
        background_tasks.add_task(send_application_created_email, email_data)

    return ApplicationRead.from_orm(new_app)


# ------------------------------------------------------------
# GET MY APPLICATION + STAGES
# ------------------------------------------------------------
@router.get("/my", status_code=200)
async def get_my_application(
    current_user: User = Depends(AllowRoles(UserRole.Student)),
    session: AsyncSession = Depends(get_db_session),
):
    if not current_user.student_id:
        raise HTTPException(status_code=400, detail="No student linked to account")

    student_id = str(current_user.student_id)

    # Get latest application (student may have previous completed ones)
    result = await session.execute(
        select(Application)
        .where(Application.student_id == student_id)
        .order_by(Application.created_at.desc())
    )
    app = result.scalars().first()

    if not app:
        return {
            "application": None,
            "message": "No application found for this student."
        }

    # Fetch its stages
    stage_result = await session.execute(
        select(ApplicationStage)
        .where(ApplicationStage.application_id == app.id)
        .order_by(ApplicationStage.sequence_order.asc())
    )
    stages = stage_result.scalars().all()

    # Flags
    is_rejected = any(s.status == "Rejected" for s in stages)
    rejected_stage = next((s for s in stages if s.status == "Rejected"), None)
    is_completed = all(s.status == "Approved" for s in stages)

    return {
        "application": {
            "id": app.id,
            "status": app.status,
            "current_department_id": app.current_department_id,
            "remarks": app.remarks,
            "created_at": app.created_at,
            "updated_at": app.updated_at,
        },
        "stages": [
            {
                "id": s.id,
                "department_id": s.department_id,
                "status": s.status,
                "priority": s.priority,
                "remarks": s.remarks,
                "reviewer_id": s.reviewer_id,
                "sequence_order": s.sequence_order,
                "reviewed_at": s.reviewed_at,
            }
            for s in stages
        ],
        "flags": {
            "is_rejected": is_rejected,
            "is_completed": is_completed,
            "is_in_progress": (app.status == "InProgress"),
        },
        "rejection_details": {
            "department_id": rejected_stage.department_id if rejected_stage else None,
            "remarks": rejected_stage.remarks if rejected_stage else None
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
    # If student, ensure they own the application
    if current_user.role == UserRole.Student:
        # Fetch app simple check
        result = await session.execute(
            select(Application).where(Application.id == application_id)
        )
        app = result.scalar_one_or_none()
        
        # Check existence and ownership
        if not app or str(app.student_id) != str(current_user.student_id):
            raise HTTPException(status_code=403, detail="Not authorized to access this certificate")

    try:
        # Convert string to standard Python UUID object
        app_uuid = UUID(application_id)
        
        # Generate PDF bytes
        pdf_bytes = await generate_certificate_pdf(session, app_uuid)
        
        # Return PDF
        filename = f"No_Dues_Certificate_{application_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        # Catch logic errors from the service (e.g., app not completed)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Catch system errors (e.g., pdfkit issues)
        print(f"Certificate Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error generating certificate")