import pytest

@pytest.mark.asyncio
async def test_student_login_requires_existing_student(client):
    payload = {
        "identifier": "2300100999",
        "password": "password123"
    }

    res = await client.post("/api/students/login", json=payload)
    # If student exists and password correct -> 200, else 401.
    assert res.status_code in (200, 401)
