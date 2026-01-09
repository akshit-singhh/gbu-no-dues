# app/schemas/application.py

from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import date, datetime

# ============================================================
# 1. SHARED BASE (For partial updates/reading)
# ============================================================
class StudentBase(BaseModel):
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
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 2. APPLICATION CREATE (POST)
#    - Includes Proof URL (from Supabase)
#    - Includes Remarks
#    - Includes Profile Fields (to sync with Student Profile)
# ============================================================
class ApplicationCreate(BaseModel):
    # --- NEW: Application Specifics ---
    proof_document_url: str  # The public URL returned from /api/utils/upload-proof
    remarks: Optional[str] = None

    # --- Profile Details (Mandatory for No Dues) ---
    father_name: str
    mother_name: str
    gender: str
    category: str
    dob: date
    permanent_address: str
    domicile: str
    
    # --- Hostel Info ---
    is_hosteller: bool
    hostel_name: Optional[str] = None
    hostel_room: Optional[str] = None

    # --- Academic Details ---
    section: Optional[str] = None
    batch: str             # e.g., "2021-2025"
    admission_year: int    # e.g., 2021
    admission_type: str    # e.g., "Regular"


# ============================================================
# 3. STUDENT UPDATE (PATCH) -> NESTED Structure
# ============================================================
# A. The inner data (Just the personal edits)
class StudentUpdateData(StudentBase):
    pass 

# B. The Wrapper to match { "student_update": { ... } }
class StudentUpdateWrapper(BaseModel):
    student_update: StudentUpdateData


# ============================================================
# 4. APPLICATION READ (Admin / Status)
# ============================================================
class ApplicationRead(BaseModel):
    id: UUID
    student_id: UUID
    status: str
    
    # Include the proof URL in the response
    proof_document_url: Optional[str] = None
    
    # Correct handling of optional DB fields
    current_stage_order: int = 1
    remarks: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)