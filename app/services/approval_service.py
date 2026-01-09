# app/services/approval_service.py

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID

from app.models.application import Application, ApplicationStatus
from app.models.application_stage import ApplicationStage
from app.models.user import User, UserRole

# ----------------------------------------------------------------
# 1. SMART STATUS UPDATER (Batch Logic - Non-Blocking)
# ----------------------------------------------------------------
async def _update_application_status(session: AsyncSession, application_id: UUID):
    """
    Checks if the application can move to the next level.
    
    LOGIC:
    1. Wait for ALL stages at the current level to finish (Approve or Reject).
    2. If any are still Pending -> Stay IN_PROGRESS.
    3. Once everyone finishes:
       - If any Rejections -> Mark App as REJECTED.
       - If all Approved -> Move to NEXT Level.
    """
    # 1. Fetch Application
    app_res = await session.execute(select(Application).where(Application.id == application_id))
    app = app_res.scalar_one()

    current_level = app.current_stage_order

    # 2. Fetch ALL stages at the CURRENT level
    current_stages_res = await session.execute(
        select(ApplicationStage)
        .where(
            (ApplicationStage.application_id == application_id) &
            (ApplicationStage.sequence_order == current_level)
        )
    )
    current_stages = current_stages_res.scalars().all()

    # ---------------------------------------------------------
    # CHECK 1: IS ANYONE STILL PENDING? (Priority)
    # ---------------------------------------------------------
    # If even one department hasn't acted yet, we wait. 
    # We keep the status as IN_PROGRESS so others can still see and act on it.
    if any(s.status == ApplicationStatus.PENDING.value for s in current_stages):
        app.status = ApplicationStatus.IN_PROGRESS.value
        session.add(app)
        return 

    # ---------------------------------------------------------
    # CHECK 2: ARE THERE REJECTIONS?
    # ---------------------------------------------------------
    # We only reach here if EVERYONE at this level has finished (Approved or Rejected).
    rejected_stages = [s for s in current_stages if s.status == ApplicationStatus.REJECTED.value]
    
    if rejected_stages:
        # One or more departments rejected it. Now we stop the flow.
        app.status = ApplicationStatus.REJECTED.value
        
        # Consolidate remarks (e.g., "Library: Book due; Hostel: Fine pending")
        reject_notes = "; ".join([f"{s.verifier_role}: {s.comments or 'No remarks'}" for s in rejected_stages])
        app.remarks = f"Rejected at Level {current_level}: {reject_notes}"
        
        session.add(app)
        return

    # ---------------------------------------------------------
    # CHECK 3: ALL APPROVED -> MOVE NEXT
    # ---------------------------------------------------------
    # No pending, No rejections -> Everyone approved!
    next_stage_res = await session.execute(
        select(ApplicationStage)
        .where(
            (ApplicationStage.application_id == application_id) &
            (ApplicationStage.sequence_order > current_level)
        )
        .order_by(ApplicationStage.sequence_order.asc())
    )
    next_stage = next_stage_res.scalars().first()

    if next_stage:
        # Advance to the next level (e.g., 2 -> 3)
        app.current_stage_order = next_stage.sequence_order
        app.status = ApplicationStatus.IN_PROGRESS.value
    else:
        # No more stages -> Completed
        app.status = ApplicationStatus.COMPLETED.value
        app.is_completed = True
        app.current_stage_order = 999 

    app.updated_at = datetime.utcnow()
    session.add(app)


# ----------------------------------------------------------------
# HELPER: FETCH REVIEWER
# ----------------------------------------------------------------
async def _fetch_user(session: AsyncSession, reviewer_id):
    if not isinstance(reviewer_id, UUID):
        reviewer_id = UUID(str(reviewer_id))
    result = await session.execute(select(User).where(User.id == reviewer_id))
    return result.scalar_one_or_none()


# ----------------------------------------------------------------
# ACTION: APPROVE STAGE
# ----------------------------------------------------------------
async def approve_stage(session: AsyncSession, stage_id: str, reviewer_id):
    stage_uuid = UUID(stage_id) if isinstance(stage_id, str) else stage_id

    result = await session.execute(select(ApplicationStage).where(ApplicationStage.id == stage_uuid))
    stage = result.scalar_one_or_none()
    if not stage: raise ValueError("Stage not found")
    if stage.status == ApplicationStatus.APPROVED.value: raise ValueError("Already approved.")

    # Validate Logic
    app_res = await session.execute(select(Application).where(Application.id == stage.application_id))
    application = app_res.scalar_one()

    if stage.sequence_order != application.current_stage_order:
         raise ValueError("Cannot approve: Application is not currently at this stage level.")

    reviewer = await _fetch_user(session, reviewer_id)
    if not reviewer: raise ValueError("Reviewer user not found")

    # [Permission Checks]
    if reviewer.role != UserRole.Admin:
        if stage.school_id is not None:
            if reviewer.role != UserRole.Dean or getattr(reviewer, 'school_id', None) != stage.school_id:
                 raise ValueError("Only the correct Dean can approve this stage.")
        elif stage.department_id is not None:
            if reviewer.role != UserRole.Staff or getattr(reviewer, 'department_id', None) != stage.department_id:
                 raise ValueError("Only the correct Staff can approve this stage.")
        else:
            reviewer_role_str = reviewer.role.value if hasattr(reviewer.role, "value") else reviewer.role
            if stage.verifier_role != reviewer_role_str:
                raise ValueError(f"Access Denied: This stage requires {stage.verifier_role} role.")

    # Update Stage
    stage.status = ApplicationStatus.APPROVED.value
    stage.verified_by = reviewer.id
    stage.verified_at = datetime.utcnow()
    stage.comments = "Approved via Portal"
    
    session.add(stage)

    #  CRITICAL: Flush changes so the query inside _update_application_status sees this approval
    await session.flush()
    
    # Update Global Status
    await _update_application_status(session, stage.application_id)

    # COMMIT THE TRANSACTION
    await session.commit()
    await session.refresh(stage)
    
    return stage


# ----------------------------------------------------------------
# ACTION: REJECT STAGE
# ----------------------------------------------------------------
async def reject_stage(session: AsyncSession, stage_id: str, reviewer_id, remarks: str):
    stage_uuid = UUID(stage_id) if isinstance(stage_id, str) else stage_id

    result = await session.execute(select(ApplicationStage).where(ApplicationStage.id == stage_uuid))
    stage = result.scalar_one_or_none()
    if not stage: raise ValueError("Stage not found")

    app_res = await session.execute(select(Application).where(Application.id == stage.application_id))
    application = app_res.scalar_one()

    if stage.sequence_order != application.current_stage_order:
        raise ValueError("Cannot reject: Application is not currently at this stage level.")

    reviewer = await _fetch_user(session, reviewer_id)
    if not reviewer: raise ValueError("Reviewer user not found")

    # Update Stage
    stage.status = ApplicationStatus.REJECTED.value
    stage.comments = remarks
    stage.verified_by = reviewer.id
    stage.verified_at = datetime.utcnow()
    
    session.add(stage)
    
    # CRITICAL: Flush changes
    await session.flush()
    
    # Update Global Status
    await _update_application_status(session, stage.application_id)

    # COMMIT THE TRANSACTION
    await session.commit()
    await session.refresh(stage)

    return stage