# app/api/endpoints/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List
from uuid import UUID

# Schemas
from app.schemas.auth import (
    LoginRequest, 
    RegisterRequest, 
    TokenWithUser,
    ForgotPasswordRequest,
    VerifyOTPRequest,
    ResetPasswordRequest
)
from app.schemas.user import UserRead, UserUpdate
from app.schemas.student import StudentRead

# Models
from app.models.user import UserRole, User

# Services
from app.services.auth_service import (
    authenticate_user,
    create_login_response,
    create_user,
    get_user_by_email,
    list_users,
    delete_user_by_id,
    update_user,
    request_password_reset,
    verify_reset_otp,
    finalize_password_reset
)
from app.services.student_service import get_student_by_id, list_students

# Deps
from app.api.deps import get_db_session, get_current_user, require_super_admin

router = APIRouter(prefix="/api/admin", tags=["Auth (Super Admin)"])


# -------------------------------------------------------------------
# LOGIN (Admin login)
# -------------------------------------------------------------------
@router.post("/login", response_model=TokenWithUser)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session)
):
    user = await authenticate_user(session, payload.email, payload.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return await create_login_response(user, session)


# -------------------------------------------------------------------
# REGISTER SUPER ADMIN
# -------------------------------------------------------------------
@router.post("/register-super-admin", response_model=UserRead)
async def register_super_admin(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_super_admin),
):
    if data.role != UserRole.Admin:
        raise HTTPException(400, detail="This endpoint only creates Admin accounts.")

    existing = await get_user_by_email(session, data.email)
    if existing:
        raise HTTPException(400, detail="Email already exists")

    user = await create_user(
        session=session,
        name=data.name,
        email=data.email,
        password=data.password,
        role=UserRole.Admin,
        department_id=None
    )
    return user


# -------------------------------------------------------------------
# REGISTER NORMAL USER (HOD / Staff)
# -------------------------------------------------------------------
@router.post("/register-user", response_model=UserRead)
async def register_user(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_super_admin),
):
    # BLOCK ADMIN
    if data.role == UserRole.Admin:
        raise HTTPException(400, detail="Use /register-super-admin for Admin accounts.")

    # VALIDATE EMAIL
    existing = await get_user_by_email(session, data.email)
    if existing:
        raise HTTPException(400, detail="Email already exists")

    # Staff must have a department_id
    if data.role == UserRole.Staff:
        if not data.department_id:
            raise HTTPException(400, detail="department_id is required for Staff users")

    # HOD also must have department assignment (optional for now)
    if data.role == UserRole.HOD and not data.department_id:
        raise HTTPException(400, detail="HOD must belong to a department")

    user = await create_user(
        session=session,
        name=data.name,
        email=data.email,
        password=data.password,
        role=data.role,
        department_id=data.department_id,
    )
    return user


# -------------------------------------------------------------------
# PUBLIC FORGOT PASSWORD ENDPOINTS
# -------------------------------------------------------------------
@router.post("/forgot-password", tags=["Password Reset"])
async def forgot_password(
    payload: ForgotPasswordRequest, 
    session: AsyncSession = Depends(get_db_session)
):
    """
    Initiates password reset. Explicitly informs if user is not found.
    """
    try:
        await request_password_reset(session, payload.email)
        # Explicit Success Message
        return {"message": f"OTP sent successfully. Please check your mail."}
    except ValueError as e:
        # Explicit Error Message (User Not Found)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=str(e) # This will be "User with this email does not exist"
        )

@router.post("/verify-reset-otp", tags=["Password Reset"])
async def verify_reset_otp_endpoint(
    payload: VerifyOTPRequest, 
    session: AsyncSession = Depends(get_db_session)
):
    """
    Verifies the 6-digit OTP sent to the user's email.
    """
    is_valid = await verify_reset_otp(session, payload.email, payload.otp)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    return {"message": "OTP verified successfully"}


@router.post("/reset-password", tags=["Password Reset"])
async def reset_password(
    payload: ResetPasswordRequest, 
    session: AsyncSession = Depends(get_db_session)
):
    """
    Finalizes the password reset process by setting a new password.
    """
    try:
        await finalize_password_reset(
            session, 
            payload.email, 
            payload.otp, 
            payload.new_password
        )
        return {"message": "Password updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------------
# LIST ALL USERS
# -------------------------------------------------------------------
@router.get("/users", response_model=List[UserRead])
async def get_all_users(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_super_admin),
):
    return await list_users(session)


# -------------------------------------------------------------------
# DELETE USER
# -------------------------------------------------------------------
@router.delete("/users/{user_id}", status_code=204)
async def remove_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_super_admin),
):
    try:
        await delete_user_by_id(session, str(user_id))
    except ValueError as e:
        raise HTTPException(404, detail=str(e))

    return None


# -------------------------------------------------------------------
# UPDATE USER
# -------------------------------------------------------------------
@router.put("/users/{user_id}", response_model=UserRead)
async def update_user_endpoint(
    user_id: str,
    data: UserUpdate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_super_admin),
):
    # Staff must always have department
    if data.role == UserRole.Staff and not data.department_id:
        raise HTTPException(400, detail="department_id is required for Staff users")

    try:
        return await update_user(
            session,
            user_id=user_id,
            name=data.name,
            email=data.email,
            role=data.role,
            department_id=data.department_id
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


# -------------------------------------------------------------------
# GET CURRENT ADMIN
# -------------------------------------------------------------------
@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


# -------------------------------------------------------------------
# GET STUDENT BY ID
# -------------------------------------------------------------------
@router.get("/students/{student_id}", response_model=StudentRead)
async def admin_get_student_by_id(
    student_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_super_admin),
):
    student = await get_student_by_id(session, student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    return student


# -------------------------------------------------------------------
# LIST ALL STUDENTS
# -------------------------------------------------------------------
@router.get("/students", response_model=List[StudentRead])
async def admin_list_students(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_super_admin),
):
    return await list_students(session)