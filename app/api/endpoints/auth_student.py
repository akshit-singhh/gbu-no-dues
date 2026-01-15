# app/api/endpoints/auth_student.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib

from app.api.deps import get_db_session
from app.schemas.auth import StudentLoginRequest, StudentLoginResponse
from app.services.auth_service import authenticate_student
from app.core.config import settings
from app.core.rate_limiter import limiter  # <--- Import Limiter

router = APIRouter(prefix="/api/students", tags=["Auth (Students)"])

def verify_captcha_hash(user_input: str, hash_from_frontend: str) -> bool:
    if not user_input or not hash_from_frontend:
        return False
    
    # Re-calculate hash to verify
    normalized = user_input.strip().upper()
    raw_str = f"{normalized}{settings.SECRET_KEY}"
    calculated_hash = hashlib.sha256(raw_str.encode()).hexdigest()
    
    return calculated_hash == hash_from_frontend

@router.post("/login", response_model=StudentLoginResponse)
@limiter.limit("5/minute")  # <--- 1. RATE LIMIT: Max 5 login attempts per minute per IP
async def student_login_endpoint(
    request: Request,  # <--- 2. MANDATORY: 'request' arg required for limiter
    data: StudentLoginRequest,
    session: AsyncSession = Depends(get_db_session)
):
    # 1. CAPTCHA Verification (Using Hash from Body)
    if not verify_captcha_hash(data.captcha_input, data.captcha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid CAPTCHA code."
        )

    # 2. Auth Logic
    auth = await authenticate_student(session, data.identifier, data.password)

    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid credentials"
        )

    return auth