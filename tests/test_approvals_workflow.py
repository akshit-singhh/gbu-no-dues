import pytest
import uuid
import random
import string
from sqlmodel import select
from app.models.application_stage import ApplicationStage
from app.models.department import Department
from app.core.database import AsyncSessionLocal

def random_str(prefix=""):
    return f"{prefix}{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"

@pytest.mark.asyncio
async def test_full_application_lifecycle(client):
    # Unique data
    unique_roll = random_str("FLOW")
    unique_email = f"{unique_roll}@test.com"

    # --- 1. Student Setup ---
    s_payload = {
        "enrollment_number": random_str("ENR"),
        "roll_number": unique_roll,
        "full_name": "Lifecycle Student",
        "mobile_number": "9999999999",
        "email": unique_email,
        "password": "pass",
        "confirm_password": "pass"
    }
    # Register
    reg_res = await client.post("/api/students/register", json=s_payload)
    assert reg_res.status_code == 201
    
    # Login
    login_res = await client.post("/api/students/login", json={"identifier": unique_roll, "password": "pass"})
    s_token = login_res.json()["access_token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}

    # --- 2. Create Application ---
    create_res = await client.post(
        "/api/applications/create", 
        json={"student_update": {"father_name": "Test Father"}},
        headers=s_headers
    )
    assert create_res.status_code == 201
    app_id = create_res.json()["id"]

    # --- 3. Stage Verification / Injection ---
    stages_to_approve = []
    
    async with AsyncSessionLocal() as session:
        # Check if stages exist
        stages_res = await session.execute(select(ApplicationStage).where(ApplicationStage.application_id == app_id))
        stages = stages_res.scalars().all()
        
        if not stages:
            print("⚠️ No stages found. Injecting manual stage.")
            dept_res = await session.execute(select(Department).limit(1))
            dept = dept_res.scalar_one_or_none()
            if not dept:
                dept = Department(name=f"Dept_{random_str()}", sequence_order=1)
                session.add(dept)
                await session.commit()
                await session.refresh(dept)
            
            new_stage = ApplicationStage(
                application_id=uuid.UUID(app_id),
                department_id=dept.id,
                status="Pending",
                sequence_order=1
            )
            session.add(new_stage)
            await session.commit()
            await session.refresh(new_stage)
            stages_to_approve.append(str(new_stage.id))
        else:
            print(f" Found {len(stages)} existing stages.")
            for stage in stages:
                stages_to_approve.append(str(stage.id))

    # --- 4. Admin Login ---
    # Register a temporary admin for this test run
    admin_email = f"admin_{unique_roll}@test.com"
    async with AsyncSessionLocal() as session:
        from app.services.auth_service import create_user
        from app.models.user import UserRole
        await create_user(
            session, "Test Admin", admin_email, "adminpass", UserRole.Admin
        )

    admin_login = await client.post("/api/admin/login", json={"email": admin_email, "password": "adminpass"})
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # --- 5. Approve ALL Stages ---
    for stage_id in stages_to_approve:
        approve_res = await client.post(
            f"/api/approvals/{stage_id}/approve",
            headers=admin_headers
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "Approved"

    # --- 6. Verify Global Status ---
    app_details = await client.get("/api/applications/my", headers=s_headers)
    data = app_details.json()
    
    print(f"DEBUG Final App Status: {data['application']['status']}")
    
    assert data["application"]["status"] == "Completed"
    assert data["flags"]["is_completed"] == True