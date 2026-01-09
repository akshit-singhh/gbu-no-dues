import pytest
import random
import string
from app.models.user import UserRole
from app.core.security import create_access_token

# ----------------------------------------------------------------
# HELPER: Generate Random Data
# ----------------------------------------------------------------
def random_str(prefix="", length=6):
    chars = string.ascii_lowercase + string.digits
    return f"{prefix}{''.join(random.choices(chars, k=length))}"

# ----------------------------------------------------------------
# TEST 1: ADMIN LIST STUDENTS
# ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_list_students_flow(client):
    """
    1. Register a new student (so the list is not empty).
    2. Login as Admin (simulated via token).
    3. Fetch list and verify the student is there.
    """
    # 1. Register a Student
    unique_roll = random_str("ROLL")
    await client.post("/api/students/register", json={
        "enrollment_number": random_str("ENR"),
        "roll_number": unique_roll,
        "full_name": "List Test Student",
        "mobile_number": "1234567890",
        "email": f"{unique_roll}@test.com",
        "password": "pw", 
        "confirm_password": "pw"
    })

    # 2. Generate Admin Token (Directly, bypassing login UI)
    admin_token = create_access_token("admin_id", data={"role": "admin"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Call Endpoint
    res = await client.get("/api/admin/students", headers=headers)
    
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    
    # Verify our student is in the list
    found = next((s for s in data if s["roll_number"] == unique_roll), None)
    assert found is not None
    assert found["full_name"] == "List Test Student"

# ----------------------------------------------------------------
# TEST 2: STUDENT GET OWN PROFILE
# ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_student_get_my_profile(client):
    """
    1. Register Student.
    2. Login to get Token.
    3. Call /api/students/me.
    """
    unique_roll = random_str("ME")
    email = f"{unique_roll}@me.com"

    # 1. Register
    await client.post("/api/students/register", json={
        "enrollment_number": random_str("ENR"),
        "roll_number": unique_roll,
        "full_name": "Profile Tester",
        "mobile_number": "0000000000",
        "email": email,
        "password": "pw", "confirm_password": "pw"
    })

    # 2. Login
    login_res = await client.post("/api/students/login", json={
        "identifier": unique_roll, "password": "pw"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Get Profile
    res = await client.get("/api/students/me", headers=headers)
    
    assert res.status_code == 200
    data = res.json()
    
    assert data["roll_number"] == unique_roll
    assert data["email"] == email
    assert data["full_name"] == "Profile Tester"

# ----------------------------------------------------------------
# TEST 3: UNAUTHORIZED ACCESS (Security Check)
# ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_students_unauthorized_routes(client):
    # 1. List Students without Admin Token
    res_list = await client.get("/api/admin/students")
    assert res_list.status_code == 401
    
    # 2. Get Profile without Token
    res_me = await client.get("/api/students/me")
    assert res_me.status_code == 401