# app/schemas/auth.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID

from app.models.user import UserRole
from app.schemas.user import UserRead
from app.schemas.student import StudentRead


# -------------------------------------------------------------------
# LOGIN REQUEST (Admin/Staff/Dean) - [FIXED]
# -------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_input: str = Field(..., description="The 5-character code from the CAPTCHA image")
    captcha_hash: str = Field(..., description="The cryptographic hash returned by the captcha generator")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123",
                "captcha_input": "....",
                "captcha_hash": "...."
            }
        }


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
    # Captcha is usually optional for internal admin registration
    captcha_input: Optional[str] = Field(None, description="CAPTCHA code (optional for admin creation)")

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
# TOKEN + USER DETAILS
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
    captcha_input: str = Field(..., description="The 5-character code from the CAPTCHA image")
    captcha_hash: str = Field(..., description="The cryptographic hash returned by the captcha generator")


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
    captcha_input: Optional[str] = Field(None, description="CAPTCHA code")

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
    code: str
    
class DepartmentCreateRequest(BaseModel):
    name: str
    phase_number: int