from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict
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
    department_id: Optional[int] = None   # Required if Role = Staff
    school_id: Optional[int] = None       # Required if Role = Dean


# ---------------------------------------------------------
# UPDATE USER (Admin edits)
# ---------------------------------------------------------
class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    department_id: Optional[int] = None
    school_id: Optional[int] = None


# ---------------------------------------------------------
# READ USER (response)
# ---------------------------------------------------------
class UserRead(UserBase):
    id: UUID
    role: UserRole | str
    
    # Department Info
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    
    # School Info (For Deans)
    school_id: Optional[int] = None
    school_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)