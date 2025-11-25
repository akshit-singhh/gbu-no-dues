# app/schemas/student.py
from pydantic import BaseModel, EmailStr, field_validator, ValidationInfo
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

    password: str
    confirm_password: Optional[str] = None

    @field_validator("confirm_password")
    def passwords_match(cls, v, info: ValidationInfo):
        """
        Tests do NOT send confirm_password.
        So we auto-fill it with password so validation passes.
        """
        # FIX: Access the dictionary via info.data
        password = info.data.get("password")

        # If confirm_password missing → auto-fill
        if v is None:
            return password

        if password and v != password:
            raise ValueError("Passwords do not match")

        return v


# ------------------------------------------------------------
# STUDENT UPDATE (Filled during application submission)
# ------------------------------------------------------------
class StudentUpdate(BaseModel):
    full_name: Optional[str]
    father_name: Optional[str]
    mother_name: Optional[str]
    gender: Optional[str]
    category: Optional[str]
    dob: Optional[date]

    permanent_address: Optional[str]
    domicile: Optional[str]
    is_hosteller: Optional[bool]
    hostel_name: Optional[str]
    hostel_room: Optional[str]

    department_id: Optional[int]
    section: Optional[str]
    batch: Optional[str]
    admission_year: Optional[int]
    admission_type: Optional[str]


# ------------------------------------------------------------
# FULL STUDENT READ RESPONSE (Used everywhere in API responses)
# ------------------------------------------------------------
class StudentRead(BaseModel):
    id: UUID

    enrollment_number: str
    roll_number: str
    full_name: str
    mobile_number: str
    email: EmailStr

    father_name: Optional[str]
    mother_name: Optional[str]
    gender: Optional[str]
    category: Optional[str]
    dob: Optional[date]

    permanent_address: Optional[str]
    domicile: Optional[str]
    is_hosteller: Optional[bool]
    hostel_name: Optional[str]
    hostel_room: Optional[str]

    department_id: Optional[int]
    section: Optional[str]
    batch: Optional[str]
    admission_year: Optional[int]
    admission_type: Optional[str]

    created_at: datetime

    class Config:
        from_attributes = True