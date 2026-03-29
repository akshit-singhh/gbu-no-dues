import os
import io
import uuid
import base64
import qrcode
import asyncio
import ssl
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from ftplib import FTP, FTP_TLS, error_perm

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

# =====================================================================
# CUSTOM FTP_TLS CLASS (Fixes the 425 TLS Session Resumption Error)
# =====================================================================
class ResumedFTP_TLS(FTP_TLS):
    """Extension of FTP_TLS to support TLS session resumption on the data channel."""
    def ntransfercmd(self, cmd, rest=None):
        conn, size = FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(
                conn,
                server_hostname=self.host,
                session=self.sock.session 
            )
        return conn, size
# =====================================================================

# -----------------------------
# CONFIGURATION
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
CERT_DIR = os.path.join(STATIC_DIR, "certificates")
os.makedirs(CERT_DIR, exist_ok=True)

pdf_executor = ThreadPoolExecutor(max_workers=4)
template_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)

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
# LOAD STORAGE CONFIG
# -----------------------------
# Looks for "STORAGE" first, falls back to "STORAGE_BACKEND", defaults to "FTP"
STORAGE_BACKEND = os.environ.get("STORAGE", os.environ.get("STORAGE_BACKEND", "FTP")).upper()

# Supabase
try:
    from app.core.supabase_client import supabase # type: ignore
except ImportError:
    supabase = None

# FTP
FTP_HOST = os.environ.get("FTP_HOST")
FTP_PORT = int(os.environ.get("FTP_PORT", 21))
FTP_USER = os.environ.get("FTP_USER")
FTP_PASSWORD = os.environ.get("FTP_PASSWORD")
FTP_PASSIVE_MODE = os.environ.get("FTP_PASSIVE_MODE", "True").lower() in ("true", "1", "yes")

# NEW CONFIG: Added Certificate Directory
FTP_CERTIFICATE_DIR = os.environ.get("FTP_CERTIFICATE_DIR", "/certificates")

FTP_USE_TLS = os.environ.get("FTP_USE_TLS", "True").lower() in ("true", "1", "yes")

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# -----------------------------
# MAIN FUNCTION
# -----------------------------
async def generate_certificate_pdf(
    session: AsyncSession,
    application_id: uuid.UUID,
    generated_by_id: uuid.UUID | None = None
) -> bytes:
    
    # 1. FETCH APPLICATION
    application = (await session.execute(
        select(Application).where(Application.id == application_id)
    )).scalar_one()

    # 2. FETCH STUDENT
    student = (await session.execute(
        select(Student)
        .options(
            selectinload(Student.school),
            selectinload(Student.department),
            selectinload(Student.programme),
            selectinload(Student.specialization)
        )
        .where(Student.id == application.student_id)
    )).scalar_one()

    # 3. FETCH STAGES
    stages_raw = (await session.execute(
        select(ApplicationStage, Department.name, User.name, Department.code)
        .outerjoin(Department, ApplicationStage.department_id == Department.id)
        .outerjoin(User, ApplicationStage.verified_by == User.id)
        .where(ApplicationStage.application_id == application.id)
        .order_by(ApplicationStage.sequence_order)
    )).all()

    formatted_stages = []
    ACADEMIC_ROLES = {"HOD", "DEAN", "PROGRAM_COORDINATOR"}

    for i, (stage, dept_name, reviewer_name, dept_code) in enumerate(stages_raw):
        role_key = stage.verifier_role.upper() if stage.verifier_role else "UNKNOWN"

        if i == 0:
            display_name = "School Office"
        elif role_key in ACADEMIC_ROLES:
            if role_key == "HOD":
                display_name = f"HOD ({dept_code if dept_code else dept_name})"
            elif role_key == "DEAN":
                display_name = f"Dean ({dept_name})" if dept_name else "School Dean"
            else:
                display_name = dept_name
        else:
            display_name = dept_name or role_key.replace("_", " ").title()

        formatted_stages.append({
            "department_name": display_name,
            "status": "Approved" if stage.status == "approved" else "Pending",
            "reviewer_name": reviewer_name or "System",
            "reviewed_at": stage.verified_at.strftime("%d-%m-%Y") if stage.verified_at else "-"
        })

    # 4. CERTIFICATE ID
    existing_cert = (await session.execute(
        select(Certificate).where(Certificate.application_id == application.id)
    )).scalar_one_or_none()

    readable_id = existing_cert.certificate_number if existing_cert else f"GBU-ND-{datetime.now().year}-{uuid.uuid4().hex[:5].upper()}"

    # 5. ASSETS: QR & Logo
    certificate_url = f"{settings.FRONTEND_URL}/verify/{readable_id}"
    qr = qrcode.QRCode(box_size=10, border=1, error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(certificate_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()

    logo_base64 = image_to_base64(os.path.join(STATIC_DIR, "images", "gbu_logo.png"))

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

    loop = asyncio.get_running_loop()
    pdf_bytes = await loop.run_in_executor(pdf_executor, _generate_pdf_sync, html_content)

    # -----------------------------
    # UPLOAD PDF TO STORAGE (FTP / Supabase)
    # -----------------------------
    pdf_name = f"certificate_{application.id}.pdf"
    pdf_url = ""

    try:
        if STORAGE_BACKEND == "SUPABASE" and supabase:
            supabase.storage.from_("certificates").upload(
                file=pdf_bytes,
                path=pdf_name,
                file_options={"content-type": "application/pdf", "upsert": "true"}
            )
            pdf_url = supabase.storage.from_("certificates").get_public_url(pdf_name).split("?")[0]

        elif STORAGE_BACKEND == "FTP":
            if not all([FTP_HOST, FTP_USER, FTP_PASSWORD]):
                raise Exception("FTP credentials missing")

            # APPLIED TLS FIXES
            if FTP_USE_TLS:
                ftp = ResumedFTP_TLS()
                ftp.connect(host=FTP_HOST, port=FTP_PORT, timeout=30)
                ftp.auth()
                ftp.login(user=FTP_USER, passwd=FTP_PASSWORD)
                ftp.prot_p()
            else:
                ftp = FTP()
                ftp.connect(host=FTP_HOST, port=FTP_PORT, timeout=30)
                ftp.login(user=FTP_USER, passwd=FTP_PASSWORD)

            ftp.set_pasv(FTP_PASSIVE_MODE)

            # UPDATED: Save to Certificate Directory instead of Uploads Directory
            ftp_dir = f"{FTP_CERTIFICATE_DIR}/{application.student_id}"
            try:
                ftp.cwd(ftp_dir)
            except error_perm:
                # Create folder recursively
                parts = ftp_dir.strip("/").split("/")
                path_accum = ""
                for part in parts:
                    if not part: continue
                    path_accum += f"/{part}"
                    try:
                        ftp.mkd(path_accum)
                    except error_perm:
                        pass
                ftp.cwd(ftp_dir)

            # APPLIED SSL EOF FIX
            try:
                ftp.storbinary(f"STOR {pdf_name}", io.BytesIO(pdf_bytes))
            except ssl.SSLEOFError:
                pass
                
            ftp.quit()

            pdf_url = f"{ftp_dir}/{pdf_name}"

    except Exception as e:
        print(f"⚠️ Storage upload failed: {e}")
        pdf_url = ""

    # -----------------------------
    # SAVE / UPDATE DB
    # -----------------------------
    if existing_cert:
        existing_cert.pdf_url = pdf_url
        existing_cert.generated_at = datetime.utcnow()
        session.add(existing_cert)
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