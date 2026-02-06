# app/schemas/student.py

from pydantic import BaseModel, EmailStr, field_validator, ValidationInfo, ConfigDict, model_validator
from typing import Optional, Any
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
    captcha_input: str
    captcha_hash: str

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
    mobile_number: Optional[str] = None
    email: Optional[EmailStr] = None
    
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
    
    # Allow updating Academic Dept via Code (Robust)
    department_code: Optional[str] = None 
    department_id: Optional[int] = None # Kept for backward compatibility
    
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

    # IDs
    school_id: Optional[int] = None
    department_id: Optional[int] = None

    # Names & Codes (Populated via Validator for UI convenience)
    school_name: Optional[str] = None
    school_code: Optional[str] = None
    
    department_name: Optional[str] = None
    department_code: Optional[str] = None

    section: Optional[str] = None
    batch: Optional[str] = None
    admission_year: Optional[int] = None
    admission_type: Optional[str] = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    # Validator to extract Names & Codes from Relationships
    @model_validator(mode='before')
    @classmethod
    def flatten_school_dept_details(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        
        # If it's a SQLModel/ORM object
        return {
            "id": data.id,
            "enrollment_number": data.enrollment_number,
            "roll_number": data.roll_number,
            "full_name": data.full_name,
            "mobile_number": data.mobile_number,
            "email": data.email,
            "father_name": data.father_name,
            "mother_name": data.mother_name,
            "gender": data.gender,
            "category": data.category,
            "dob": data.dob,
            "permanent_address": data.permanent_address,
            "domicile": data.domicile,
            "is_hosteller": data.is_hosteller,
            "hostel_name": data.hostel_name,
            "hostel_room": data.hostel_room,
            
            "school_id": data.school_id,
            # Handle relationship safely
            "school_name": data.school.name if getattr(data, "school", None) else None,
            "school_code": getattr(data.school, "code", None) if getattr(data, "school", None) else None,
            
            "department_id": data.department_id,
            # Handle relationship safely
            "department_name": data.department.name if getattr(data, "department", None) else None,
            "department_code": getattr(data.department, "code", None) if getattr(data, "department", None) else None,
            
            "section": data.section,
            "batch": data.batch,
            "admission_year": data.admission_year,
            "admission_type": data.admission_type,
            "created_at": data.created_at
        }