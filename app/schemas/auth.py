# app/schemas/auth.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from uuid import UUID

from app.models.user import UserRole
# Keeping these imports for response models
from app.schemas.user import UserRead
from app.schemas.student import StudentRead


# -------------------------------------------------------------------
# LOGIN REQUEST
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
# REGISTER REQUEST (Staff/Admin)
# -------------------------------------------------------------------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole
    
    department_code: Optional[str] = None   
    school_code: Optional[str] = None
    
    # Backward compatibility
    department_id: Optional[int] = None 
    school_id: Optional[int] = None

    captcha_input: Optional[str] = Field(None, description="CAPTCHA code")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Staff User",
                "email": "staff@example.com",
                "password": "password123",
                "role": "staff",
                "department_code": "LIB",
                "school_code": None
            }
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
    student_id: Optional[str] = None


# -------------------------------------------------------------------
# STUDENT AUTH SCHEMAS
# -------------------------------------------------------------------

class StudentLoginRequest(BaseModel):
    identifier: str
    password: str
    captcha_input: str = Field(..., description="The 5-character code from the CAPTCHA image")
    captcha_hash: str = Field(..., description="The cryptographic hash returned by the captcha generator")


class StudentWithSchool(BaseModel):
    id: UUID
    full_name: str
    email: str
    roll_number: str
    enrollment_number: str
    mobile_number: Optional[str] = None
    school_id: Optional[int] = None
    school_name: Optional[str] = None
    department_id: Optional[int] = None

    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    admission_year: Optional[int] = None
    gender: Optional[str] = None
    section: Optional[str] = None
    admission_type: Optional[str] = None
    is_hosteller: bool = False
    hostel_name: Optional[str] = None
    hostel_room: Optional[str] = None
    
    class Config:
        from_attributes = True
        extra = "allow"


class StudentLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    student_id: UUID
    student: StudentWithSchool 

    class Config:
        from_attributes = True


class StudentRegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    roll_number: str
    enrollment_number: str
    mobile_number: str
    school_id: int
    
    # Optional Profile Fields
    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    admission_year: Optional[int] = None
    gender: Optional[str] = None
    section: Optional[str] = None
    admission_type: Optional[str] = None
    is_hosteller: bool = False
    hostel_name: Optional[str] = None
    hostel_room: Optional[str] = None

    captcha_input: str
    captcha_hash: str


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
# ADMIN CREATION SCHEMAS
# -------------------------------------------------------------------
class SchoolCreateRequest(BaseModel):
    name: str
    code: str
    
class DepartmentCreateRequest(BaseModel):
    name: str
    phase_number: int
    code: str