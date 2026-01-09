import pytest
from unittest.mock import patch, MagicMock
import email

# Import the actual service functions
from app.services.email_service import (
    send_welcome_email, 
    send_application_created_email,
    send_application_approved_email, 
    send_application_rejected_email
)

# ----------------------------------------------------------------
# HELPER: DECODE EMAIL CONTENT
# ----------------------------------------------------------------
def get_email_subject(mock_smtp_instance):
    """
    Helper to extract the Subject from the mocked sendmail call.
    smtplib.sendmail(from, to, msg_string) -> We parse msg_string.
    """
    call_args = mock_smtp_instance.sendmail.call_args
    if not call_args:
        return None
    
    # Arg [2] is the message string
    msg_str = call_args[0][2] 
    msg = email.message_from_string(msg_str)
    return msg['Subject']

# ----------------------------------------------------------------
# TEST 1: WELCOME EMAIL (Registration)
# ----------------------------------------------------------------
@patch("app.services.email_service.settings") # Mock settings to avoid ENV errors
@patch("app.services.email_service.smtplib.SMTP")
def test_send_welcome_email(mock_smtp, mock_settings):
    # Setup Mock
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    # Dummy Config
    mock_settings.EMAILS_ENABLED = True
    mock_settings.SMTP_USER = "admin@college.edu"

    student_data = {
        "full_name": "New Student",
        "enrollment_number": "EN123",
        "roll_number": "R123",
        "email": "student@test.com"
    }

    # Run Function
    send_welcome_email(student_data)

    # Verify Logic
    mock_smtp.assert_called() # Connection made
    mock_server.login.assert_called() # Logged in
    
    # Verify Recipient
    call_args = mock_server.sendmail.call_args
    recipient = call_args[0][1]
    assert recipient == "student@test.com"
    
    # Verify Content
    subject = get_email_subject(mock_server)
    assert "Welcome" in subject


# ----------------------------------------------------------------
# TEST 2: APPLICATION CREATED (Submission Confirmation)
# ----------------------------------------------------------------
@patch("app.services.email_service.settings")
@patch("app.services.email_service.smtplib.SMTP")
def test_send_application_created_email(mock_smtp, mock_settings):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    mock_settings.EMAILS_ENABLED = True

    data = {
        "name": "Submitter One",
        "email": "submit@test.com",
        "application_id": "uuid-123-456"
    }

    send_application_created_email(data)

    # Verify Recipient
    recipient = mock_server.sendmail.call_args[0][1]
    assert recipient == "submit@test.com"

    # Verify Subject (ensures correct template used)
    subject = get_email_subject(mock_server)
    assert "Received" in subject or "Submitted" in subject


# ----------------------------------------------------------------
# TEST 3: APPROVAL EMAIL
# ----------------------------------------------------------------
@patch("app.services.email_service.settings")
@patch("app.services.email_service.smtplib.SMTP")
def test_send_approval_email(mock_smtp, mock_settings):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    mock_settings.EMAILS_ENABLED = True

    data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "roll_number": "R999",
        "enrollment_number": "E999",
        "application_id": "some-uuid"
    }

    send_application_approved_email(data)

    # Verify
    recipient = mock_server.sendmail.call_args[0][1]
    assert recipient == "jane@example.com"
    
    subject = get_email_subject(mock_server)
    assert "Approved" in subject or "Certificate" in subject


# ----------------------------------------------------------------
# TEST 4: REJECTION EMAIL
# ----------------------------------------------------------------
@patch("app.services.email_service.settings")
@patch("app.services.email_service.smtplib.SMTP")
def test_send_rejection_email(mock_smtp, mock_settings):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    mock_settings.EMAILS_ENABLED = True

    data = {
        "name": "John Smith",
        "email": "john@example.com",
        "department_name": "Library",
        "remarks": "Book not returned"
    }

    send_application_rejected_email(data)
    
    # Verify
    recipient = mock_server.sendmail.call_args[0][1]
    assert recipient == "john@example.com"
    
    # Verify Content contains crucial info
    msg_str = mock_server.sendmail.call_args[0][2]
    assert "Library" in msg_str # Ensure department is mentioned
    assert "Book not returned" in msg_str # Ensure remark is mentioned
    
    subject = get_email_subject(mock_server)
    assert "Action Required" in subject or "Rejected" in subject