from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import uuid

from app.models.application import Application
from app.models.student import Student

ALLOWED_STUDENT_UPDATE_FIELDS = {
    "full_name",
    "father_name",
    "mother_name",
    "gender",
    "category",
    "dob",
    "permanent_address",
    "domicile",
    "is_hosteller",
    "hostel_name",
    "hostel_room",
    "department_id",
    "section",
    "batch",
    "admission_year",
    "admission_type",
}

VALID_CATEGORIES = {"GEN", "OBC", "SC", "ST"}

async def create_application_for_student(
    session: AsyncSession,
    student_id: str,
    payload: dict
):

    # ---------------------------------------
    # 1. Fetch student
    # ---------------------------------------
    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise ValueError("Student not found")

    # ---------------------------------------
    # 2. Check existing application
    # ---------------------------------------
    existing_app_q = await session.execute(
        select(Application).where(Application.student_id == student.id)
    )
    existing_app = existing_app_q.scalar_one_or_none()

    if existing_app:
        # Normalize status for comparison
        current_status = existing_app.status.upper() if existing_app.status else "PENDING"

        # If Rejected, we allow resubmission by removing the old rejected entry
        # so a new one can be created cleanly below.
        if current_status == "REJECTED":
            await session.delete(existing_app)
            await session.flush() # Ensure deletion is registered before insertion
        
        # If Completed, strict block
        elif current_status == "COMPLETED":
            raise ValueError("Your application is already completed.")
            
        # If Pending, InProgress, Submitted, etc. -> Block
        else:
            raise ValueError("You already have an active application.")

    # ---------------------------------------
    # 3. Update student fields safely
    # ---------------------------------------
    student_update = payload.get("student_update") or {}

    for field, value in student_update.items():

        if field not in ALLOWED_STUDENT_UPDATE_FIELDS:
            continue  # ignore fields not allowed

        # Normalize category
        if field == "category" and value:
            value = value.upper()  # gen -> GEN
            if value not in VALID_CATEGORIES:
                raise ValueError(
                    f"Invalid category '{value}'. Allowed: {list(VALID_CATEGORIES)}"
                )

        # Normalize gender
        if field == "gender" and value:
            value = value.capitalize()  # male -> Male

        if hasattr(student, field):
            setattr(student, field, value)

    session.add(student)

    # ---------------------------------------
    # 4. Create new application
    # ---------------------------------------
    # Note: If it was Rejected, the old one is deleted above, 
    # so we are safe to create a new one here.
    app = Application(
        id=uuid.uuid4(),
        student_id=student.id,
        status="Pending",
        remarks=payload.get("remarks") or None
    )

    session.add(app)

    # ---------------------------------------
    # 5. Commit transaction
    # ---------------------------------------
    try:
        await session.commit()
        await session.refresh(app)
        return app

    except IntegrityError as e:
        await session.rollback()
        print("IntegrityError while creating application:", e)
        raise ValueError("Failed to create application. Integrity Error.")
    except Exception as e:
        await session.rollback()
        print("Unexpected error:", e)
        raise e