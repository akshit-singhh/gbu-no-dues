# app/services/email_service.py

import smtplib
import os
import asyncio
import logging
from functools import partial
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings

# ---------------------------------------------------------
# SETUP LOGGING
# ---------------------------------------------------------
logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# TEMPLATE HELPER
# ---------------------------------------------------------
def get_template(template_name: str):
    """
    Loads email templates from the 'app/templates/email' directory.
    Using os.path.abspath ensures it works regardless of where the server is started.
    """
    template_dir = os.path.join(os.path.abspath(os.getcwd()), 'app', 'templates', 'email')
    env = Environment(loader=FileSystemLoader(template_dir))
    return env.get_template(template_name)


# ---------------------------------------------------------
# SYNC SMTP SENDER (Blocking IO - Run in Executor)
# ---------------------------------------------------------
def send_email_via_smtp(to_email: str, subject: str, html_content: str):
    if not settings.SMTP_HOST:
        logger.warning(f"⚠️ SMTP Host not configured. Email to {to_email} skipped.")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))

        # Connection Logic: Port 465 (SSL) vs 587 (STARTTLS)
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            if settings.SMTP_PORT == 587:
                server.starttls()

        with server:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            server.sendmail(
                settings.EMAILS_FROM_EMAIL,
                to_email,
                msg.as_string()
            )

        logger.info(f"✅ Email sent successfully to {to_email}")

    except Exception as e:
        logger.error(f"❌ Failed to send email to {to_email}: {str(e)}")


# ---------------------------------------------------------
# ASYNC WRAPPER (Non-Blocking for FastAPI)
# ---------------------------------------------------------
async def send_email_async(to_email: str, subject: str, html_content: str):
    """
    Offloads the blocking SMTP call to a separate thread so the API remains fast.
    """
    try:
        loop = asyncio.get_running_loop()
        task = partial(send_email_via_smtp, to_email, subject, html_content)
        await loop.run_in_executor(None, task)
    except Exception as e:
        logger.error(f"⚠️ Async Email Task Error: {str(e)}")


# ---------------------------------------------------------
# 1. WELCOME EMAIL
# ---------------------------------------------------------
async def send_welcome_email(student_data: dict):
    template = get_template('student_welcome.html')

    context = {
        "name": student_data.get("full_name"),
        "enrollment_number": student_data.get("enrollment_number"),
        "roll_number": student_data.get("roll_number"),
        "email": student_data.get("email"),
        "login_url": f"{settings.FRONTEND_URL}/login"
    }

    html_content = template.render(context)

    await send_email_async(
        student_data.get("email"),
        "Welcome to GBU No Dues Portal",
        html_content
    )


# ---------------------------------------------------------
# 2. APPLICATION REJECTED EMAIL
# ---------------------------------------------------------
async def send_application_rejected_email(data: dict):
    template = get_template('application_rejected.html')

    context = {
        "name": data.get("name"),
        "department_name": data.get("department_name"),
        "remarks": data.get("remarks"),
        "rejection_date": datetime.now().strftime("%d-%m-%Y"),
        "login_url": f"{settings.FRONTEND_URL}/login"
    }

    html_content = template.render(context)

    await send_email_async(
        data.get("email"),
        "Action Required: No Dues Application Returned",
        html_content
    )


# ---------------------------------------------------------
# 3. APPLICATION APPROVED EMAIL
# ---------------------------------------------------------
async def send_application_approved_email(data: dict):
    template = get_template('application_approved.html')

    context = {
        "name": data.get("name"),
        "roll_number": data.get("roll_number"),
        "enrollment_number": data.get("enrollment_number"),
        "display_id": data.get("display_id"),
        "application_id": str(data.get("application_id")),
        "completion_date": datetime.now().strftime("%d-%m-%Y"),
        "certificate_url": (
            f"{settings.FRONTEND_URL}/certificate/download/"
            f"{data.get('application_id')}"
        )
    }

    html_content = template.render(context)

    await send_email_async(
        data.get("email"),
        "🎉 No Dues Application Approved",
        html_content
    )


# ---------------------------------------------------------
# 4. APPLICATION SUBMITTED EMAIL
# ---------------------------------------------------------
async def send_application_created_email(data: dict):
    """
    data requires:
    - name
    - email
    - application_id
    - display_id
    """
    template = get_template('application_created.html')

    context = {
        "name": data.get("name"),
        "display_id": data.get("display_id") or str(data.get("application_id")),
        "application_id": str(data.get("application_id")),
        "submission_date": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
        "track_url": f"{settings.FRONTEND_URL}/dashboard"
    }

    html_content = template.render(context)

    await send_email_async(
        data.get("email"),
        "Application Submitted Successfully - GBU No Dues",
        html_content
    )


# ---------------------------------------------------------
# 5. PASSWORD RESET OTP EMAIL
# ---------------------------------------------------------
async def send_reset_password_email(data: dict):
    """
    data = {
        "email": "...",
        "name": "...",
        "otp": "123456"
    }
    """
    template = get_template('password_reset.html')

    context = {
        "name": data.get("name", "User"),
        "otp": data.get("otp"),
        "expiry_minutes": 15,
        "support_email": settings.EMAILS_FROM_EMAIL
    }

    html_content = template.render(context)

    await send_email_async(
        data.get("email"),
        "Password Reset OTP - GBU No Dues",
        html_content
    )


# ---------------------------------------------------------
# 6. PENDING REMINDER EMAIL (For Verifiers)
# ---------------------------------------------------------
async def send_pending_reminder_email(
    verifier_name: str,
    verifier_email: str,
    pending_count: int,
    department_name: str
):
    """
    Sends a reminder to a Department/Verifier about overdue applications.
    Uses 'pending_reminder.html' template.
    """
    template = get_template('pending_reminder.html')

    context = {
        "verifier_name": verifier_name,
        "pending_count": pending_count,
        "department_name": department_name,
        "dashboard_url": f"{settings.FRONTEND_URL}/login"
    }

    html_content = template.render(context)

    await send_email_async(
        verifier_email,
        f"⚠️ Action Required: {pending_count} Pending Applications",
        html_content
    )