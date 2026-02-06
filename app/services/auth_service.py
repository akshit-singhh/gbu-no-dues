# app/services/auth_service.py

import string
from sqlmodel import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
import uuid
import random
from datetime import datetime, timedelta, timezone
from loguru import logger 

from app.models.user import User, UserRole
from app.models.student import Student
from app.models.department import Department
from app.models.school import School
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
)
from app.schemas.auth import TokenWithUser, StudentLoginResponse
from app.schemas.student import StudentRegister
from app.core.config import settings


# ============================================================================
# FETCH USER BY EMAIL
# ============================================================================
async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    statement = select(User).where(User.email == email).options(selectinload(User.student))
    result = await session.execute(statement)
    return result.scalar_one_or_none()


# ============================================================================
# FETCH USER BY ID
# ============================================================================
async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    try:
        uuid_obj = uuid.UUID(str(user_id))
    except ValueError:
        return None
        
    statement = select(User).where(User.id == uuid_obj).options(selectinload(User.student))
    result = await session.execute(statement)
    return result.scalar_one_or_none()


# ============================================================================
# REGISTER STUDENT (FIXED: Circular Dependency Resolution)
# ============================================================================
async def register_student(session: AsyncSession, payload: StudentRegister) -> Student:
    """
    Creates a User account first, then creates a Student profile linked to it.
    Resolves FK violation by 3-step process: Create User -> Create Student -> Update User.
    """
    # 1. Check if Email Exists (User Table)
    existing_user = await get_user_by_email(session, payload.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # 2. Check Enrollment/Roll No (Student Table)
    stmt = select(Student).where(
        or_(
            Student.enrollment_number == payload.enrollment_number,
            Student.roll_number == payload.roll_number
        )
    )
    result = await session.execute(stmt)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enrollment or Roll Number already registered"
        )

    # 3. Generate IDs explicitly
    new_user_id = uuid.uuid4()
    new_student_id = uuid.uuid4()

    # 4. STEP 1: Create User (student_id MUST be None initially)
    new_user = User(
        id=new_user_id,
        name=payload.full_name,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role=UserRole.Student,
        school_id=payload.school_id, 
        student_id=None, # <--- IMPORTANT: Leave None to avoid FK error
        is_active=True
    )
    session.add(new_user)
    
    # 5. STEP 2: Create Student (Link to User is safe because User is added to session)
    new_student = Student(
        id=new_student_id,
        user_id=new_user_id, # Link Backward to User
        school_id=payload.school_id,
        enrollment_number=payload.enrollment_number,
        roll_number=payload.roll_number,
        full_name=payload.full_name,
        mobile_number=payload.mobile_number,
        email=payload.email
    )
    session.add(new_student)

    try:
        # Flush to insert User and Student into DB (but in same transaction)
        await session.flush()

        # 6. STEP 3: Update User to link to Student
        new_user.student_id = new_student_id
        session.add(new_user) # Mark User as dirty/modified

        # 7. Commit Transaction
        await session.commit()
        await session.refresh(new_student)
        return new_student

    except Exception as e:
        await session.rollback()
        logger.error(f"Registration DB Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during registration: {str(e)}"
        )


# ============================================================================
# CREATE USER (General Admin Use)
# ============================================================================
async def create_user(
    session: AsyncSession,
    name: str,
    email: str,
    password: str,
    role: UserRole,
    department_id: int | None = None,
    student_id: uuid.UUID | None = None,
    school_id: int | None = None,
) -> User:

    # Admin creation logic might differ, but generally safe to set student_id if student exists
    user_data = {
        "id": uuid.uuid4(),
        "name": name,
        "email": email,
        "password_hash": get_password_hash(password),
        "role": role,
        "student_id": student_id,
        "department_id": department_id,
        "school_id": school_id,
        "is_active": True
    }

    user = User(**user_data)
    session.add(user)

    try:
        await session.commit()
        
        # Refresh with Eager Load
        stmt = (
            select(User)
            .options(
                selectinload(User.school),
                selectinload(User.department),
                selectinload(User.student)
            )
            .where(User.id == user.id)
        )
        result = await session.execute(stmt)
        return result.scalar_one()

    except IntegrityError:
        await session.rollback()
        raise ValueError("User with this email already exists")


# ============================================================================
# AUTHENTICATE USER (Admin / Staff)
# ============================================================================
async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None
    
    if hasattr(user, "is_active") and not user.is_active:
        return None

    return user


# ============================================================================
# AUTHENTICATE STUDENT LOGIN
# ============================================================================
async def authenticate_student(
    session: AsyncSession,
    identifier: str,
    password: str
) -> StudentLoginResponse | None:

    identifier = identifier.strip()

    # 1. Fetch Student 
    query = (
        select(Student)
        .options(selectinload(Student.school)) 
        .where(
            or_(
                Student.enrollment_number.ilike(identifier),
                Student.roll_number.ilike(identifier),
                Student.email.ilike(identifier)
            )
        )
    )
    result = await session.execute(query)
    students = result.scalars().all()
    
    if not students:
        return None
        
    # Self-Healing Logic for Duplicates
    if len(students) > 1:
        logger.warning(f"Duplicate student records found for: {identifier}. Using most recent.")
        student = sorted(students, key=lambda s: s.created_at, reverse=True)[0]
    else:
        student = students[0]

    # 2. Fetch Linked User
    result = await session.execute(
        select(User)
        .where(User.student_id == student.id)
        .options(selectinload(User.student))
    )
    user = result.scalars().first()
    
    if not user:
        # Fallback: Try finding user by email if link is broken
        user = await get_user_by_email(session, student.email)
        if not user:
            return None

    # Verify Role
    user_role_val = user.role.value if hasattr(user.role, "value") else user.role
    if str(user_role_val) != UserRole.Student.value:
        return None

    # Verify Password
    if not verify_password(password, user.password_hash):
        return None

    token = create_access_token(
        subject=str(user.id),
        data={
            "role": "student",
            "student_id": str(student.id),
            "school_id": student.school_id
        }
    )

    student_dict = student.model_dump()
    student_dict["school_name"] = student.school.name if student.school else "Unknown School"

    return StudentLoginResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        student_id=student.id,
        student=student_dict,
    )


# ============================================================================
# CREATE LOGIN RESPONSE (Restored)
# ============================================================================
async def create_login_response(user: User, session: AsyncSession) -> TokenWithUser:
    role_str = str(user.role.value if hasattr(user.role, "value") else user.role).lower()

    user_dept_id = getattr(user, "department_id", None)
    user_school_id = getattr(user, "school_id", None)
    
    if user.student and user.student.school_id:
        user_school_id = user.student.school_id

    # 1. Fetch Department Name
    department_name = None
    if user_dept_id:
        try:
            result = await session.execute(
                select(Department.name).where(Department.id == user_dept_id)
            )
            department_name = result.scalar_one_or_none()
        except:
            pass

    # 2. Fetch School Name
    school_name = None
    if user_school_id:
        try:
            result = await session.execute(
                select(School.name).where(School.id == user_school_id)
            )
            school_name = result.scalar_one_or_none()
        except:
            pass

    # 3. Create Token Claims
    token_data = {
        "role": role_str,
        "department_id": user_dept_id,
        "school_id": user_school_id,
    }
    
    if user.student_id:
        token_data["student_id"] = str(user.student_id)

    token = create_access_token(
        subject=str(user.id),
        data=token_data,
    )

    return TokenWithUser(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_name=user.name,
        user_role=role_str,
        user_id=user.id,
        
        department_id=user_dept_id,
        department_name=department_name,
        school_id=user_school_id,
        school_name=school_name
    )


# ============================================================================
# PASSWORD RESET UTILS
# ============================================================================
async def request_password_reset(session: AsyncSession, email: str):
    """
    Generates a 6-digit OTP and sets expiry to 5 minutes from now.
    """
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User with this email not found")

    # Generate 6-digit OTP
    otp = ''.join(random.choices(string.digits, k=6))
    
    # Set OTP and Expiry (Now + 5 minutes)
    user.otp_code = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    return otp, user

async def verify_reset_otp(session: AsyncSession, email: str, otp: str) -> bool:
    """
    Verifies the OTP and checks if it is expired.
    """
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.otp_code or not user.otp_expires_at:
        return False

    # Check 1: Does OTP Match?
    if user.otp_code != otp:
        return False

    # Check 2: Is it Expired?
    if datetime.utcnow() > user.otp_expires_at:
        return False

    return True

async def finalize_password_reset(session: AsyncSession, email: str, otp: str, new_password: str):
    """
    Resets the password if OTP is valid.
    """
    # Verify again just to be safe
    is_valid = await verify_reset_otp(session, email, otp)
    if not is_valid:
        raise ValueError("Invalid or expired OTP")

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one()

    # Update Password and Clear OTP
    user.password_hash = get_password_hash(new_password)
    user.otp_code = None
    user.otp_expires_at = None
    
    session.add(user)
    await session.commit()


# ============================================================================
# LIST USERS
# ============================================================================
async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User))
    return result.scalars().all()


# ============================================================================
# DELETE USER
# ============================================================================
async def delete_user_by_id(session: AsyncSession, user_id: str) -> None:
    try:
        uuid_obj = uuid.UUID(str(user_id))
    except ValueError:
        raise ValueError("Invalid User ID")

    result = await session.execute(select(User).where(User.id == uuid_obj))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    await session.delete(user)
    await session.commit()


# ============================================================================
# UPDATE USER
# ============================================================================
async def update_user(
    session: AsyncSession,
    user_id: str,
    name: str | None = None,
    email: str | None = None,
    role: UserRole | None = None,
    department_id: int | None = None,
    school_id: int | None = None,
) -> User:

    try:
        uuid_obj = uuid.UUID(str(user_id))
    except ValueError:
        raise ValueError("Invalid User ID")

    # 1. Fetch User
    result = await session.execute(select(User).where(User.id == uuid_obj))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    # 2. Update Email (Check Duplicates)
    if email and email != user.email:
        dup = await session.execute(select(User).where(User.email == email))
        if dup.scalar_one_or_none():
            raise ValueError("Email already in use")
        user.email = email

    if name: user.name = name
    if role: user.role = role

    # 3. Handle Foreign Keys (0 -> None)
    if department_id is not None:
        if department_id == 0:
            user.department_id = None
        else:
            user.department_id = department_id

    if school_id is not None:
        if school_id == 0:
            user.school_id = None
        else:
            user.school_id = school_id

    # 4. Save & Return (With Eager Loading)
    try:
        await session.commit()
        
        stmt = (
            select(User)
            .options(
                selectinload(User.school),
                selectinload(User.department),
                selectinload(User.student).selectinload(Student.school)
            )
            .where(User.id == user.id)
        )
        result = await session.execute(stmt)
        return result.scalar_one()

    except IntegrityError as e:
        await session.rollback()
        print(f"Update User Error: {str(e)}") 
        if "foreign key constraint" in str(e).lower():
            raise ValueError("Invalid School ID or Department ID provided.")
        raise ValueError("Failed to update user (Database Integrity Error)")