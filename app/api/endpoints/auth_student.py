# app/api/endpoints/auth_student.py

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_
from sqlalchemy.orm import selectinload
import hashlib

from app.api.deps import get_db_session
from app.core.config import settings
from app.core.rate_limiter import limiter 
from app.core.security import create_access_token
from app.models.student import Student
from app.models.user import User

# Schemas
from app.schemas.auth import (
    StudentLoginRequest, 
    StudentLoginResponse, 
    StudentRegisterRequest
)

# Services
from app.services.auth_service import authenticate_student, get_user_by_email, register_student as register_student_service
from app.services.email_service import send_welcome_email

router = APIRouter(prefix="/api/students", tags=["Auth (Students)"])

# ----------------------------------------------------------------
# HELPER: Verify Captcha
# ----------------------------------------------------------------
def verify_captcha_hash(user_input: str, hash_from_frontend: str) -> bool:
    if not user_input or not hash_from_frontend:
        return False
    normalized = user_input.strip().upper()
    raw_str = f"{normalized}{settings.SECRET_KEY}"
    calculated_hash = hashlib.sha256(raw_str.encode()).hexdigest()
    return calculated_hash == hash_from_frontend


# ----------------------------------------------------------------
# 1. STUDENT REGISTRATION (Public)
# ----------------------------------------------------------------
@router.post("/register", response_model=StudentLoginResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute") 
async def register_student(
    request: Request,
    data: StudentRegisterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Registers a new student, creates a User account, and auto-logins.
    """
    
    # 1. CAPTCHA Verification
    if not verify_captcha_hash(data.captcha_input, data.captcha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid CAPTCHA code. Please refresh and try again."
        )

    # 2. Perform Registration
    try:
        # Call the service in auth_service.py
        created_student = await register_student_service(session, data)
        
        # 3. Reload Student with School Data (Critical for Response)
        # We must re-fetch the student with the relationship loaded to avoid 500 Error
        refresh_query = (
            select(Student)
            .options(selectinload(Student.school))
            .where(Student.id == created_student.id)
        )
        refresh_res = await session.execute(refresh_query)
        student = refresh_res.scalar_one()

        # 4. Fetch User for Token (User ID needed for Subject)
        user = await get_user_by_email(session, student.email)
        if not user:
            raise HTTPException(500, "Account created but user link failed.")

        # 5. Send Welcome Email (Background Task)
        email_data = {
            "full_name": student.full_name,
            "enrollment_number": student.enrollment_number,
            "roll_number": student.roll_number,
            "email": student.email
        }
        background_tasks.add_task(send_welcome_email, email_data)

        # 6. Generate Access Token (Auto-Login)
        access_token = create_access_token(
            subject=str(user.id),
            data={
                "role": "student",
                "student_id": str(student.id),
                "school_id": student.school_id
            }
        )

        # 7. Prepare Response
        # Safely extract school name
        student_dict = student.model_dump()
        student_dict["school_name"] = student.school.name if student.school else "Unknown School"

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "student_id": student.id,
            "student": student_dict
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Fallback for unexpected errors
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


# ----------------------------------------------------------------
# 2. STUDENT LOGIN
# ----------------------------------------------------------------
@router.post("/login", response_model=StudentLoginResponse)
@limiter.limit("5/minute") 
async def student_login_endpoint(
    request: Request, 
    data: StudentLoginRequest,
    session: AsyncSession = Depends(get_db_session)
):
    # 1. CAPTCHA Verification
    if not verify_captcha_hash(data.captcha_input, data.captcha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid CAPTCHA code. Please refresh and try again."
        )

    # 2. Auth Logic
    auth = await authenticate_student(session, data.identifier, data.password)

    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid credentials. Please check your Roll No / Enrollment No and password."
        )

    return auth