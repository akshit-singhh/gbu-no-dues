from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models.application import Application
from app.models.application_stage import ApplicationStage


# ---------------------------------------------------------
# INTERNAL: RECALCULATE GLOBAL APPLICATION STATUS
# ---------------------------------------------------------
async def _update_application_status(session: AsyncSession, application_id: str):

    result = await session.execute(
        select(ApplicationStage).where(ApplicationStage.application_id == application_id)
    )
    stages = result.scalars().all()

    # Determine new application-level status
    if any(s.status == "Rejected" for s in stages):
        new_status = "Rejected"

    elif all(s.status == "Approved" for s in stages):
        new_status = "Completed"

    elif any(s.status == "Approved" for s in stages):
        new_status = "InProgress"

    else:
        new_status = "Pending"

    # Fetch application
    app_result = await session.execute(
        select(Application).where(Application.id == application_id)
    )
    app = app_result.scalar_one()

    # Apply update
    app.status = new_status
    app.updated_at = datetime.utcnow()
    session.add(app)


# ---------------------------------------------------------
# APPROVE STAGE
# ---------------------------------------------------------
async def approve_stage(session: AsyncSession, stage_id: str, reviewer_id: str):

    result = await session.execute(
        select(ApplicationStage).where(ApplicationStage.id == stage_id)
    )
    stage = result.scalar_one_or_none()

    if not stage:
        raise ValueError("Stage not found.")

    # 🚫 PREVENT INVALID OPERATIONS
    if stage.status == "Approved":
        raise ValueError("Stage is already approved.")
    if stage.status == "Rejected":
        raise ValueError("Rejected stage cannot be approved.")

    # Apply approval
    stage.status = "Approved"
    stage.reviewer_id = reviewer_id
    stage.reviewed_at = datetime.utcnow()
    session.add(stage)

    # Update application-level status
    await _update_application_status(session, stage.application_id)

    return stage


# ---------------------------------------------------------
# REJECT STAGE
# ---------------------------------------------------------
async def reject_stage(session: AsyncSession, stage_id: str, reviewer_id: str, remarks: str):

    result = await session.execute(
        select(ApplicationStage).where(ApplicationStage.id == stage_id)
    )
    stage = result.scalar_one_or_none()

    if not stage:
        raise ValueError("Stage not found.")

    # 🚫 PREVENT INVALID OPERATIONS
    if stage.status == "Rejected":
        raise ValueError("Stage is already rejected.")
    if stage.status == "Approved":
        raise ValueError("Approved stage cannot be rejected.")

    # Apply rejection
    stage.status = "Rejected"
    stage.remarks = remarks
    stage.reviewer_id = reviewer_id
    stage.reviewed_at = datetime.utcnow()
    session.add(stage)

    # Update application-level status
    await _update_application_status(session, stage.application_id)

    return stage
