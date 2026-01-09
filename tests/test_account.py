import pytest
import random
import string

# ----------------------------------------------------------------
# HELPER: Generate Random Data to prevent DB constraints
# ----------------------------------------------------------------
def random_str(prefix="", length=6):
    chars = string.ascii_lowercase + string.digits
    return f"{prefix}{''.join(random.choices(chars, k=length))}"

# ----------------------------------------------------------------
# TEST 1: SUCCESSFUL PASSWORD CHANGE
# ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_change_password_success(client):
    """
    Test the full flow: Register -> Login -> Change Password -> Login with New.
    """
    # 1. Setup Unique User
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
    
    # 2. Register
    reg_res = await client.post("/api/students/register", json=student_payload)
    assert reg_res.status_code == 201

    # 3. Login (Get Token)
    login_res = await client.post("/api/students/login", json={
        "identifier": unique_roll, 
        "password": "oldpassword123"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Change Password
    change_payload = {
        "old_password": "oldpassword123",
        "new_password": "newpassword456"
    }
    res = await client.post("/api/account/change-password", json=change_payload, headers=headers)
    
    # Assert Success Response
    assert res.status_code == 200
    assert res.json()["detail"] == "Password changed successfully"

    # 5. Verify: Login with OLD password should FAIL
    res_fail = await client.post("/api/students/login", json={
        "identifier": unique_roll, 
        "password": "oldpassword123"
    })
    assert res_fail.status_code == 401

    # 6. Verify: Login with NEW password should SUCCEED
    res_success = await client.post("/api/students/login", json={
        "identifier": unique_roll, 
        "password": "newpassword456"
    })
    assert res_success.status_code == 200


# ----------------------------------------------------------------
# TEST 2: FAIL IF OLD PASSWORD IS WRONG
# ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_change_password_invalid_old(client):
    """
    Ensure the system blocks requests where 'old_password' is incorrect.
    """
    # 1. Setup Unique User
    unique_roll = random_str("ROLL_FAIL")
    unique_email = f"{unique_roll}@test.com"

    student_payload = {
        "enrollment_number": random_str("ENR"),
        "roll_number": unique_roll,
        "full_name": "Bad Actor",
        "mobile_number": "9999999999",
        "email": unique_email,
        "password": "securepassword",
        "confirm_password": "securepassword"
    }
    
    # 2. Register & Login
    await client.post("/api/students/register", json=student_payload)
    login_res = await client.post("/api/students/login", json={
        "identifier": unique_roll, 
        "password": "securepassword"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Attempt Change with WRONG old password
    change_payload = {
        "old_password": "WRONG_PASSWORD", 
        "new_password": "hackedpassword"
    }
    res = await client.post("/api/account/change-password", json=change_payload, headers=headers)
    
    # 4. Assert Failure
    assert res.status_code == 400
    assert "Incorrect old password" in res.json()["detail"]

    # 5. Verify Original Password still works
    res_verify = await client.post("/api/students/login", json={
        "identifier": unique_roll, 
        "password": "securepassword"
    })
    assert res_verify.status_code == 200