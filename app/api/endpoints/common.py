from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, col
from typing import List, Optional
from pydantic import BaseModel

from app.core.rate_limiter import limiter
from app.api.deps import get_db_session
from app.models.school import School
from app.models.department import Department
from app.models.academic import Programme, Specialization 

router = APIRouter(
    prefix="/api/common",
    tags=["Common / Metadata"]
)

# ----------------------------------------------------------
# SCHEMAS (Simple Data for Dropdowns)
# ----------------------------------------------------------
class SchoolOption(BaseModel):
    name: str
    code: str

class DeptOption(BaseModel):
    name: str
    code: str
    is_academic: bool

class ProgrammeOption(BaseModel):
    name: str
    code: str
    department_code: str

class SpecializationOption(BaseModel):
    name: str
    code: str
    programme_code: str

# ----------------------------------------------------------
# 1. GET ALL SCHOOLS
# ----------------------------------------------------------
@router.get("/schools", response_model=List[SchoolOption])
@limiter.limit("20/minute")
async def get_schools(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    result = await session.execute(select(School).order_by(School.name))
    schools = result.scalars().all()
    return [SchoolOption(name=s.name, code=s.code) for s in schools]

# ----------------------------------------------------------
# 2. GET DEPARTMENTS
# ----------------------------------------------------------
@router.get("/departments", response_model=List[DeptOption])
@limiter.limit("20/minute")
async def get_departments(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    type: str = Query("all", enum=["academic", "admin", "all"]),
    school_code: Optional[str] = Query(None) 
):
    query = select(Department).order_by(Department.name)
    
    if type == "academic":
        query = query.where(Department.phase_number == 1)
        if school_code:
            query = query.join(School).where(School.code == school_code)
            
    elif type == "admin":
        query = query.where(col(Department.phase_number).in_([2, 3]))
        
    result = await session.execute(query)
    depts = result.scalars().all()
    
    return [
        DeptOption(name=d.name, code=d.code, is_academic=(d.phase_number == 1)) 
        for d in depts
    ]

# ----------------------------------------------------------
# 3. GET PROGRAMMES (Full List or Filtered)
# ----------------------------------------------------------
@router.get("/programmes", response_model=List[ProgrammeOption])
@limiter.limit("20/minute")
async def get_programmes(
    request: Request,
    # Made Optional: If not provided, returns ALL programmes
    department_code: Optional[str] = Query(None, description="Filter by Department Code (Optional)"),
    session: AsyncSession = Depends(get_db_session)
):
    query = select(Programme, Department).join(Department).order_by(Programme.name)

    if department_code:
        query = query.where(Department.code == department_code.upper().strip())
    
    result = await session.execute(query)
    rows = result.all() # Returns tuples (Programme, Department)

    return [
        ProgrammeOption(
            name=p.name, 
            code=p.code, 
            department_code=d.code # Include Dept Code for frontend mapping
        ) 
        for p, d in rows
    ]

# ----------------------------------------------------------
# 4. GET SPECIALIZATIONS (Full List or Filtered)
# ----------------------------------------------------------
@router.get("/specializations", response_model=List[SpecializationOption])
@limiter.limit("20/minute")
async def get_specializations(
    request: Request,
    # Made Optional: If not provided, returns ALL specializations
    programme_code: Optional[str] = Query(None, description="Filter by Programme Code (Optional)"),
    session: AsyncSession = Depends(get_db_session)
):
    query = select(Specialization, Programme).join(Programme).order_by(Specialization.name)

    if programme_code:
        query = query.where(Programme.code == programme_code.upper().strip())

    result = await session.execute(query)
    rows = result.all() # Returns tuples (Specialization, Programme)

    return [
        SpecializationOption(
            name=s.name, 
            code=s.code, 
            programme_code=p.code # Include Prog Code for frontend mapping
        ) 
        for s, p in rows
    ]