import pytest

@pytest.mark.asyncio
async def test_admin_login_route_exists(client):
    payload = {"email": "admin@example.com", "password": "adminpass"}
    res = await client.post("/api/admin/login", json=payload)
    assert res.status_code in (200, 401)
