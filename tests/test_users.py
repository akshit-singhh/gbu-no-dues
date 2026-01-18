import pytest
from app.models.user import User, UserRole
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_admin_create_user(client, db_session):
    # 1. Create REAL Admin User
    admin = User(name="Admin", email="admin@create.com", role=UserRole.Admin, password_hash="pw")
    db_session.add(admin)
    await db_session.commit()

    # 2. Generate Token for THIS admin
    admin_token = create_access_token(subject=str(admin.id), data={"role": "admin"})
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
async def test_admin_list_users(client, db_session):
    # 1. Create REAL Admin User
    admin = User(name="Admin List", email="admin@list.com", role=UserRole.Admin, password_hash="pw")
    db_session.add(admin)
    await db_session.commit()

    # 2. Generate Token
    admin_token = create_access_token(subject=str(admin.id), data={"role": "admin"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = await client.get("/api/users/", headers=headers)
    assert res.status_code == 200