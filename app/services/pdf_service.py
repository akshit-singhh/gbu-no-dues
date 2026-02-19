import os
import io
import uuid
import base64
import qrcode
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ✅ WeasyPrint Imports
from weasyprint import HTML
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings
from app.models.application import Application
from app.models.student import Student
from app.models.application_stage import ApplicationStage
from app.models.department import Department
from app.models.user import User
from app.models.certificate import Certificate

# -----------------------------
# CONFIGURATION
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
CERT_DIR = os.path.join(STATIC_DIR, "certificates")

os.makedirs(CERT_DIR, exist_ok=True)

# Global executor to prevent blocking the Event Loop during PDF generation
pdf_executor = ThreadPoolExecutor(max_workers=4)

template_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True
)

# -----------------------------
# HELPER: Encode Image
# -----------------------------
def image_to_base64(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# -----------------------------
# HELPER: Sync PDF Generation
# -----------------------------
def _generate_pdf_sync(html_content: str) -> bytes:
    return HTML(string=html_content).write_pdf(presentational_hints=True)

# -----------------------------
# MAIN FUNCTION
# -----------------------------
async def generate_certificate_pdf(
    session: AsyncSession,
    application_id: uuid.UUID,
    generated_by_id: uuid.UUID | None = None
) -> bytes:
    
    # 1. FETCH APPLICATION
    stmt_app = select(Application).where(Application.id == application_id)
    application = (await session.execute(stmt_app)).scalar_one()

    # 2. FETCH STUDENT
    stmt_student = (
        select(Student)
        .options(
            selectinload(Student.school),
            selectinload(Student.department),
            selectinload(Student.programme),
            selectinload(Student.specialization)
        )
        .where(Student.id == application.student_id)
    )
    student = (await session.execute(stmt_student)).scalar_one()

    # 3. FETCH STAGES
    stages_query = (
        select(ApplicationStage, Department.name, User.name, Department.code)
        .outerjoin(Department, ApplicationStage.department_id == Department.id)
        .outerjoin(User, ApplicationStage.verified_by == User.id)
        .where(ApplicationStage.application_id == application.id)
        .order_by(ApplicationStage.sequence_order)
    )
    stages_raw = (await session.execute(stages_query)).all()

    formatted_stages = []

    # ✅ CONFIG: Academic Roles
    ACADEMIC_ROLES = {"HOD", "DEAN", "PROGRAM_COORDINATOR"}

    for i, (stage, dept_name, reviewer_name, dept_code) in enumerate(stages_raw):
        role_key = stage.verifier_role.upper() if stage.verifier_role else "UNKNOWN"
        
        # --- FIXED LOGIC START ---

        # 1. FIRST STAGE (Index 0) -> ALWAYS "School Office"
        # This handles the initial clearance. Even if verified by Admin, 
        # because it is Stage 1, we label it "School Office".
        if i == 0:
            display_name = "School Office"

        # 2. ACADEMIC ROLES (HOD, DEAN)
        elif role_key in ACADEMIC_ROLES:
            if role_key == "HOD":
                display_name = f"HOD ({dept_code if dept_code else dept_name})"
            elif role_key == "DEAN":
                display_name = f"Dean ({dept_name})" if dept_name else "School Dean"
            else:
                display_name = dept_name

        # 3. OTHER ROLES (Library, Accounts, CRC, etc.)
        # Since 'i > 0', we know this is NOT the main School Office stage.
        # We MUST trust the Department Name here (e.g., "Central Library").
        else:
            if dept_name:
                display_name = dept_name 
            else:
                # Fallback: If no department name, use the Role or User Name
                # e.g. "CHIEF_WARDEN" -> "Chief Warden"
                display_name = role_key.replace("_", " ").title()

        # --- LOGIC END ---

        formatted_stages.append({
            "department_name": display_name,
            "status": "Approved" if stage.status == "approved" else "Pending",
            "reviewer_name": reviewer_name or "System",
            "reviewed_at": stage.verified_at.strftime("%d-%m-%Y") if stage.verified_at else "-"
        })

    # 4. CERTIFICATE ID LOGIC
    stmt_cert = select(Certificate).where(Certificate.application_id == application.id)
    existing_cert = (await session.execute(stmt_cert)).scalar_one_or_none()

    if existing_cert:
        readable_id = existing_cert.certificate_number
    else:
        suffix = uuid.uuid4().hex[:5].upper()
        readable_id = f"GBU-ND-{datetime.now().year}-{suffix}"

    # 5. PREPARE ASSETS (QR & Logo)
    certificate_url = f"{settings.FRONTEND_URL}/verify/{readable_id}"
    
    qr = qrcode.QRCode(box_size=10, border=1, error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(certificate_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()

    logo_path = os.path.join(STATIC_DIR, "images", "gbu_logo.png")
    logo_base64 = image_to_base64(logo_path)

    # 6. RENDER TEMPLATE
    context = {
        "student": student,
        "stages": formatted_stages,
        "certificate_id": readable_id,
        "generation_date": datetime.now().strftime("%d-%m-%Y"),
        "current_year": datetime.now().year,
        "qr_base64": qr_base64,
        "logo_base64": logo_base64,
    }

    html_content = template_env.get_template("pdf/certificate_template.html").render(context)

    # 7. GENERATE PDF
    loop = asyncio.get_running_loop()
    pdf_bytes = await loop.run_in_executor(pdf_executor, _generate_pdf_sync, html_content)

    # 8. SAVE & UPDATE DB
    pdf_name = f"certificate_{application.id}.pdf"
    pdf_path = os.path.join(CERT_DIR, pdf_name)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    
    pdf_url = f"/static/certificates/{pdf_name}"

    if existing_cert:
        existing_cert.pdf_url = pdf_url
        existing_cert.generated_at = datetime.utcnow()
    else:
        new_cert = Certificate(
            id=uuid.uuid4(),
            application_id=application.id,
            certificate_number=readable_id,
            pdf_url=pdf_url,
            generated_at=datetime.utcnow(),
            generated_by=generated_by_id
        )
        session.add(new_cert)

    await session.commit()
    return pdf_bytes