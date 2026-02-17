from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List

from app.api.deps import get_db_session, require_admin
from app.models.academic import Programme, Specialization
from app.models.department import Department
from app.schemas.academic import (
    ProgrammeCreate, ProgrammeRead, 
    SpecializationCreate, SpecializationRead
)

router = APIRouter(prefix="/api/academic", tags=["Academic Structure"])

# =================================================================
# ADMIN: CREATE PROGRAMME
# =================================================================
@router.post("/programmes", response_model=ProgrammeRead)
async def create_programme(
    payload: ProgrammeCreate,
    session: AsyncSession = Depends(get_db_session),
    # _: User = Depends(require_admin) # Uncomment to protect
):
    # 1. Resolve Department
    dept = await session.execute(select(Department).where(Department.code == payload.department_code.upper()))
    dept = dept.scalar_one_or_none()
    if not dept:
        raise HTTPException(400, "Invalid Department Code")

    # 2. Create
    prog = Programme(name=payload.name, code=payload.code.upper(), department_id=dept.id)
    session.add(prog)
    await session.commit()
    await session.refresh(prog)
    return prog

# =================================================================
# ADMIN: CREATE SPECIALIZATION
# =================================================================
@router.post("/specializations", response_model=SpecializationRead)
async def create_specialization(
    payload: SpecializationCreate,
    session: AsyncSession = Depends(get_db_session),
):
    # 1. Resolve Programme
    prog = await session.execute(select(Programme).where(Programme.code == payload.programme_code.upper()))
    prog = prog.scalar_one_or_none()
    if not prog:
        raise HTTPException(400, "Invalid Programme Code")

    # 2. Create
    spec = Specialization(name=payload.name, code=payload.code.upper(), programme_id=prog.id)
    session.add(spec)
    await session.commit()
    await session.refresh(spec)
    return spec

# =================================================================
# PUBLIC: GET DROPDOWNS (Cascading Logic)
# =================================================================
@router.get("/programmes", response_model=List[ProgrammeRead])
async def get_programmes(
    department_code: str, 
    session: AsyncSession = Depends(get_db_session)
):
    """Fetch all programmes for a specific department (e.g., 'CSE')"""
    query = (
        select(Programme)
        .join(Department)
        .where(Department.code == department_code.upper())
    )
    result = await session.execute(query)
    return result.scalars().all()

@router.get("/specializations", response_model=List[SpecializationRead])
async def get_specializations(
    programme_code: str, 
    session: AsyncSession = Depends(get_db_session)
):
    """Fetch all specializations for a specific programme (e.g., 'BTECH')"""
    query = (
        select(Specialization)
        .join(Programme)
        .where(Programme.code == programme_code.upper())
    )
    result = await session.execute(query)
    return result.scalars().all()