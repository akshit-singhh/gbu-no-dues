# app/schemas/user.py

from typing import Optional, Any
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
    
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    
    school_id: Optional[int] = None
    school_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    # ✅ ROBUST FIX: Convert to Dict
    @model_validator(mode='before')
    @classmethod
    def flatten_details(cls, data: Any) -> Any:
        """
        Converts the SQLAlchemy object to a Dictionary and populates
        missing fields (school_name, etc.) manually.
        This bypasses the "object has no field" error.
        """
        # If it's already a dict, just return it
        if isinstance(data, dict):
            return data

        # 1. Initialize variables
        dept_name = None
        sch_name = None
        # Default IDs from the User object
        sch_id = getattr(data, "school_id", None)
        dept_id = getattr(data, "department_id", None)

        # 2. Logic: Extract Names from Relationships
        
        # A. Department (Staff)
        if getattr(data, "department", None):
            dept_name = data.department.name

        # B. School (Dean - Direct Link)
        if getattr(data, "school", None):
            sch_name = data.school.name

        # C. Student School (Indirect Link)
        # Check role safely (handle Enum or string)
        role_val = getattr(data, "role", "")
        # If role is Enum, get value, else string
        role_str = str(role_val.value if hasattr(role_val, "value") else role_val).lower()

        if "student" in role_str:
            student_obj = getattr(data, "student", None)
            if student_obj and getattr(student_obj, "school", None):
                # Override with Student's School Info
                sch_id = student_obj.school_id
                sch_name = student_obj.school.name

        # 3. Create the Safe Dictionary
        # We manually construct the dict that matches UserRead fields
        return {
            "id": data.id,
            "name": data.name,
            "email": data.email,
            "role": data.role,
            "department_id": dept_id,
            "department_name": dept_name,
            "school_id": sch_id,
            "school_name": sch_name
        }