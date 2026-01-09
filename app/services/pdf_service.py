# app/services/pdf_service.py

import os
import pdfkit
import uuid
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
# CONFIGURATION
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_CERT_DIR = os.path.join(BASE_DIR, 'static', 'certificates')

# Ensure directories exist
os.makedirs(STATIC_CERT_DIR, exist_ok=True)

# Jinja2 Setup
template_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

# PDFKit Configuration
# ⚠️ IMPORTANT: Update this path to where wkhtmltopdf is installed on your machine
# Windows Example: r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
# Linux/Docker Example: "/usr/bin/wkhtmltopdf"
if os.name == 'nt':
    WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe" 
else:
    WKHTMLTOPDF_PATH = '/usr/bin/wkhtmltopdf'

config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

options = {
    'page-size': 'A4',
    'margin-top': '15mm',
    'margin-right': '15mm',
    'margin-bottom': '15mm',
    'margin-left': '15mm',
    'encoding': "UTF-8",
    'no-outline': None,
    'enable-local-file-access': None,
    'disable-smart-shrinking': None
}


# -----------------------------
# MAIN GENERATION FUNCTION
# -----------------------------
async def generate_certificate_pdf(
    session: AsyncSession, 
    application_id: uuid.UUID, 
    generated_by_id: uuid.UUID | None = None
) -> bytes:
    """
    Generates a PDF using the 'certificate_template.html' and wkhtmltopdf.
    """

    # 1. Fetch Application & Student
    result = await session.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one()

    student_res = await session.execute(select(Student).where(Student.id == application.student_id))
    student = student_res.scalar_one()

    # 2. Fetch Stages (with Join for Department & Reviewer Names)
    #    We need this to populate the "Clearance Status" table in your HTML
    query = (
        select(ApplicationStage, Department.name, User.name)
        .outerjoin(Department, ApplicationStage.department_id == Department.id)
        .outerjoin(User, ApplicationStage.verified_by == User.id)
        .where(ApplicationStage.application_id == application.id)
        .order_by(ApplicationStage.sequence_order)
    )
    
    stages_res = await session.execute(query)
    raw_stages = stages_res.all()

    # 3. Transform Stages Data for Jinja Template
    #    Your HTML expects: department_name, status, reviewer_name, reviewed_at
    formatted_stages = []
    for stage, dept_name, reviewer_name in raw_stages:
        # Determine Display Name (Department Name OR Role Name)
        display_name = dept_name if dept_name else stage.verifier_role.replace("_", " ").title()
        
        # Format Date
        date_str = stage.verified_at.strftime("%d-%m-%Y") if stage.verified_at else "-"
        
        # Handle "Approved" vs "Pending" styling logic
        status_text = "Approved" if stage.status == "approved" else "Pending"

        formatted_stages.append({
            "department_name": display_name,
            "status": status_text,
            "reviewer_name": reviewer_name if reviewer_name else "System",
            "reviewed_at": date_str
        })

    # 4. Handle Certificate ID (Get Existing or Create New)
    cert_query = await session.execute(select(Certificate).where(Certificate.application_id == application.id))
    existing_cert = cert_query.scalar_one_or_none()

    if existing_cert:
        cert_uuid = existing_cert.id
        readable_id = existing_cert.certificate_number
        if not readable_id:
            # Generate one if missing (format: GBU-ND-YYYY-XXXXX)
            suffix = str(uuid.uuid4().hex)[:5].upper()
            readable_id = f"GBU-ND-{datetime.now().year}-{suffix}"
    else:
        cert_uuid = uuid.uuid4()
        suffix = str(uuid.uuid4().hex)[:5].upper()
        readable_id = f"GBU-ND-{datetime.now().year}-{suffix}"

    # 5. Prepare Context for HTML
    #    These variables map directly to the {{ variables }} in your HTML
    generation_date = datetime.now().strftime("%d-%m-%Y")
    certificate_url = f"{settings.FRONTEND_URL}/verify/{readable_id}" # QR Code Link

    context = {
        "student": student,
        "stages": formatted_stages,
        "certificate_id": readable_id,
        "generation_date": generation_date,
        "certificate_url": certificate_url
    }

    # 6. Render HTML
    try:
        template = template_env.get_template("pdf/certificate_template.html")
        html_content = template.render(context)
    except Exception as e:
        raise ValueError(f"Template rendering failed. Check 'certificate_template.html'. Error: {e}")

    # 7. Generate PDF
    try:
        pdf_bytes = pdfkit.from_string(html_content, False, configuration=config, options=options)
    except OSError as e:
        # Common error if wkhtmltopdf is not found in path
        raise RuntimeError(f"wkhtmltopdf failed. Is the path correct? {WKHTMLTOPDF_PATH}. Error: {e}")

    # 8. Save to Disk
    filename = f"certificate_{application.id}.pdf"
    file_path = os.path.join(STATIC_CERT_DIR, filename)
    file_url = f"/static/certificates/{filename}"

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    # 9. Update Database Record
    if existing_cert:
        existing_cert.pdf_url = file_url
        existing_cert.generated_at = datetime.utcnow()
        existing_cert.certificate_number = readable_id
        if generated_by_id:
            existing_cert.generated_by = generated_by_id
        session.add(existing_cert)
    else:
        new_cert = Certificate(
            id=cert_uuid,
            application_id=application.id,
            generated_by=generated_by_id,
            pdf_url=file_url,
            certificate_number=readable_id,
            generated_at=datetime.utcnow()
        )
        session.add(new_cert)

    await session.commit()
    return pdf_bytes