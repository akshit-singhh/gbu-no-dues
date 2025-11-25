# app/services/approval_service.py

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID

from app.models.application import Application
from app.models.application_stage import ApplicationStage
from app.models.user import User, UserRole

async def _update_application_status(session: AsyncSession, application_id: str):
    """Recalculate global application status based on stages."""
    result = await session.execute(
        select(ApplicationStage).where(ApplicationStage.application_id == application_id)
    )
    stages = result.scalars().all()

    if any(s.status == "Rejected" for s in stages):
        new_status = "Rejected"
    elif all(s.status == "Approved" for s in stages) and len(stages) > 0:
        new_status = "Completed"
    elif any(s.status == "Approved" for s in stages):
        new_status = "InProgress"
    else:
        new_status = "Pending"

    app_res = await session.execute(
        select(Application).where(Application.id == application_id)
    )
    app = app_res.scalar_one()
    app.status = new_status
    app.updated_at = datetime.utcnow()
    session.add(app)


async def _fetch_user(session: AsyncSession, reviewer_id):
    # Accept either UUID or str
    if not isinstance(reviewer_id, UUID):
        reviewer_id = UUID(str(reviewer_id))
    result = await session.execute(select(User).where(User.id == reviewer_id))
    return result.scalar_one_or_none()


async def approve_stage(session: AsyncSession, stage_id: str, reviewer_id):
    result = await session.execute(
        select(ApplicationStage).where(ApplicationStage.id == stage_id)
    )
    stage = result.scalar_one_or_none()
    if not stage:
        raise ValueError("Stage not found")

    # fetch application to check which department currently owns it
    app_res = await session.execute(select(Application).where(Application.id == stage.application_id))
    application = app_res.scalar_one_or_none()
    if not application:
        raise ValueError("Linked application not found")

    # fetch reviewer user
    reviewer = await _fetch_user(session, reviewer_id)
    if not reviewer:
        raise ValueError("Reviewer user not found")

    # Permission check: admin bypass, otherwise reviewer must belong to app.current_department_id
    if not (reviewer.role == UserRole.Admin or reviewer.role == UserRole.HOD):
        if reviewer.department_id is None:
            raise ValueError("Reviewer does not belong to any department")
        if application.current_department_id != reviewer.department_id:
            raise ValueError("Reviewer not allowed to approve this application")

    # update stage
    stage.status = "Approved"
    stage.reviewer_id = reviewer.id
    stage.reviewed_at = datetime.utcnow()
    session.add(stage)

    # update application global status
    await _update_application_status(session, stage.application_id)

    return stage


async def reject_stage(session: AsyncSession, stage_id: str, reviewer_id, remarks: str):
    result = await session.execute(
        select(ApplicationStage).where(ApplicationStage.id == stage_id)
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

    # Permission check same as approve
    if not (reviewer.role == UserRole.Admin or reviewer.role == UserRole.HOD):
        if reviewer.department_id is None:
            raise ValueError("Reviewer does not belong to any department")
        if application.current_department_id != reviewer.department_id:
            raise ValueError("Reviewer not allowed to reject this application")

    stage.status = "Rejected"
    stage.remarks = remarks
    stage.reviewer_id = reviewer.id
    stage.reviewed_at = datetime.utcnow()
    session.add(stage)

    await _update_application_status(session, stage.application_id)

    return stage
