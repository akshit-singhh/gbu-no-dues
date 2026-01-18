import pytest
import uuid
from app.models.user import User, UserRole
from app.models.school import School
from app.core.security import create_access_token

def random_str(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:6]}"

@pytest.mark.asyncio
async def test_admin_list_students_flow(client, db_session):
    # 0. Setup School
    school = School(name="List School", dean_name="Dean")
    db_session.add(school)
    
    # 1. Setup Admin User
    admin = User(name="Admin", email="admin@list.com", role=UserRole.Admin, password_hash="pw")
    db_session.add(admin)
    await db_session.commit()

    # 2. Register a Student (Needs valid School ID)
    unique_roll = random_str("ROLL")
    await client.post("/api/students/register", json={
        "enrollment_number": random_str("ENR"),
        "roll_number": unique_roll,
        "full_name": "List Test Student",
        "mobile_number": "1234567890",
        "email": f"{unique_roll}@test.com",
        "password": "pw",
        "confirm_password": "pw",
        "school_id": school.id # ✅ Added
    })

    # 3. Use Admin Token
    admin_token = create_access_token(subject=str(admin.id), data={"role": "admin"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 4. Call Endpoint
    res = await client.get("/api/admin/students", headers=headers)
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_student_get_my_profile(client, db_session):
    # 0. Setup School
    school = School(name="Profile School", dean_name="Dean")
    db_session.add(school)
    await db_session.commit()

    unique_roll = random_str("ME")
    email = f"{unique_roll}@me.com"

    # 1. Register with School ID
    reg_res = await client.post("/api/students/register", json={
        "enrollment_number": random_str("ENR"),
        "roll_number": unique_roll,
        "full_name": "Profile Tester",
        "mobile_number": "0000000000",
        "email": email,
        "password": "pw", "confirm_password": "pw",
        "school_id": school.id # ✅ Added
    })
    assert reg_res.status_code == 201 # Ensure registration worked

    # 2. Login
    login_res = await client.post("/api/students/login", json={
        "identifier": unique_roll, "password": "pw"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    
    # 3. Get Profile
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.get("/api/students/me", headers=headers)
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_students_unauthorized_routes(client):
    res_list = await client.get("/api/admin/students")
    assert res_list.status_code == 403 # Expect 403