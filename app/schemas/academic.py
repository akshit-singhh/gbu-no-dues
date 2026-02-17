from pydantic import BaseModel
from typing import Optional, List

# --- PROGRAMME ---
class ProgrammeCreate(BaseModel):
    name: str
    code: str
    department_code: str # Admin sends code ("CSE"), backend resolves ID

class ProgrammeRead(BaseModel):
    id: int
    name: str
    code: str
    department_id: int

# --- SPECIALIZATION ---
class SpecializationCreate(BaseModel):
    name: str
    code: str
    programme_code: str # Admin sends code ("BTECH"), backend resolves ID

class SpecializationRead(BaseModel):
    id: int
    name: str
    code: str
    programme_id: int