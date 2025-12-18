from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID

from app.api.deps import get_db_session
from app.models.application import Application
from app.models.student import Student
from app.models.enums import OverallApplicationStatus
from app.models.certificate import Certificate

router = APIRouter(tags=["Verification"])

# Ensure 'app/templates' exists
templates = Jinja2Templates(directory="app/templates")

@router.get("/verify/{certificate_id}", response_class=HTMLResponse)
async def verify_certificate(
    request: Request,
    certificate_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    # --- Helper to return Failed State ---
    def render_fail(msg):
        return templates.TemplateResponse("verification.html", {
            "request": request,
            "verified": False,
            "message": msg
        })

    certificate = None
    application = None

    # 1. Try to parse as UUID (Standard Logic)
    try:
        input_uuid = UUID(certificate_id)
        
        # Strategy A: Check if input_uuid is a CERTIFICATE ID
        cert_query = select(Certificate).where(Certificate.id == input_uuid)
        cert_res = await session.execute(cert_query)
        certificate = cert_res.scalar_one_or_none()

        if not certificate:
            # Strategy B: Check if input_uuid is an APPLICATION ID
            app_query = select(Application).where(Application.id == input_uuid)
            app_res = await session.execute(app_query)
            application = app_res.scalar_one_or_none()

            if application:
                # Found application! Now try to find its certificate
                cert_query_by_app = select(Certificate).where(Certificate.application_id == application.id)
                cert_res_by_app = await session.execute(cert_query_by_app)
                certificate = cert_res_by_app.scalar_one_or_none()

    except ValueError:
        # 2. If not UUID, assume it's a READABLE ID (e.g. GBU-ND-2025-XXXX)
        cert_query_readable = select(Certificate).where(Certificate.certificate_number == certificate_id)
        cert_res_readable = await session.execute(cert_query_readable)
        certificate = cert_res_readable.scalar_one_or_none()

    # 3. Final Fetching
    if certificate:
        if not application:
            app_query = select(Application).where(Application.id == certificate.application_id)
            app_res = await session.execute(app_query)
            application = app_res.scalar_one_or_none()
    
    # 4. Final Validation
    if not certificate:
        return render_fail("No valid certificate found for this ID.")
        
    if not application:
        return render_fail("Associated application record not found.")

    # 5. Check Status
    status_str = str(application.status) if not isinstance(application.status, str) else application.status
    if status_str != OverallApplicationStatus.Completed.value and status_str != "Completed":
        return render_fail(f"Application is '{status_str}' and not valid for certification.")

    # 6. Fetch Student Details
    student_query = select(Student).where(Student.id == application.student_id)
    student_res = await session.execute(student_query)
    student = student_res.scalar_one_or_none()
    
    if not student:
        return render_fail("Student record not found.")

    # 7. Render Success State
    return templates.TemplateResponse("verification.html", {
        "request": request,
        "verified": True,
        "student": student,
        "application": application,
        "certificate": certificate,
        "generation_date": certificate.generated_at.strftime("%d-%m-%Y")
    })