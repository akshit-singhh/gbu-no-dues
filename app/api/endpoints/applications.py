from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import get_db_session
from app.core.rbac import AllowRoles
from app.models.user import User, UserRole
from app.models.application import Application
from app.models.application_stage import ApplicationStage
from app.schemas.application import ApplicationCreate, ApplicationRead
from app.services.application_service import create_application_for_student
from app.services.email_service import send_application_created_email

# We need the Enum for the pre-check (optional, but good for consistency)
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