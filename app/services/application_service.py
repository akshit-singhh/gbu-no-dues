# app/services/application_service.py

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import uuid
from datetime import datetime
from typing import Optional

from app.models.application import Application, ApplicationStatus
from app.models.application_stage import ApplicationStage
from app.models.student import Student
from app.models.department import Department  # ✅ Import Department
from app.models.user import UserRole
from app.schemas.application import ApplicationCreate

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

# ✅ FIXED: Names now match your 'departments' table exactly
DEFAULT_STAGES = [
    # Dean is special (linked to School, not Department table)
    {"role": UserRole.Dean,     "order": 1, "name": "School Dean"}, 
    
    # Matches DB name "Library"
    {"role": UserRole.Library,  "order": 2, "name": "Library"},
    
    # Matches DB name "Hostel"
    {"role": UserRole.Hostel,   "order": 2, "name": "Hostel"},
    
    # Matches DB name "Sports"
    {"role": UserRole.Sports,   "order": 2, "name": "Sports"},
    
    # Matches DB name "Laboratories"
    {"role": UserRole.Lab,      "order": 2, "name": "Laboratories"},
    
    # Matches DB name "CRC"
    {"role": UserRole.CRC,      "order": 2, "name": "CRC"},
    
    # Matches DB name "Accounts"
    {"role": UserRole.Account,  "order": 3, "name": "Accounts"}
]

async def create_application_for_student(
    session: AsyncSession,
    student_id: str,
    payload: ApplicationCreate
) -> Application:

    # 1. Fetch Student & Departments (✅ NEW LOGIC)
    student_res = await session.execute(select(Student).where(Student.id == student_id))
    student = student_res.scalar_one_or_none()
    if not student:
        raise ValueError("Student not found")

    # ✅ Fetch all departments to create a lookup map
    # This creates a dictionary: { "library": 1, "hostel": 2, ... }
    dept_res = await session.execute(select(Department))
    all_depts = dept_res.scalars().all()
    
    # We use lowercase keys for safe matching
    dept_map = {d.name.lower(): d.id for d in all_depts}

    # 2. Check for existing active application
    existing_app_q = await session.execute(
        select(Application)
        .where(Application.student_id == student.id)
        .order_by(Application.created_at.desc())
    )
    existing_app = existing_app_q.scalars().first()

    if existing_app:
        current_status = str(existing_app.status).lower()
        if current_status in [ApplicationStatus.PENDING.value, ApplicationStatus.IN_PROGRESS.value]:
            raise ValueError("You already have an active application under process.")
        if current_status == ApplicationStatus.COMPLETED.value:
            raise ValueError("You have already received your No Dues certificate.")

    # 3. Update Student Fields
    student.father_name = payload.father_name
    student.mother_name = payload.mother_name
    student.gender = payload.gender
    student.category = payload.category
    student.dob = payload.dob
    student.permanent_address = payload.permanent_address
    student.domicile = payload.domicile
    
    student.section = payload.section
    student.batch = payload.batch
    student.admission_year = payload.admission_year
    student.admission_type = payload.admission_type
    
    student.is_hosteller = payload.is_hosteller
    if payload.is_hosteller:
        student.hostel_name = payload.hostel_name
        student.hostel_room = payload.hostel_room
    else:
        student.hostel_name = None
        student.hostel_room = None

    session.add(student)

    # 4. Create Main Application
    app = Application(
        id=uuid.uuid4(),
        student_id=student.id,
        status=ApplicationStatus.PENDING.value,
        current_stage_order=1, 
        remarks=payload.remarks, 
        proof_document_url=payload.proof_document_url,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(app)
    await session.flush() 

    # 5. Generate Stages (✅ UPDATED LOGIC)
    for stage_info in DEFAULT_STAGES:
        
        # Skip Hostel if not hosteller
        if stage_info["role"] == UserRole.Hostel and not student.is_hosteller:
            continue

        stage_school_id = None
        stage_dept_id = None 

        # Logic A: Dean uses School ID
        if stage_info["role"] == UserRole.Dean:
            stage_school_id = student.school_id
        
        # Logic B: Everyone else uses Department ID from the map
        else:
            config_name = stage_info["name"].lower() # e.g., "library"
            if config_name in dept_map:
                stage_dept_id = dept_map[config_name] # e.g., 1
            else:
                print(f"⚠️ Warning: No Department found for '{stage_info['name']}'")

        stage = ApplicationStage(
            id=uuid.uuid4(),
            application_id=app.id,
            verifier_role=stage_info["role"].value if hasattr(stage_info["role"], "value") else stage_info["role"],
            sequence_order=stage_info["order"],
            status=ApplicationStatus.PENDING.value,
            
            # ✅ NOW POPULATED CORRECTLY
            school_id=stage_school_id, 
            department_id=stage_dept_id, 
            
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(stage)

    # 6. Commit
    try:
        await session.commit()
        await session.refresh(app)
        return app

    except IntegrityError as e:
        await session.rollback()
        print(f"Database Integrity Error: {e}") 
        raise ValueError("Failed to create application due to data conflict.")
    except Exception as e:
        await session.rollback()
        print(f"Unexpected Error: {e}")
        raise e

async def get_application_by_student(session: AsyncSession, student_id: uuid.UUID) -> Optional[Application]:
    """Fetch the latest application for a student."""
    query = select(Application).where(Application.student_id == student_id).order_by(Application.created_at.desc())
    result = await session.execute(query)
    return result.scalars().first()