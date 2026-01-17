# app/api/endpoints/users.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List
from sqlmodel import select

from app.api.deps import get_db_session, require_admin
from app.schemas.user import UserRead
from app.schemas.auth import RegisterRequest
from app.services.auth_service import get_user_by_email, create_user
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/users", tags=["Users"])


# -------------------------------------------------------------------
# Create ANY user (Admin only)
# -------------------------------------------------------------------
# Added status_code=201 to match typical REST patterns and test expectations
@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin) # Admin Only
):
    # Ensure email is unique
    existing = await get_user_by_email(session, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Validate and enforce allowed roles
    # (Note: Pydantic usually handles this if typed as UserRole, but keeping manual check for safety)
    allowed_values = [r.value for r in UserRole]
    if data.role not in allowed_values:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{data.role}'. Allowed roles: {allowed_values}"
        )

    # Create user
    user = await create_user(
        session,
        data.name,
        data.email,
        data.password,
        role=data.role,  # role now comes from body
    )
    return user


# -------------------------------------------------------------------
# List all users (Admin only)
# -------------------------------------------------------------------
@router.get("/", response_model=List[UserRead])
async def list_users(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin) # Admin Only
):
    result = await session.execute(select(User))
    return result.scalars().all()


# -------------------------------------------------------------------
# Delete a user (Admin only)
# -------------------------------------------------------------------
@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin) # Admin Only
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(user)
    await session.commit()
    return {"detail": "User deleted successfully"}