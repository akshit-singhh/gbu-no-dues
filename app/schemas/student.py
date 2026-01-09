# app/schemas/student.py
from pydantic import BaseModel, EmailStr, field_validator, ValidationInfo, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import date, datetime

# ------------------------------------------------------------
# STUDENT REGISTRATION (Public)
# ------------------------------------------------------------
class StudentRegister(BaseModel):
    enrollment_number: str
    roll_number: str
    full_name: str
    mobile_number: str
    email: EmailStr
    
    # Linked to School
    school_id: int

    password: str
    confirm_password: Optional[str] = None

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: Optional[str], info: ValidationInfo) -> str:
        password = info.data.get("password")
        if v is None:
            return password if password else ""
        if password and v != password:
            raise ValueError("Passwords do not match")
        return v


# ------------------------------------------------------------
# STUDENT UPDATE (For PATCH /api/students/me)
# ------------------------------------------------------------
class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    mobile_number: Optional[str] = None  # ✅ Added this so they can update phone
    email: Optional[EmailStr] = None     # ✅ Added this so they can update email
    
    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    gender: Optional[str] = None
    category: Optional[str] = None
    dob: Optional[date] = None

    permanent_address: Optional[str] = None
    domicile: Optional[str] = None
    
    # Hostel Details
    is_hosteller: Optional[bool] = None
    hostel_name: Optional[str] = None
    hostel_room: Optional[str] = None

    # Academic Details
    school_id: Optional[int] = None
    section: Optional[str] = None
    batch: Optional[str] = None
    admission_year: Optional[int] = None
    admission_type: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------
# FULL STUDENT READ RESPONSE
# ------------------------------------------------------------
class StudentRead(BaseModel):
    id: UUID

    enrollment_number: str
    roll_number: str
    full_name: str
    mobile_number: str
    email: EmailStr

    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    gender: Optional[str] = None
    category: Optional[str] = None
    dob: Optional[date] = None

    permanent_address: Optional[str] = None
    domicile: Optional[str] = None
    is_hosteller: Optional[bool] = None
    hostel_name: Optional[str] = None
    hostel_room: Optional[str] = None

    school_id: Optional[int] = None
    section: Optional[str] = None
    batch: Optional[str] = None
    admission_year: Optional[int] = None
    admission_type: Optional[str] = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)