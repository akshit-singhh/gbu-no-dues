import pytest
from httpx import AsyncClient

# helper to create student
async def create_test_student(client, enrollment="2300107777", email="application.test@example.com"):
    student_payload = {
        "enrollment_number": enrollment,
        "roll_number": "235ICS777",
        "full_name": "Application Test Student",
        "mobile_number": "9876543210",
        "email": email,
        "password": "testpassword123",
        "confirm_password": "testpassword123"
    }
    res = await client.post("/api/students/register", json=student_payload)
    assert res.status_code in (200, 201)
    return res.json()

@pytest.mark.asyncio
async def test_create_application_route_exists(client):
    # POST /api/applications/create should exist (Swagger)
    # Without auth it may return 401 or 403; just assert route exists
    res = await client.post("/api/applications/create", json={})
    # Add 403 to the allowed status codes
    assert res.status_code in (200, 201, 400, 401, 403)
@pytest.mark.asyncio
async def test_get_my_application_route_exists(client):
    res = await client.get("/api/applications/my")
    assert res.status_code in (200, 401, 403)

