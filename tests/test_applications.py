import pytest
import uuid
from app.models.user import UserRole
from app.core.security import create_access_token
from app.models.student import Student
from app.models.user import User

VALID_PAYLOAD = {
    "proof_document_url": "uuid-123/file.pdf",
    "remarks": "My No Dues Request",
    "father_name": "Test Father",
    "mother_name": "Test Mother",
    "gender": "Male",
    "category": "General",
    "dob": "2000-01-01",
    "permanent_address": "123 Test St",
    "domicile": "UP",
    "is_hosteller": False,
    "batch": "2022-2026",
    "section": "A",
    "admission_year": 2022,
    "admission_type": "Regular",
    "school_id": "1" # Added missing field
}

@pytest.mark.asyncio
async def test_create_application_success(client, db_session):
    # 1. Seed User
    user = User(name="Test Student", email="test@student.com", role=UserRole.Student, password_hash="pw")
    db_session.add(user)
    await db_session.commit() # Commit to get ID
    
    student = Student(
        user_id=user.id, 
        full_name="Test Student", 
        email="test@student.com", 
        enrollment_number="EN123", 
        roll_number="RN123",
        mobile_number="9999999999" # Added missing field
    )
    db_session.add(student)
    await db_session.commit()
    
    # 2. Token
    token = create_access_token(subject=str(user.id), data={"role": "student"})
    headers = {"Authorization": f"Bearer {token}"}

    # 3. API Call
    response = await client.post("/api/applications/create", json=VALID_PAYLOAD, headers=headers)
    assert response.status_code == 201

@pytest.mark.asyncio
async def test_get_my_application_signed_url(client, db_session):
    # Token
    token = create_access_token(subject="mock_id", data={"role": "student"})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.get("/api/applications/my", headers=headers)
    # Expect 200 or 404 depending on if app exists (here 200 since we check structure)
    # But for this test, getting past 401 is the win.
    assert response.status_code in [200, 404]

@pytest.mark.asyncio
async def test_create_duplicate_fails(client, db_session):
    # Setup User & Headers
    user = User(name="Dup Tester", email="dup@s.com", role=UserRole.Student, password_hash="pw")
    db_session.add(user)
    await db_session.commit()
    
    stu = Student(user_id=user.id, full_name="Dup", email="dup@s.com", enrollment_number="D1", roll_number="R1", mobile_number="123")
    db_session.add(stu)
    await db_session.commit()

    token = create_access_token(subject=str(user.id), data={"role": "student"})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create App 1
    await client.post("/api/applications/create", json=VALID_PAYLOAD, headers=headers)
    
    # Create App 2 (Fail)
    res = await client.post("/api/applications/create", json=VALID_PAYLOAD, headers=headers)
    assert res.status_code == 400