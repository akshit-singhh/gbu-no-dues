import pytest
import random
import string

def random_str(prefix=""):
    return f"{prefix}{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"

@pytest.mark.asyncio
async def test_change_password(client):
    # Unique user data to avoid DB conflicts
    unique_roll = random_str("ROLL")
    unique_email = f"{unique_roll}@test.com"

    student_payload = {
        "enrollment_number": random_str("ENR"),
        "roll_number": unique_roll,
        "full_name": "Pwd Changer",
        "mobile_number": "1231231234",
        "email": unique_email,
        "password": "oldpassword123",
        "confirm_password": "oldpassword123"
    }
    
    # 1. Register
    reg_res = await client.post("/api/students/register", json=student_payload)
    assert reg_res.status_code == 201

    # 2. Login
    login_res = await client.post("/api/students/login", json={"identifier": unique_roll, "password": "oldpassword123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Change Password
    change_payload = {
        "old_password": "oldpassword123",
        "new_password": "newpassword456"
    }
    res = await client.post("/api/account/change-password", json=change_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["detail"] == "Password changed successfully"

    # 4. Verify Old Password Fails
    res_fail = await client.post("/api/students/login", json={"identifier": unique_roll, "password": "oldpassword123"})
    assert res_fail.status_code == 401

    # 5. Verify New Password Works
    res_success = await client.post("/api/students/login", json={"identifier": unique_roll, "password": "newpassword456"})
    assert res_success.status_code == 200