import pytest
import uuid
from datetime import datetime

from app.models.user import User, UserRole
from app.models.student import Student
from app.models.school import School
from app.models.application import Application, ApplicationStatus
from app.models.application_stage import ApplicationStage
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_dean_approval_moves_to_next_stage(client, db_session):
    """
    Test that when Dean approves, the application moves from Order 1 to Order 2.
    """
    
    # ----------------------------------------------------------------
    # 1. SETUP: Seed Database with Linked Entities
    # ----------------------------------------------------------------
    
    # A. Create School
    school = School(name="School of Testing", dean_name="Dr. Test Dean")
    db_session.add(school)
    await db_session.commit()
    await db_session.refresh(school)

    # B. Create Student User & Profile
    student_user = User(
        email="workflow_student@uni.edu",
        name="Workflow Student",
        role=UserRole.Student,
        password_hash="hashed_pw", # Ensures DB constraint is met
        is_active=True
    )
    db_session.add(student_user)
    await db_session.commit()

    student_profile = Student(
        user_id=student_user.id,
        full_name="Workflow Student",
        email="workflow_student@uni.edu",
        enrollment_number="WORK100",
        roll_number="ROLL_WORK",
        school_id=school.id, # ✅ Linked to School
        mobile_number="9999999999"
    )
    db_session.add(student_profile)
    await db_session.commit()

    # C. Create Dean User
    dean_user = User(
        email="workflow_dean@uni.edu",
        name="Dean User",
        role=UserRole.Dean,
        password_hash="hashed_pw",
        school_id=school.id, # ✅ Linked to Same School
        is_active=True
    )
    db_session.add(dean_user)
    await db_session.commit()

    # D. Create Application (Currently at Stage 1)
    app = Application(
        student_id=student_profile.id,
        status=ApplicationStatus.PENDING.value,
        current_stage_order=1,
        proof_document_url="uuid/proof.pdf",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(app)
    await db_session.commit()

    # E. Create Stages (Dean + Next Step)
    # Stage 1: Dean (Current)
    stage_dean = ApplicationStage(
        application_id=app.id,
        verifier_role=UserRole.Dean.value,
        sequence_order=1,
        status=ApplicationStatus.PENDING.value,
        school_id=school.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(stage_dean)

    # Stage 2: Library (Next Step - Required to verify transition)
    stage_lib = ApplicationStage(
        application_id=app.id,
        verifier_role=UserRole.Library.value,
        sequence_order=2, # Next Order
        status=ApplicationStatus.PENDING.value,
        department_id=1, # Mock ID
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(stage_lib)
    await db_session.commit()

    # ----------------------------------------------------------------
    # 2. ACTION: Dean Approves
    # ----------------------------------------------------------------

    # Generate Dean Token
    dean_token = create_access_token(
        subject=str(dean_user.id),
        data={"role": "dean", "school_id": str(school.id)}
    )
    dean_headers = {"Authorization": f"Bearer {dean_token}"}

    # Fetch Pending List
    res = await client.get("/api/approvals/pending", headers=dean_headers)
    assert res.status_code == 200
    
    # Extract the Stage ID for this specific app
    pending_list = res.json()
    target_item = next((i for i in pending_list if i["application_id"] == str(app.id)), None)
    assert target_item is not None, "Dean could not see the application"
    
    stage_id = target_item["active_stage"]["stage_id"]

    # Approve
    approve_res = await client.post(f"/api/approvals/{stage_id}/approve", headers=dean_headers)
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # ----------------------------------------------------------------
    # 3. VERIFY: Check Application State
    # ----------------------------------------------------------------
    
    # Login as Student to check status
    student_token = create_access_token(
        subject=str(student_user.id),
        data={"role": "student"}
    )
    student_headers = {"Authorization": f"Bearer {student_token}"}

    status_res = await client.get("/api/applications/my", headers=student_headers)
    assert status_res.status_code == 200
    
    app_data = status_res.json()["application"]
    
    # ✅ Assertion: Stage should increment to 2
    assert app_data["current_stage_order"] == 2
    
    # ✅ Assertion: Status should change to 'in_progress' (since it started as pending)
    assert app_data["status"] == "in_progress"