import os
import pdfkit
import uuid
import random
import string
from uuid import UUID
from datetime import datetime
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.models.application import Application
from app.models.student import Student
from app.models.application_stage import ApplicationStage
from app.models.department import Department
from app.models.user import User
from app.models.enums import OverallApplicationStatus
from app.models.certificate import Certificate

# -----------------------------
# Setup Jinja2 Environment
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(BASE_DIR, 'templates', 'pdf')

# Ensure static directory for certificates exists
STATIC_CERT_DIR = os.path.join(BASE_DIR, 'static', 'certificates')
os.makedirs(STATIC_CERT_DIR, exist_ok=True)

pdf_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

# Cache the template for performance
try:
    certificate_template = pdf_env.get_template("certificate_template.html")
except Exception as e:
    raise FileNotFoundError(f"PDF template not found in {template_dir}: {e}")

# -----------------------------
# PDF Configuration
# -----------------------------
# Adjust path based on your environment
if os.name == 'nt': # Windows
    WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
else: # Linux / Docker
    WKHTMLTOPDF_PATH = '/usr/bin/wkhtmltopdf'

# Check if binary exists to avoid vague errors
if not os.path.exists(WKHTMLTOPDF_PATH):
    print(f"WARNING: wkhtmltopdf not found at {WKHTMLTOPDF_PATH}. PDF generation will fail.")

pdf_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

pdf_options = {
    'page-size': 'A4',
    'margin-top': '15mm',
    'margin-right': '15mm',
    'margin-bottom': '15mm',
    'margin-left': '15mm',
    'encoding': "UTF-8",
    'no-outline': None,
    'disable-smart-shrinking': None,
    'enable-local-file-access': None
}


def generate_readable_id():
    """Generates a format like GBU-ND-2025-XH7B2"""
    year = datetime.now().year
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"GBU-ND-{year}-{suffix}"

# -----------------------------
# PDF Generation Function
# -----------------------------
async def generate_certificate_pdf(
    session: AsyncSession, 
    application_id: UUID, 
    generated_by_id: UUID | None = None
) -> bytes:
    """
    1. Fetches Application Data
    2. Determines Certificate ID (Existing or New)
    3. Generates PDF with that specific ID
    4. Saves PDF to disk
    5. Records/Updates entry in 'certificates' table
    6. Returns PDF bytes
    """

    # 1. Fetch Application & Verify Status
    result = await session.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if not application:
        raise ValueError("Application not found")

    # Loose check to allow "Completed" string or Enum
    current_status = str(application.status) if not hasattr(application.status, 'value') else application.status.value
    if current_status != "Completed":
        raise ValueError(f"Certificate available only for completed applications. Current status: '{current_status}'")

    # 2. Fetch Student Details
    student_res = await session.execute(select(Student).where(Student.id == application.student_id))
    student = student_res.scalar_one()

    # 3. Fetch Stages
    stmt = (
        select(ApplicationStage, Department.name, User.name)
        .join(Department, ApplicationStage.department_id == Department.id)
        .outerjoin(User, ApplicationStage.reviewer_id == User.id)
        .where(ApplicationStage.application_id == application.id)
        .order_by(ApplicationStage.sequence_order)
    )
    stage_results = await session.execute(stmt)
    raw_stages = stage_results.all()

    stages_data = []
    for stage_obj, dept_name, reviewer_name in raw_stages:
        stages_data.append({
            "department_name": dept_name,
            "status": stage_obj.status,
            "reviewer_name": reviewer_name if reviewer_name else "System",
            "reviewed_at": stage_obj.reviewed_at.strftime("%d-%m-%Y") if stage_obj.reviewed_at else "N/A"
        })

    # 4. Determine Certificate ID BEFORE Rendering
    # Check if a certificate record already exists for this application
    cert_query = await session.execute(select(Certificate).where(Certificate.application_id == application.id))
    existing_cert = cert_query.scalar_one_or_none()

    if existing_cert:
        # Use the ID from the database
        cert_uuid = existing_cert.id
        # Use existing readable number or generate if missing
        readable_id = existing_cert.certificate_number or generate_readable_id()
    else:
        # Generate a new ID now, to be saved later
        cert_uuid = uuid.uuid4()
        readable_id = generate_readable_id()

    # 5. Prepare Template Context
    # Verify URL using the Certificate UUID (URL-safe)
    verify_url = f"{settings.FRONTEND_URL}/verify/{cert_uuid}"
    generation_date = datetime.now().strftime("%d-%m-%Y")
    
    context = {
        "student": student,
        "stages": stages_data,
        "certificate_id": readable_id,
        "generation_date": generation_date,
        "certificate_url": verify_url
    }

    # 6. Render HTML
    html_content = certificate_template.render(context)

    # 7. Convert to PDF Bytes
    try:
        pdf_bytes = pdfkit.from_string(html_content, False, options=pdf_options, configuration=pdf_config)
    except OSError as e:
        raise ValueError(f"PDF generation failed. Ensure wkhtmltopdf is installed. Error: {e}")

    # ---------------------------------------------------------
    # 8. SAVE TO DISK & DATABASE
    # ---------------------------------------------------------
    
    # A. Define filename and save path
    filename = f"certificate_{application.id}.pdf"
    file_path = os.path.join(STATIC_CERT_DIR, filename)
    
    # B. Write bytes to file
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    # C. Construct public URL
    file_url = f"/static/certificates/{filename}" 

    # D. Database Upsert
    if existing_cert:
        # Update existing record
        existing_cert.pdf_url = file_url
        existing_cert.generated_at = datetime.utcnow()
        if not existing_cert.certificate_number:
            existing_cert.certificate_number = readable_id
        if generated_by_id:
            existing_cert.generated_by = generated_by_id
        session.add(existing_cert)
    else:
        # Create new record
        new_cert = Certificate(
            id=cert_uuid, 
            application_id=application.id,
            generated_by=generated_by_id,
            pdf_url=file_url,
            certificate_number=readable_id,
            generated_at=datetime.utcnow()
        )
        session.add(new_cert)

    # E. Commit changes
    await session.commit()

    return pdf_bytes