import pytest
import random
import string

def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters, k=length))

def random_number(length=10):
    return ''.join(random.choices(string.digits, k=length))

@pytest.mark.asyncio
async def test_student_register(client):
    # Generate random data to avoid "User already exists" (400) errors
    enrollment = random_number(10)
    email = f"test.{random_string(5)}@example.com"
    
    payload = {
        "enrollment_number": enrollment,
        "roll_number": f"ROLL{random_number(5)}",
        "full_name": "Test Student",
        "mobile_number": random_number(10),
        "email": email,
        "password": "password123",
        "confirm_password": "password123"
    }

    res = await client.post("/api/students/register", json=payload)
    
    # Debugging: print response if it fails
    if res.status_code not in (200, 201):
        print(f"Registration failed: {res.json()}")

    assert res.status_code in (200, 201)
    data = res.json()
    assert "id" in data or "enrollment_number" in data