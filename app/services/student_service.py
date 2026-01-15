# app/services/student_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_  # <--- Added 'or_' for duplicate check
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
import uuid

from app.models.student import Student
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.schemas.student import StudentRegister, StudentUpdate


# ------------------------------------------------------------
# REGISTER STUDENT + LINKED USER ACCOUNT
# ------------------------------------------------------------
async def register_student_and_user(session: AsyncSession, data: StudentRegister) -> Student:
    """
    Registers a student and creates a user account.
    INCLUDES MANUAL DUPLICATE CHECK to prevent database corruption.
    """

    # 1. MANUAL DUPLICATE CHECK (CRASH PROOF VERSION)
    # This prevents creating two students with the same Roll No if the DB constraint is missing.
    query = select(Student).where(
        or_(
            Student.roll_number == data.roll_number,
            Student.enrollment_number == data.enrollment_number
        )
    )
    result = await session.execute(query)
    
    # FIX: Use scalars().first() instead of scalar_one_or_none()
    # This avoids crashing if multiple duplicates already exist.
    existing = result.scalars().first()

    if existing:
        if existing.roll_number == data.roll_number:
            raise ValueError(f"Roll Number '{data.roll_number}' is already registered.")
        else:
            raise ValueError(f"Enrollment Number '{data.enrollment_number}' is already registered.")

    # -----------------------------
    # 2) CREATE STUDENT
    # -----------------------------
    # Using the exact fields from your working code + any additional fields from the schema
    student = Student(
        enrollment_number=data.enrollment_number,
        roll_number=data.roll_number,
        full_name=data.full_name,
        mobile_number=data.mobile_number,
        email=data.email,
        school_id=data.school_id,
        # Safely map optional fields if they exist in your schema/model
        father_name=getattr(data, 'father_name', None),
        mother_name=getattr(data, 'mother_name', None),
        admission_year=getattr(data, 'admission_year', None),
        is_hosteller=getattr(data, 'is_hosteller', False),
        hostel_name=getattr(data, 'hostel_name', None),
        hostel_room=getattr(data, 'hostel_room', None),
        batch=getattr(data, 'batch', None),
        section=getattr(data, 'section', None),
        admission_type=getattr(data, 'admission_type', None)
    )

    session.add(student)

    try:
        await session.flush() # Generates the ID for the student
    except IntegrityError as e:
        await session.rollback()
        msg = str(e.orig).lower() if hasattr(e, 'orig') else str(e)

        if "enrollment_number" in msg:
            raise ValueError("Enrollment number already exists")
        if "roll_number" in msg:
            raise ValueError("Roll number already exists")
        if "email" in msg:
            raise ValueError("Email already exists")
        
        # Fallback for other integrity errors
        raise ValueError(f"Failed to create student record: {msg}")

    # -----------------------------
    # 3) CREATE LINKED USER ACCOUNT
    # -----------------------------
    
    # Pre-check for User email duplicate to avoid rolling back student creation unnecessarily
    user_check = await session.execute(select(User).where(User.email == data.email))
    if user_check.scalar_one_or_none():
        await session.rollback()
        raise ValueError("User email is already in use by another account.")

    user = User(
        id=uuid.uuid4(),
        name=data.full_name,
        email=data.email,
        password_hash=get_password_hash(data.password),
        role=UserRole.Student.value,  
        student_id=student.id,
    )

    session.add(user)

    try:
        await session.commit()
        await session.refresh(student)
        return student

    except IntegrityError as e:
        await session.rollback()
        msg = str(e.orig).lower() if hasattr(e, 'orig') else str(e)

        if "email" in msg:
            raise ValueError("User email already exists")

        raise ValueError("Failed to create user account")


# ------------------------------------------------------------
# UPDATE STUDENT PROFILE (GENERAL UPDATE)
# ------------------------------------------------------------
async def update_student_profile(
    session: AsyncSession, 
    student_id: uuid.UUID, 
    update_data: StudentUpdate
) -> Student:

    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if not student:
        raise ValueError("Student not found")

    # Use model_dump(exclude_unset=True) so we only update fields the user actually sent
    update_dict = update_data.model_dump(exclude_unset=True)

    for key, value in update_dict.items():
        # Safety check: Ensure the attribute exists on the model
        if hasattr(student, key):
            setattr(student, key, value)

    try:
        await session.commit()
        await session.refresh(student)
        return student

    except IntegrityError as e:
        await session.rollback()
        msg = str(e.orig).lower() if hasattr(e, 'orig') else str(e)
        raise ValueError(f"Failed to update student details: {msg}")


# ------------------------------------------------------------
# GET STUDENT BY ID
# ------------------------------------------------------------
async def get_student_by_id(session: AsyncSession, student_id: uuid.UUID) -> Student | None:
    # Added options(selectinload) to prevent relationship loading errors
    result = await session.execute(
        select(Student)
        .where(Student.id == student_id)
        .options(selectinload(Student.school))
    )
    return result.scalar_one_or_none()


# ------------------------------------------------------------
# LIST ALL STUDENTS
# ------------------------------------------------------------
async def list_students(session: AsyncSession) -> list[Student]:
    result = await session.execute(select(Student))
    return result.scalars().all()