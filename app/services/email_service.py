import smtplib
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
from app.core.config import settings

# Helper to get template
def get_template(template_name):
    template_dir = os.path.join(os.getcwd(), 'app', 'templates', 'email')
    env = Environment(loader=FileSystemLoader(template_dir))
    return env.get_template(template_name)

# Helper to send email via SMTP
def send_email_via_smtp(to_email, subject, html_content):
    # CHANGED: Only require HOST. User/Pass are now optional (for Mailpit)
    if not settings.SMTP_HOST:
        print("⚠️ SMTP Host not configured. Skipping email.")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))

        print(f"📧 Connecting to SMTP: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            
            # Logic: Use TLS only if it's a production-like port (587/2525)
            # Mailpit runs on 1025 and usually doesn't need TLS locally
            if settings.SMTP_PORT in [587, 2525]:
                server.starttls()
                server.ehlo()
            
            # CHANGED: Only login if credentials are provided in .env
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())

        print(f"✅ Email sent successfully to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")


# ---------------------------------------------------------
# 1. WELCOME EMAIL
# ---------------------------------------------------------
def send_welcome_email(student_data: dict):
    try:
        template = get_template('student_welcome.html')
        context = {
            "name": student_data.get("full_name"),
            "enrollment_number": student_data.get("enrollment_number"),
            "roll_number": student_data.get("roll_number"),
            "email": student_data.get("email"),
            "login_url": f"{settings.FRONTEND_URL}/login"
        }
        html_content = template.render(context)
        send_email_via_smtp(student_data.get("email"), "Welcome to GBU No Dues Portal", html_content)
    except Exception as e:
        print(f"Error preparing welcome email: {e}")


# ---------------------------------------------------------
# 2. REJECTION EMAIL
# ---------------------------------------------------------
def send_application_rejected_email(data: dict):
    try:
        template = get_template('application_rejected.html')
        context = {
            "name": data.get("name"),
            "department_name": data.get("department_name"),
            "remarks": data.get("remarks"),
            "rejection_date": datetime.now().strftime("%d-%m-%Y"),
            "login_url": f"{settings.FRONTEND_URL}/login"
        }
        html_content = template.render(context)
        send_email_via_smtp(data.get("email"), "Action Required: No Dues Application Returned", html_content)
    except Exception as e:
        print(f"Error preparing rejection email: {e}")


# ---------------------------------------------------------
# 3. APPROVAL / COMPLETION EMAIL
# ---------------------------------------------------------
def send_application_approved_email(data: dict):
    try:
        template = get_template('application_approved.html')
        context = {
            "name": data.get("name"),
            "roll_number": data.get("roll_number"),
            "enrollment_number": data.get("enrollment_number"),
            "application_id": str(data.get("application_id")),
            "completion_date": datetime.now().strftime("%d-%m-%Y"),
            "certificate_url": f"{settings.FRONTEND_URL}/certificate/download/{data.get('application_id')}" 
        }
        html_content = template.render(context)
        send_email_via_smtp(data.get("email"), "🎉 No Dues Application Approved", html_content)
    except Exception as e:
        print(f"Error preparing approval email: {e}")
        
# ---------------------------------------------------------
# 4. APPLICATION SUBMITTED EMAIL (NEW)
# ---------------------------------------------------------
def send_application_created_email(data: dict):
    """
    data requires: name, email, application_id
    """
    try:
        template = get_template('application_created.html')
        context = {
            "name": data.get("name"),
            "application_id": str(data.get("application_id")),
            "submission_date": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
            "track_url": f"{settings.FRONTEND_URL}/dashboard"  # Redirect to dashboard to see status
        }
        html_content = template.render(context)
        send_email_via_smtp(data.get("email"), "Application Submitted Successfully - GBU No Dues", html_content)
    except Exception as e:
        print(f"Error preparing submission email: {e}")