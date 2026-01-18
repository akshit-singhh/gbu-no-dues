# app/services/department_service.py

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.models.application_stage import ApplicationStage, ApplicationStatus

async def list_pending_stages(
    session: AsyncSession, 
    school_id: Optional[int] = None, 
    department_id: Optional[int] = None
):
    """
    Fetches pending stages for EITHER a School (Dean) OR a Department (Staff).
    """
    query = select(ApplicationStage).where(
        ApplicationStage.status == ApplicationStatus.PENDING
    ).order_by(ApplicationStage.sequence_order.asc())

    if school_id:
        query = query.where(ApplicationStage.school_id == school_id)
    elif department_id:
        query = query.where(ApplicationStage.department_id == department_id)
    else:
        return []

    result = await session.execute(query)
    return result.scalars().all()

# ... (keep get_stage, but remove approve/reject if you switch to approval_service)
async def get_stage(session: AsyncSession, stage_id: str):
    try:
        stage_uuid = UUID(stage_id)
    except ValueError:
        return None
    result = await session.execute(select(ApplicationStage).where(ApplicationStage.id == stage_uuid))
    return result.scalar_one_or_none()