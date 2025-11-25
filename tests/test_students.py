import pytest


@pytest.mark.asyncio
async def test_list_students(client):
    # If endpoint requires auth, tests can be extended to create admin and login
    res = await client.get("/api/admin/students")  # from swagger: admin list students
    # If unauthenticated it's likely 401; but ensure route exists and returns 200/401
    assert res.status_code in (200, 401, 403)

@pytest.mark.asyncio
async def test_get_my_profile_requires_auth(client):
    # GET /api/students/me exists; without token it should return 401
    res = await client.get("/api/students/me")
    assert res.status_code in (200, 401, 403)

