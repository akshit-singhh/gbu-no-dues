# app/services/pdf_service.py

import os
import io
import uuid
import base64
import pdfkit
import qrcode
from datetime import datetime
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings
from app.models.application import Application
from app.models.student import Student
from app.models.application_stage import ApplicationStage
from app.models.department import Department
from app.models.user import User
from app.models.certificate import Certificate

# -----------------------------
# PATH CONFIGURATION
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
CERT_DIR = os.path.join(STATIC_DIR, "certificates")

os.makedirs(CERT_DIR, exist_ok=True)

# -----------------------------
# JINJA2 SETUP
# -----------------------------
template_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True
)

# -----------------------------
# WKHTMLTOPDF CONFIG
# -----------------------------
if os.name == "nt":
    WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
else:
    WKHTMLTOPDF_PATH = "/usr/bin/wkhtmltopdf"

config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

options = {
    "page-size": "A4",
    "margin-top": "15mm",
    "margin-right": "15mm",
    "margin-bottom": "15mm",
    "margin-left": "15mm",
    "encoding": "UTF-8",
    "dpi": 300,
    "zoom": 1,
    "disable-smart-shrinking": None,
    "print-media-type": None,
    "enable-local-file-access": None,
    "no-outline": None
}

# -----------------------------
# HELPER: Encode Image to Base64
# -----------------------------
def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return encoded

# -----------------------------
# MAIN FUNCTION
# -----------------------------
async def generate_certificate_pdf(
    session: AsyncSession,
    application_id: uuid.UUID,
    generated_by_id: uuid.UUID | None = None
) -> bytes:
    """
    Generates a PDF certificate using wkhtmltopdf with embedded logo and QR.
    No local QR or logo files are required.
    """

    # -----------------------------
    # FETCH APPLICATION & STUDENT
    # -----------------------------
    application = (
        await session.execute(
            select(Application).where(Application.id == application_id)
        )
    ).scalar_one()

    student = (
        await session.execute(
            select(Student).where(Student.id == application.student_id)
        )
    ).scalar_one()

    # -----------------------------
    # FETCH STAGES
    # -----------------------------
    stages_query = (
        select(ApplicationStage, Department.name, User.name)
        .outerjoin(Department, ApplicationStage.department_id == Department.id)
        .outerjoin(User, ApplicationStage.verified_by == User.id)
        .where(ApplicationStage.application_id == application.id)
        .order_by(ApplicationStage.sequence_order)
    )

    stages_raw = (await session.execute(stages_query)).all()

    formatted_stages = []
    for stage, dept_name, reviewer_name in stages_raw:
        formatted_stages.append({
            "department_name": dept_name or stage.verifier_role.replace("_", " ").title(),
            "status": "Approved" if stage.status == "approved" else "Pending",
            "reviewer_name": reviewer_name or "System",
            "reviewed_at": stage.verified_at.strftime("%d-%m-%Y") if stage.verified_at else "-"
        })

    # -----------------------------
    # CERTIFICATE ID
    # -----------------------------
    cert = (
        await session.execute(
            select(Certificate).where(Certificate.application_id == application.id)
        )
    ).scalar_one_or_none()

    if cert:
        readable_id = cert.certificate_number
    else:
        suffix = uuid.uuid4().hex[:5].upper()
        readable_id = f"GBU-ND-{datetime.now().year}-{suffix}"

    # -----------------------------
    # QR CODE (IN-MEMORY)
    # -----------------------------
    certificate_url = f"{settings.FRONTEND_URL}/verify/{readable_id}"
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(certificate_url)
    qr.make(fit=True)

    qr_image = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()

    # -----------------------------
    # LOGO (IN-MEMORY)
    # -----------------------------
    logo_path = os.path.join(STATIC_DIR, "images", "gbu_logo.png")
    logo_base64 = image_to_base64(logo_path)

    # -----------------------------
    # TEMPLATE CONTEXT
    # -----------------------------
    context = {
        "student": student,
        "stages": formatted_stages,
        "certificate_id": readable_id,
        "generation_date": datetime.now().strftime("%d-%m-%Y"),
        "certificate_url": certificate_url,
        "qr_base64": qr_base64,
        "logo_base64": logo_base64
    }

    # -----------------------------
    # RENDER HTML
    # -----------------------------
    html = template_env.get_template("pdf/certificate_template.html").render(context)

    # -----------------------------
    # GENERATE PDF
    # -----------------------------
    pdf_bytes = pdfkit.from_string(html, False, configuration=config, options=options)

    # -----------------------------
    # SAVE PDF (OPTIONAL)
    # -----------------------------
    pdf_name = f"certificate_{application.id}.pdf"
    pdf_path = os.path.join(CERT_DIR, pdf_name)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    pdf_url = f"/static/certificates/{pdf_name}"

    # -----------------------------
    # SAVE DB RECORD
    # -----------------------------
    if cert:
        cert.pdf_url = pdf_url
        cert.generated_at = datetime.utcnow()
        cert.certificate_number = readable_id
        cert.generated_by = generated_by_id
        session.add(cert)
    else:
        session.add(Certificate(
            id=uuid.uuid4(),
            application_id=application.id,
            certificate_number=readable_id,
            pdf_url=pdf_url,
            generated_at=datetime.utcnow(),
            generated_by=generated_by_id
        ))

    await session.commit()
    return pdf_bytes
