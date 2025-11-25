from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID

from app.models.user import UserRole
from app.schemas.user import UserRead
from app.schemas.student import StudentRead


# -------------------------------------------------------------------
# LOGIN REQUEST
# -------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# -------------------------------------------------------------------
# REGISTER REQUEST  
# (Admin creates: HOD / Staff / Student)
# -------------------------------------------------------------------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole                  # Admin / HOD / Staff / Student
    department_id: Optional[int] = None   # REQUIRED for Staff & HOD

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "name": "Staff User",
                    "email": "staff@example.com",
                    "password": "password123",
                    "role": "Staff",
                    "department_id": 3
                },
                {
                    "name": "HOD User",
                    "email": "hod@example.com",
                    "password": "password123",
                    "role": "HOD",
                    "department_id": 1
                },
                {
                    "name": "Student User",
                    "email": "student@example.com",
                    "password": "password123",
                    "role": "Student"
                    # Student does NOT need department_id
                }
            ]
        }


# -------------------------------------------------------------------
# TOKEN RESPONSE
# -------------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None


# -------------------------------------------------------------------
# TOKEN + USER DETAILS (Used for login response)
# -------------------------------------------------------------------
class TokenWithUser(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    user: UserRead

    # attach department name explicitly
    department_name: Optional[str] = None


# -------------------------------------------------------------------
# STUDENT LOGIN REQUEST
# -------------------------------------------------------------------
class StudentLoginRequest(BaseModel):
    identifier: str
    password: str


# -------------------------------------------------------------------
# STUDENT LOGIN RESPONSE
# -------------------------------------------------------------------
class StudentLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    student_id: UUID
    student: StudentRead

    class Config:
        from_attributes = True
