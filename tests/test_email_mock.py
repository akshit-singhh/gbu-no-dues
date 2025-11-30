import pytest
from unittest.mock import patch, MagicMock
from app.services.email_service import send_welcome_email, send_application_approved_email, send_application_rejected_email

@patch("app.services.email_service.smtplib.SMTP")
def test_send_welcome_email(mock_smtp):
    # Setup mock
    mock_server_instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server_instance
    
    student_data = {
        "full_name": "Test Student",
        "enrollment_number": "123456",
        "roll_number": "ROLL123",
        "email": "test@example.com"
    }

    # Run
    send_welcome_email(student_data)

    # Verify connection was made and email sent
    mock_smtp.assert_called()
    mock_server_instance.login.assert_called()
    mock_server_instance.sendmail.assert_called()
    
    # Check recipient (safest check without decoding base64)
    call_args = mock_server_instance.sendmail.call_args
    recipient = call_args[0][1]
    assert recipient == "test@example.com"

@patch("app.services.email_service.smtplib.SMTP")
def test_send_approval_email(mock_smtp):
    mock_server_instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server_instance

    data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "roll_number": "R999",
        "enrollment_number": "E999",
        "application_id": "some-uuid"
    }

    send_application_approved_email(data)

    # Verify
    mock_server_instance.sendmail.assert_called()
    recipient = mock_server_instance.sendmail.call_args[0][1]
    assert recipient == "jane@example.com"

@patch("app.services.email_service.smtplib.SMTP")
def test_send_rejection_email(mock_smtp):
    mock_server_instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server_instance

    data = {
        "name": "John Smith",
        "email": "john@example.com",
        "department_name": "Library",
        "remarks": "Book not returned"
    }

    send_application_rejected_email(data)
    
    # Verify
    mock_server_instance.sendmail.assert_called()
    recipient = mock_server_instance.sendmail.call_args[0][1]
    assert recipient == "john@example.com"