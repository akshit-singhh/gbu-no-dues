# app/schemas/user.py

from typing import Optional, Any, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict, model_validator
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
    
    # Use CODES (Robust) instead of IDs (Fragile)
    department_code: Optional[str] = None   
    school_code: Optional[str] = None       


# ---------------------------------------------------------
# UPDATE USER (Admin edits)
# ---------------------------------------------------------
class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    
    # Allow updating via Codes
    department_code: Optional[str] = None
    school_code: Optional[str] = None
    
    # IDs kept for backward compatibility if needed
    department_id: Optional[int] = None
    school_id: Optional[int] = None


# ---------------------------------------------------------
# READ USER (Response)
# ---------------------------------------------------------
class UserRead(UserBase):
    id: UUID
    role: UserRole | str
    
    # IDs (For Frontend Keys)
    department_id: Optional[int] = None
    school_id: Optional[int] = None

    # Names (For Display)
    department_name: Optional[str] = None
    school_name: Optional[str] = None

    # Codes (For Logic/Consistency)
    department_code: Optional[str] = None
    school_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    # Extracts Name AND Code from relationships
    @model_validator(mode='before')
    @classmethod
    def flatten_details(cls, data: Any) -> Any:
        """
        Converts the SQLAlchemy object to a Dictionary and populates
        missing fields (school_name, school_code, etc.) manually.
        """
        # If it's already a dict, just return it
        if isinstance(data, dict):
            return data

        # 1. Initialize variables
        dept_name = None
        dept_code = None
        
        sch_name = None
        sch_code = None
        
        # Default IDs from the User object
        sch_id = getattr(data, "school_id", None)
        dept_id = getattr(data, "department_id", None)

        # 2. Logic: Extract Names & Codes from Relationships
        
        # A. Department (Staff / HOD)
        if getattr(data, "department", None):
            dept_name = data.department.name
            dept_code = getattr(data.department, "code", None)

        # B. School (Dean - Direct Link)
        if getattr(data, "school", None):
            sch_name = data.school.name
            sch_code = getattr(data.school, "code", None)

        # C. Student School (Indirect Link)
        role_val = getattr(data, "role", "")
        role_str = str(role_val.value if hasattr(role_val, "value") else role_val).lower()

        if "student" in role_str:
            student_obj = getattr(data, "student", None)
            if student_obj and getattr(student_obj, "school", None):
                # Override with Student's School Info
                sch_id = student_obj.school_id
                sch_name = student_obj.school.name
                sch_code = getattr(student_obj.school, "code", None)

        # 3. Return the fully populated dictionary
        return {
            "id": data.id,
            "name": data.name,
            "email": data.email,
            "role": data.role,
            
            # IDs
            "department_id": dept_id,
            "school_id": sch_id,
            
            # Names
            "department_name": dept_name,
            "school_name": sch_name,
            
            # Codes
            "department_code": dept_code,
            "school_code": sch_code
        }

# ---------------------------------------------------------
# USER LIST RESPONSE
# ---------------------------------------------------------
class UserListResponse(BaseModel):
    total: int
    users: List[UserRead]