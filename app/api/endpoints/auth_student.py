# app/api/endpoints/auth_student.py

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib

from app.api.deps import get_db_session
from app.core.config import settings
from app.core.rate_limiter import limiter 
from app.core.security import create_access_token

# Schemas
from app.schemas.auth import (
    StudentLoginRequest, 
    StudentLoginResponse, 
    StudentRegisterRequest
)

# Services
from app.services.auth_service import authenticate_student
from app.services.student_service import register_student_and_user
from app.services.email_service import send_welcome_email

router = APIRouter(prefix="/api/students", tags=["Auth (Students)"])

# ----------------------------------------------------------------
# HELPER: Verify Captcha
# ----------------------------------------------------------------
def verify_captcha_hash(user_input: str, hash_from_frontend: str) -> bool:
    if not user_input or not hash_from_frontend:
        return False
    
    # Re-calculate hash to verify
    normalized = user_input.strip().upper()
    raw_str = f"{normalized}{settings.SECRET_KEY}"
    calculated_hash = hashlib.sha256(raw_str.encode()).hexdigest()
    
    return calculated_hash == hash_from_frontend


# ----------------------------------------------------------------
# 1. STUDENT REGISTRATION (Public)
# ----------------------------------------------------------------
@router.post("/register", response_model=StudentLoginResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # Rate Limit protection
async def register_student(
    request: Request, # Required for limiter
    data: StudentRegisterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Registers a new student, creates a User account, sends a welcome email,
    and returns an access token immediately (Auto-Login).
    """
    
    # 1. Registration Logic (Service handles duplicate checks)
    try:
        # Note: We map StudentRegisterRequest (Auth Schema) to the service
        student = await register_student_and_user(session, data)
        
        # 2. Send Welcome Email
        email_data = {
            "full_name": student.full_name,
            "enrollment_number": student.enrollment_number,
            "roll_number": student.roll_number,
            "email": student.email
        }
        background_tasks.add_task(send_welcome_email, email_data)

        # 3. Fetch Linked User to Generate Token
        # We know the user exists because the service just created it.
        # But we need the ID for the token subject.
        from app.services.auth_service import get_user_by_email
        user = await get_user_by_email(session, student.email)
        
        if not user:
            raise HTTPException(status_code=500, detail="User account creation failed unexpectedly.")

        # 4. Generate Token (Auto-Login)
        access_token = create_access_token(
            subject=str(user.id),
            data={
                "role": "student",
                "student_id": str(student.id),
                "school_id": student.school_id
            }
        )

        # 5. Prepare Response
        # We manually inject school_name since Pydantic strips relations by default
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
        # Catch duplicates or validation errors from service
        raise HTTPException(status_code=400, detail=str(e))


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
        # Updated error message to match UI (Roll No / Enrollment No only)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid credentials. Please check your Roll Number or Enrollment Number and password."
        )

    return auth
