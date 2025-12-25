# app/services/auth_service.py

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import uuid
import random
from datetime import datetime, timedelta, timezone # Added timezone

from app.models.user import User, UserRole
from app.models.student import Student
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
)
from app.schemas.auth import TokenWithUser
from app.schemas.user import UserRead
from app.schemas.auth_student import StudentLoginResponse


# ============================================================================
# FETCH USER BY EMAIL
# ============================================================================
async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# ============================================================================
# FETCH USER BY ID
# ============================================================================
async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ============================================================================
# CREATE USER  (FULLY FIXED)
# ============================================================================
async def create_user(
    session: AsyncSession,
    name: str,
    email: str,
    password: str,
    role: UserRole,
    department_id: int | None = None,
    student_id: uuid.UUID | None = None,
) -> User:

    # ---- VALIDATION RULES ----
    # 1) Staff MUST have department_id
    if role == UserRole.Staff and department_id is None:
        raise ValueError("Staff must be assigned to a department")

    # 2) Non-staff cannot have department_id
    if role != UserRole.Staff and department_id is not None:
        raise ValueError(f"{role.value} cannot have a department_id")

    # 3) Student must have linked student_id
    if role == UserRole.Student and student_id is None:
        raise ValueError("Student account must include student_id")

    # 4) Non-student cannot have student_id
    if role != UserRole.Student and student_id is not None:
        raise ValueError(f"{role.value} accounts cannot have student_id")

    user = User(
        id=uuid.uuid4(),
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        department_id=department_id,
        student_id=student_id,
    )

    session.add(user)

    try:
        await session.commit()
        await session.refresh(user)
        return user

    except IntegrityError:
        await session.rollback()
        raise ValueError("User with this email already exists")


# ============================================================================
# AUTHENTICATE ADMIN/Staff/HOD
# ============================================================================
async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


# ============================================================================
# CREATE LOGIN RESPONSE
# ============================================================================
from app.models.department import Department

async def create_login_response(user: User, session: AsyncSession) -> TokenWithUser:
    # Normalize role string
    role_str = (
        user.role.value.lower()
        if isinstance(user.role, UserRole)
        else str(user.role).lower()
    )

    # Fetch department name if exists
    department_name = None
    if user.department_id:
        result = await session.execute(
            select(Department.name).where(Department.id == user.department_id)
        )
        department_name = result.scalar_one_or_none()

    # JWT token contains both role & department info
    token = create_access_token(
        subject=str(user.id),
        data={
            "role": role_str,
            "department_id": user.department_id,
            "department_name": department_name,
        },
    )

    # Build response
    user_read = UserRead.from_orm(user)
    user_read.department_name = department_name

    return TokenWithUser(
        access_token=token,
        expires_in=3600,
        user=user_read,
        department_name=department_name,
    )



# ============================================================================
# AUTHENTICATE STUDENT LOGIN
# ============================================================================
async def authenticate_student(
    session: AsyncSession,
    identifier: str,
    password: str
) -> StudentLoginResponse | None:

    identifier = identifier.strip()

    # 1) Find matching student
    result = await session.execute(
        select(Student).where(
            (Student.enrollment_number.ilike(identifier)) |
            (Student.roll_number.ilike(identifier))
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        return None

    # 2) Find user record linked to student_id
    result = await session.execute(select(User).where(User.student_id == student.id))
    user = result.scalar_one_or_none()
    if not user:
        return None

    # 3) Role must be 'Student'
    if user.role != UserRole.Student:
        return None

    # 4) Password check
    if not verify_password(password, user.password_hash):
        return None

    # 5) Generate token
    token = create_access_token(
        subject=str(user.id),
        data={"role": "student"}
    )

    return StudentLoginResponse(
        access_token=token,
        user_id=user.id,
        student_id=student.id,
        student=student,
    )


# ============================================================================
# FORGOT PASSWORD LOGIC
# ============================================================================

async def request_password_reset(session: AsyncSession, email: str):
    """
    Business logic for password reset.
    """
    user = await get_user_by_email(session, email)
    if not user:
        # Raise error so the API knows not to attempt sending an email
        raise ValueError("User not found")

    # Generate and save OTP with timezone-aware expiry
    otp = f"{random.randint(100000, 999999)}"
    user.otp_code = otp
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    session.add(user)
    await session.commit()
    
    # Trigger the email only for valid users
    from app.services.email_service import send_password_reset_email
    send_password_reset_email(user.email, otp)
    
    return True


async def verify_reset_otp(session: AsyncSession, email: str, otp: str) -> bool:
    """
    Checks if the provided OTP is valid and not expired.
    """
    user = await get_user_by_email(session, email)
    if not user or user.otp_code != otp:
        return False
    
    # FIX: Compare using timezone-aware UTC
    if user.otp_expires_at and user.otp_expires_at < datetime.now(timezone.utc):
        return False
        
    return True


async def finalize_password_reset(session: AsyncSession, email: str, otp: str, new_password: str):
    """
    Verifies OTP one last time, updates password, and clears OTP fields.
    """
    user = await get_user_by_email(session, email)
    if not user or user.otp_code != otp:
        raise ValueError("Invalid or expired OTP")

    # FIX: Use timezone-aware UTC datetime for comparison
    if user.otp_expires_at and user.otp_expires_at < datetime.now(timezone.utc):
        raise ValueError("OTP has expired")

    # Update password using existing hash utility
    user.password_hash = hash_password(new_password)
    
    # Clear OTP fields after successful reset
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
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    await session.delete(user)
    await session.commit()


# ============================================================================
# UPDATE USER (FIXED)
# ============================================================================
async def update_user(
    session: AsyncSession,
    user_id: str,
    name: str | None = None,
    email: str | None = None,
    role: UserRole | None = None,
    department_id: int | None = None,
) -> User:

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    if email and email != user.email:
        dup = await session.execute(select(User).where(User.email == email))
        if dup.scalar_one_or_none():
            raise ValueError("Email already in use")
        user.email = email

    if name:
        user.name = name

    if role:
        if role == UserRole.Staff and department_id is None and user.department_id is None:
            raise ValueError("Staff must be assigned to a department")
        if role != UserRole.Staff and department_id is not None:
            raise ValueError(f"{role.value} cannot have a department_id")

        user.role = role

    if department_id is not None:
        if user.role != UserRole.Staff:
            raise ValueError("Only Staff can have department")
        user.department_id = department_id

    try:
        await session.commit()
        await session.refresh(user)
        return user

    except IntegrityError:
        await session.rollback()
        raise ValueError("Failed to update user")