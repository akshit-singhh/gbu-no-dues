from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


# ---------------------------------------------------------
# BASE
# ---------------------------------------------------------
class UserBase(BaseModel):
    name: str
    email: EmailStr


# ---------------------------------------------------------
# CREATE USER (Admin creates any user)
# ---------------------------------------------------------
class UserCreate(UserBase):
    password: str
    role: UserRole
    department_id: Optional[int] = None   # Only required for Staff users


# ---------------------------------------------------------
# UPDATE USER (Admin edits)
# ---------------------------------------------------------
class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    department_id: Optional[int] = None   # nullable


# ---------------------------------------------------------
# READ USER (response)
# ---------------------------------------------------------
class UserRead(UserBase):
    id: UUID
    role: UserRole | str
    department_id: Optional[int] = None
    department_name: Optional[str] = None

    class Config:
        from_attributes = True

