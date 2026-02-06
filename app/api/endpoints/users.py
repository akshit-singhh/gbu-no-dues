# app/api/endpoints/users.py

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List
from sqlmodel import select

from app.api.deps import get_db_session, require_admin
from app.schemas.user import UserRead
from app.models.user import User

router = APIRouter(prefix="/api/users", tags=["Users"])

# -------------------------------------------------------------------
# List all users (For convenience, same as /api/admin/users)
# -------------------------------------------------------------------
@router.get("/", response_model=List[UserRead])
async def list_users_standard(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin)
):
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()

# -------------------------------------------------------------------
# Delete a user (For convenience, same as /api/admin/users/{id})
# -------------------------------------------------------------------
@router.delete("/{user_id}")
async def delete_user_standard(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin)
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(user)
    await session.commit()
    return {"detail": "User deleted successfully"}
