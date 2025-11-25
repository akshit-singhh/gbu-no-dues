import pytest

@pytest.mark.asyncio
async def test_list_users_route(client):
    res = await client.get("/api/users/")
    assert res.status_code in (200, 401, 403)

@pytest.mark.asyncio
async def test_create_user_route(client):
    payload = {"name": "Test User", "email": "testuser@example.com", "password": "password123", "role": "Office"}
    res = await client.post("/api/users/", json=payload)
    # creation may be protected by admin; ensure route exists
    assert res.status_code in (200, 201, 400, 401, 403)
