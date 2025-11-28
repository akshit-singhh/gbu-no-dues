# app/services/approval_service.py

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID

from app.models.application import Application
from app.models.application_stage import ApplicationStage
from app.models.user import User, UserRole
from app.models.enums import OverallApplicationStatus  # <--- IMPORT ENUM

async def _update_application_status(session: AsyncSession, application_id: UUID):
    """Recalculate global application status based on stages."""
    
    # Fetch all stages for this application
    result = await session.execute(
        select(ApplicationStage).where(ApplicationStage.application_id == application_id)
    )
    stages = result.scalars().all()

    if not stages:
        return

    # Logic to determine global status using ENUMS
    if any(s.status == "Rejected" for s in stages):
        new_status = OverallApplicationStatus.Rejected
    elif all(s.status == "Approved" for s in stages):
        new_status = OverallApplicationStatus.Completed
    elif any(s.status == "Approved" for s in stages):
        new_status = OverallApplicationStatus.InProgress
    else:
        new_status = OverallApplicationStatus.Pending

    # Fetch Application
    app_res = await session.execute(
        select(Application).where(Application.id == application_id)
    )
    app = app_res.scalar_one()

    # Only update if status changed or just to refresh timestamp
    # We assign the Enum Member, not a string
    app.status = new_status
    app.updated_at = datetime.utcnow()
    
    session.add(app)
    # Note: No commit here, the parent function handles commit


async def _fetch_user(session: AsyncSession, reviewer_id):
    if not isinstance(reviewer_id, UUID):
        reviewer_id = UUID(str(reviewer_id))
    result = await session.execute(select(User).where(User.id == reviewer_id))
    return result.scalar_one_or_none()


async def approve_stage(session: AsyncSession, stage_id: str, reviewer_id):
    # 1. Convert string to UUID safely
    if isinstance(stage_id, str):
        stage_uuid = UUID(stage_id)
    else:
        stage_uuid = stage_id

    # 2. Fetch Stage
    result = await session.execute(
        select(ApplicationStage).where(ApplicationStage.id == stage_uuid)
    )
    stage = result.scalar_one_or_none()
    
    if not stage:
        raise ValueError("Stage not found")

    # 3. Fetch Application
    app_res = await session.execute(select(Application).where(Application.id == stage.application_id))
    application = app_res.scalar_one_or_none()
    if not application:
        raise ValueError("Linked application not found")

    # 4. Fetch Reviewer & Check Permissions
    reviewer = await _fetch_user(session, reviewer_id)
    if not reviewer:
        raise ValueError("Reviewer user not found")

    # Permission Logic
    if not (reviewer.role == UserRole.Admin or reviewer.role == UserRole.HOD):
        if reviewer.department_id is None:
            raise ValueError("Reviewer does not belong to any department")
        if application.current_department_id != reviewer.department_id:
            raise ValueError("Reviewer not allowed to approve this application")

    # 5. Apply Updates
    stage.status = "Approved"
    stage.reviewer_id = reviewer.id
    stage.reviewed_at = datetime.utcnow()
    stage.remarks = "Approved via Portal" # Optional default remark
    
    session.add(stage)

    # 🔥 CRITICAL FIX: Flush changes so the next query sees 'Approved'
    await session.flush()

    # 6. Recalculate Application Status
    await _update_application_status(session, stage.application_id)

    return stage


async def reject_stage(session: AsyncSession, stage_id: str, reviewer_id, remarks: str):
    # 1. Convert string to UUID
    if isinstance(stage_id, str):
        stage_uuid = UUID(stage_id)
    else:
        stage_uuid = stage_id

    # 2. Fetch Stage
    result = await session.execute(
        select(ApplicationStage).where(ApplicationStage.id == stage_uuid)
    )
    stage = result.scalar_one_or_none()
    
    if not stage:
        raise ValueError("Stage not found")

    app_res = await session.execute(select(Application).where(Application.id == stage.application_id))
    application = app_res.scalar_one_or_none()
    if not application:
        raise ValueError("Linked application not found")

    reviewer = await _fetch_user(session, reviewer_id)
    if not reviewer:
        raise ValueError("Reviewer user not found")

    if not (reviewer.role == UserRole.Admin or reviewer.role == UserRole.HOD):
        if reviewer.department_id is None:
            raise ValueError("Reviewer does not belong to any department")
        if application.current_department_id != reviewer.department_id:
            raise ValueError("Reviewer not allowed to reject this application")

    # 3. Apply Updates
    stage.status = "Rejected"
    stage.remarks = remarks
    stage.reviewer_id = reviewer.id
    stage.reviewed_at = datetime.utcnow()
    
    session.add(stage)

    # 🔥 CRITICAL FIX: Flush here too
    await session.flush()

    await _update_application_status(session, stage.application_id)

    return stage