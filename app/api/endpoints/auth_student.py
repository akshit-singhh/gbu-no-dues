# app/api/endpoints/auth_student.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_
import hashlib

from app.api.deps import get_db_session
from app.models.student import Student
from app.schemas.auth import (
    StudentLoginRequest, 
    StudentLoginResponse, 
    StudentRegisterRequest
)
from app.services.auth_service import authenticate_student
from app.core.security import get_password_hash, create_access_token
from app.core.config import settings
from app.core.rate_limiter import limiter 

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
# 1. STUDENT REGISTRATION (Prevents Duplicates)
# ----------------------------------------------------------------
@router.post("/register", response_model=StudentLoginResponse)
async def register_student(
    payload: StudentRegisterRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Registers a new student.
    checks Email, Roll Number, AND Enrollment Number for duplicates.
    """
    
    # ✅ ROBUST CHECK: Query all unique identifiers at once
    query = select(Student).where(
        or_(
            Student.email == payload.email,
            Student.roll_number == payload.roll_number,
            Student.enrollment_number == payload.enrollment_number
        )
    )
    result = await session.execute(query)
    existing_student = result.scalars().first()

    if existing_student:
        # Determine exactly which field caused the conflict
        error_msg = "Account already exists."
        if existing_student.email == payload.email:
            error_msg = "Email is already registered. Please login."
        elif existing_student.roll_number == payload.roll_number:
            error_msg = f"Roll Number {payload.roll_number} is already registered."
        elif existing_student.enrollment_number == payload.enrollment_number:
            error_msg = f"Enrollment Number {payload.enrollment_number} is already registered."
            
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Create Student Record
    new_student = Student(
        full_name=payload.full_name,
        email=payload.email,
        roll_number=payload.roll_number,
        enrollment_number=payload.enrollment_number,
        mobile_number=payload.mobile_number,
        school_id=payload.school_id,
        password_hash=get_password_hash(payload.password),
        
        # Default Profile Fields
        father_name=payload.father_name,
        gender=payload.gender,
        batch=payload.batch,
        is_active=True
    )

    session.add(new_student)
    await session.commit()
    await session.refresh(new_student)

    # Auto-login after registration
    access_token = create_access_token(
        subject=str(new_student.id),
        role="student",
        name=new_student.full_name
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "student": new_student
    }


# ----------------------------------------------------------------
# 2. STUDENT LOGIN
# ----------------------------------------------------------------
@router.post("/login", response_model=StudentLoginResponse)
@limiter.limit("5/minute")  # Rate Limit: Max 5 login attempts per minute per IP
async def student_login_endpoint(
    request: Request,  # Required for limiter
    data: StudentLoginRequest,
    session: AsyncSession = Depends(get_db_session)
):
    # 1. CAPTCHA Verification
    if not verify_captcha_hash(data.captcha_input, data.captcha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid CAPTCHA code."
        )

    # 2. Auth Logic (Handles password verification)
    auth = await authenticate_student(session, data.identifier, data.password)

    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid credentials. Please check your Roll No / Email and password."
        )

    return auth