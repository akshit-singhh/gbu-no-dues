import pytest
import uuid
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.student import Student # Check import
from app.core.security import create_access_token

def random_str(prefix="", length=6):
    import random, string
    chars = string.ascii_lowercase + string.digits
    return f"{prefix}{''.join(random.choices(chars, k=length))}"

@pytest.mark.asyncio
async def test_department_staff_can_view_pending(client, db_session):
    # 1. Department
    library_dept = Department(name="Library", phase_number=2)
    db_session.add(library_dept)
    await db_session.commit()
    await db_session.refresh(library_dept)

    # 2. Staff User
    staff_user = User(
        email=f"lib_{random_str()}@uni.edu",
        name="Librarian",
        role=UserRole.Staff,
        department_id=library_dept.id,
        # ✅ FIX: Use password_hash
        password_hash="hashed_pw", 
        is_active=True
    )
    db_session.add(staff_user)
    
    # 3. Student User
    student_user = User(
        email=f"stu_{random_str()}@s.com", 
        name="Student", # ✅ FIX: Missing name caused IntegrityError
        role=UserRole.Student, 
        password_hash="pw" # ✅ FIX
    )
    db_session.add(student_user)
    await db_session.commit() # Get IDs
    
    # ✅ FIX: create_access_token args
    token = create_access_token(str(staff_user.id), data={"role": "staff"})
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/api/approvals/pending", headers=headers)
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_student_cannot_access_department_actions(client):
    # ✅ FIX: create_access_token args
    student_token = create_access_token("stu_id", data={"role": "student"})
    headers = {"Authorization": f"Bearer {student_token}"}
    
    res = await client.post(f"/api/approvals/{uuid.uuid4()}/approve", headers=headers)
    assert res.status_code == 403