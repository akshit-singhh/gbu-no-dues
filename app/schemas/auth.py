# app/schemas/auth.py

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
# -------------------------------------------------------------------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole
    department_id: Optional[int] = None   
    school_id: Optional[int] = None       

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
                    "name": "Dean User",
                    "email": "dean@example.com",
                    "password": "password123",
                    "role": "Dean",
                    "school_id": 1
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
# TOKEN + USER DETAILS (Updated)
# -------------------------------------------------------------------
class TokenWithUser(Token):
    user_name: str
    user_role: str
    user_id: UUID
    
    # Extra Context Fields
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    school_id: Optional[int] = None
    school_name: Optional[str] = None


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


# -------------------------------------------------------------------
# FORGOT PASSWORD SCHEMAS
# -------------------------------------------------------------------
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

# -------------------------------------------------------------------
# ADMIN CREATION SCHEMAS (Schools & Departments)
# -------------------------------------------------------------------
class SchoolCreateRequest(BaseModel):
    name: str

class DepartmentCreateRequest(BaseModel):
    name: str