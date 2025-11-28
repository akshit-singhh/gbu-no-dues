# app/api/endpoints/students.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.rbac import AllowRoles
from app.models.user import User, UserRole
from app.schemas.student import StudentRegister, StudentRead
from app.schemas.auth_student import StudentLoginRequest, StudentLoginResponse
from app.services.student_service import (
    register_student_and_user,
    get_student_by_id,
    list_students,
)
from app.services.auth_service import authenticate_student
from app.services.email_service import send_welcome_email

router = APIRouter(
    prefix="/api/students",
    tags=["Students"]
)


# ------------------------------------------------------------
# STUDENT LOGIN
# ------------------------------------------------------------
@router.post("/login", response_model=StudentLoginResponse)
async def student_login(
    data: StudentLoginRequest,
    session: AsyncSession = Depends(get_db_session)
):
    auth = await authenticate_student(session, data.identifier, data.password)

    if not auth:
        raise HTTPException(status_code=401, detail="Invalid Enrollment/Roll Number or password")

    return auth


# ------------------------------------------------------------
# STUDENT SELF-REGISTRATION (PUBLIC)
# ------------------------------------------------------------
@router.post("/register", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def register_student(
    data: StudentRegister,
    background_tasks: BackgroundTasks,  # <-- Add this parameter
    session: AsyncSession = Depends(get_db_session),
):

    if data.password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    try:
        # Create student in DB
        student = await register_student_and_user(session, data)
        
        # Prepare data for email
        # We convert to a dict explicitly to pass to the background task
        # so it doesn't rely on the DB session (which will close)
        email_data = {
            "full_name": student.full_name,
            "enrollment_number": student.enrollment_number,
            "roll_number": student.roll_number,
            "email": student.email
        }
        
        # Queue the email task
        # This will run AFTER the return statement sends the 201 response
        background_tasks.add_task(send_welcome_email, email_data)

        return StudentRead.from_orm(student)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------
# GET "MY PROFILE" (student or super admin)
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

    return StudentRead.from_orm(student)