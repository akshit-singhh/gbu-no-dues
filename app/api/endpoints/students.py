# app/api/endpoints/students.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib

from app.api.deps import get_db_session
from app.core.rbac import AllowRoles
from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.student import StudentRegister, StudentRead, StudentUpdate
from app.core.rate_limiter import limiter  # <--- Import Limiter

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

# ----------------------------------------------------------------
# HELPER: Verify Captcha (Hash-based)
# ----------------------------------------------------------------
def verify_captcha_hash(user_input: str, hash_from_frontend: str) -> bool:
    if not user_input or not hash_from_frontend:
        return False
    
    # Normalize input and recreate the hash using the App Secret
    normalized = user_input.strip().upper()
    raw_str = f"{normalized}{settings.SECRET_KEY}"
    calculated_hash = hashlib.sha256(raw_str.encode()).hexdigest()
    
    return calculated_hash == hash_from_frontend

# ------------------------------------------------------------
# STUDENT SELF-REGISTRATION (PUBLIC) - [RATE LIMITED]
# ------------------------------------------------------------
@router.post("/register", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # <--- RATE LIMIT: 5 attempts per minute per IP
async def register_student(
    request: Request,  # <--- MANDATORY: 'request' arg required for limiter
    data: StudentRegister,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
):
    # 1. CAPTCHA Verification (Using Hash from Body)
    if not data.captcha_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="CAPTCHA hash missing. Please refresh the page."
        )
    
    if not verify_captcha_hash(data.captcha_input, data.captcha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid CAPTCHA code."
        )

    # 2. Registration Logic
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