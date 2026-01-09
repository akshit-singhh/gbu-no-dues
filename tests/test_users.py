import pytest
from app.models.user import UserRole
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_admin_create_user(client):
    admin_token = create_access_token(subject="admin_id", data={"role": "admin"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    payload = {
        "name": "Test Staff",
        "email": "staff_new@test.com",
        "password": "pw",
        "role": "staff",
        "is_active": True
    }
    res = await client.post("/api/users/", json=payload, headers=headers)
    assert res.status_code == 201

@pytest.mark.asyncio
async def test_admin_list_users(client):
    admin_token = create_access_token(subject="admin_id", data={"role": "admin"})
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    res = await client.get("/api/users/", headers=headers)
    assert res.status_code == 200