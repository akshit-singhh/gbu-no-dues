# app/api/endpoints/students.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.rbac import AllowRoles
from app.models.user import User, UserRole
from app.schemas.student import StudentRegister, StudentRead, StudentUpdate

from app.services.student_service import (
    register_student_and_user,
    get_student_by_id,
    update_student_profile
)
from app.services.email_service import send_welcome_email

router = APIRouter(
    prefix="/api/students",
    tags=["Students"]
)

# ------------------------------------------------------------
# STUDENT SELF-REGISTRATION (PUBLIC)
# ------------------------------------------------------------
@router.post("/register", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def register_student(
    data: StudentRegister,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        student = await register_student_and_user(session, data)
        
        email_data = {
            "full_name": student.full_name,
            "enrollment_number": student.enrollment_number,
            "roll_number": student.roll_number,
            "email": student.email
        }
        background_tasks.add_task(send_welcome_email, email_data)

        return StudentRead.model_validate(student)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------
# GET "MY PROFILE"
# ------------------------------------------------------------
@router.get("/me", response_model=StudentRead)
async def get_my_student_profile(
    current_user: User = Depends(AllowRoles(UserRole.Student, UserRole.Admin)),
    session: AsyncSession = Depends(get_db_session),
):
    if not current_user.student_id:
        raise HTTPException(status_code=404, detail="Student profile not linked")

    student = await get_student_by_id(session, current_user.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return StudentRead.model_validate(student)


# ------------------------------------------------------------
# UPDATE PROFILE (General Update)
# ------------------------------------------------------------
@router.patch("/update", response_model=StudentRead)
async def update_my_profile(
    update_data: StudentUpdate,
    current_user: User = Depends(AllowRoles(UserRole.Student)),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Allows the student to update their profile details (Address, Mobile, etc.)
    independently of the application process.
    """
    if not current_user.student_id:
        raise HTTPException(status_code=404, detail="Student profile not linked")

    try:
        updated_student = await update_student_profile(
            session, 
            current_user.student_id, 
            update_data
        )
        return StudentRead.model_validate(updated_student)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))