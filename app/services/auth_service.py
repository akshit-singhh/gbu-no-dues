# app/services/auth_service.py

from sqlmodel import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
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
# CREATE USER (Eager Loads Relationships)
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

    if role == UserRole.Student and student_id is None:
        raise ValueError("Student account must include student_id")

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
        
        # Refresh with Eager Load to prevent MissingGreenlet errors in Pydantic
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
        refreshed_user = result.scalar_one()
        
        return refreshed_user

    except IntegrityError:
        await session.rollback()
        raise ValueError("User with this email already exists")


# ============================================================================
# AUTHENTICATE USER (Admin / Staff / Dean)
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
# CREATE LOGIN RESPONSE
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
# AUTHENTICATE STUDENT LOGIN (Robust Duplicate Handling & School Name Fix)
# ============================================================================
async def authenticate_student(
    session: AsyncSession,
    identifier: str,
    password: str
) -> StudentLoginResponse | None:

    identifier = identifier.strip()

    # 1. Fetch Student (Handle duplicates gracefully)
    # ✅ FIX: Eager load School here so it's available in the response immediately
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
    
    # Use scalars().all() to get list
    students = result.scalars().all()
    
    if not students:
        return None
        
    # ✅ FIX: Self-Healing Logic for Duplicates
    if len(students) > 1:
        logger.warning(f"⚠️ Duplicate student records found for: {identifier}. Using the most recent.")
        # Sort by creation time descending (newest first)
        student = sorted(students, key=lambda s: s.created_at, reverse=True)[0]
    else:
        student = students[0]

    # 2. Fetch Linked User
    result = await session.execute(
        select(User)
        .where(User.student_id == student.id)
        .options(selectinload(User.student))
    )
    users = result.scalars().all()
    
    if not users:
        return None
    
    # Safe pick user
    user = users[0]

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

    # ✅ FIX: Manually inject school_name into the response dict
    # This bypasses Pydantic stripping the relationship field
    student_dict = student.model_dump()
    student_dict["school_name"] = student.school.name if student.school else "Unknown School"

    return StudentLoginResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        student_id=student.id,
        student=student_dict, # Pass the enriched dictionary
    )


# ============================================================================
# FORGOT PASSWORD LOGIC (Timezone Safe)
# ============================================================================
async def request_password_reset(session: AsyncSession, email: str):
    user = await get_user_by_email(session, email)
    if not user:
        raise ValueError("User not found")

    otp = f"{random.randint(100000, 999999)}"
    
    # Store as naive UTC to avoid asyncpg offset errors
    expiry_time = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    user.otp_code = otp
    user.otp_expires_at = expiry_time.replace(tzinfo=None) 
    
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    return otp, user


async def verify_reset_otp(session: AsyncSession, email: str, otp: str) -> bool:
    user = await get_user_by_email(session, email)
    if not user: 
        return False
        
    user_otp = getattr(user, "otp_code", None)
    user_otp_exp = getattr(user, "otp_expires_at", None)

    if not user_otp or user_otp != otp:
        return False
    
    now = datetime.now(timezone.utc)
    
    # Fix Timezone Comparison Error
    if user_otp_exp and user_otp_exp.tzinfo is None:
        user_otp_exp = user_otp_exp.replace(tzinfo=timezone.utc)

    if user_otp_exp and user_otp_exp < now:
        return False
        
    return True


async def finalize_password_reset(session: AsyncSession, email: str, otp: str, new_password: str):
    user = await get_user_by_email(session, email)
    if not user:
        raise ValueError("User not found")
    
    # Re-verify inside finalize for security
    is_valid = await verify_reset_otp(session, email, otp)
    if not is_valid:
        raise ValueError("Invalid or expired OTP")

    user.password_hash = get_password_hash(new_password)
    
    user.otp_code = None
    user.otp_expires_at = None

    session.add(user)
    await session.commit()
    return True


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