# app/api/endpoints/verification.py

from fastapi import APIRouter, Depends, Request, HTTPException, status, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID
import os

from app.api.deps import get_db_session

# --- MODELS ---
from app.models.application import Application
from app.models.student import Student
from app.models.certificate import Certificate

# --- SCHEMAS ---
from app.schemas.auth import (
    ForgotPasswordRequest, 
    VerifyOTPRequest, 
    ResetPasswordRequest
)

# --- SERVICES ---
from app.services.auth_service import (
    request_password_reset,
    verify_reset_otp,
    finalize_password_reset
)
from app.services.email_service import send_reset_password_email 

router = APIRouter(prefix="/api/verification", tags=["Verification"])

# Ensure templates directory is correct
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ===================================================================
# 1. CERTIFICATE VERIFICATION (ROBUST VERSION)
# ===================================================================
@router.get("/verify/{certificate_id}", response_class=HTMLResponse)
async def verify_certificate(
    request: Request,
    certificate_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Verifies certificate step-by-step to avoid Inner Join failures.
    """
    
    # Clean the input (Remove hidden spaces/newlines)
    clean_id = certificate_id.strip()
    print(f"🔍 DEBUG: Searching for Certificate ID: '{clean_id}'")

    # Helper for failed state
    def render_fail(msg):
        print(f"❌ DEBUG: Verification Failed - {msg}")
        return templates.TemplateResponse("verification.html", {
            "request": request,
            "valid": False,
            "message": msg
        })

    # ---------------------------------------------------------
    # STEP 1: Find Certificate (No Joins yet)
    # ---------------------------------------------------------
    query = select(Certificate)
    
    try:
        # Try as UUID
        cert_uuid = UUID(clean_id)
        query = query.where(Certificate.id == cert_uuid)
    except ValueError:
        # Try as String (Certificate Number)
        query = query.where(Certificate.certificate_number == clean_id)

    result = await session.execute(query)
    certificate = result.scalar_one_or_none()

    if not certificate:
        return render_fail(f"Certificate record not found for ID: {clean_id}")

    # ---------------------------------------------------------
    # STEP 2: Find Linked Application
    # ---------------------------------------------------------
    app_res = await session.execute(
        select(Application).where(Application.id == certificate.application_id)
    )
    application = app_res.scalar_one_or_none()

    if not application:
        return render_fail("Certificate exists, but linked Application is missing.")

    # ---------------------------------------------------------
    # STEP 3: Find Linked Student
    # ---------------------------------------------------------
    student_res = await session.execute(
        select(Student).where(Student.id == application.student_id)
    )
    student = student_res.scalar_one_or_none()

    if not student:
        return render_fail("Application exists, but linked Student data is missing.")

    # ---------------------------------------------------------
    # STEP 4: Render Success
    # ---------------------------------------------------------
    print(f"✅ DEBUG: Verification Successful for {student.full_name}")
    
    return templates.TemplateResponse("verification.html", {
        "request": request,
        "valid": True,
        "student": student,
        "application": application,
        "certificate": certificate,
        "generation_date": certificate.generated_at.strftime("%d %B, %Y")
    })


# ===================================================================
# 2. PASSWORD RESET ENDPOINTS (UNCHANGED)
# ===================================================================

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    payload: ForgotPasswordRequest, 
    background_tasks: BackgroundTasks, 
    session: AsyncSession = Depends(get_db_session)
):
    try:
        otp, user = await request_password_reset(session, payload.email)
        email_data = {"name": user.name, "email": user.email, "otp": otp}
        background_tasks.add_task(send_reset_password_email, email_data)
        return {"message": "OTP sent successfully. Please check your mail."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/verify-reset-otp", status_code=status.HTTP_200_OK)
async def verify_reset_otp_endpoint(
    payload: VerifyOTPRequest, 
    session: AsyncSession = Depends(get_db_session)
):
    is_valid = await verify_reset_otp(session, payload.email, payload.otp)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    return {"message": "OTP verified successfully"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: ResetPasswordRequest, 
    session: AsyncSession = Depends(get_db_session)
):
    try:
        await finalize_password_reset(session, payload.email, payload.otp, payload.new_password)
        return {"message": "Password updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))