# app/services/approval_service.py

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID

from app.models.application import Application, ApplicationStatus
from app.models.application_stage import ApplicationStage
from app.models.user import User, UserRole
from app.models.student import Student

# 1. IMPORT PDF SERVICE
from app.services.pdf_service import generate_certificate_pdf

# ----------------------------------------------------------------
# 1. SMART STATUS UPDATER (Now with Cert Trigger)
# ----------------------------------------------------------------
async def _update_application_status(session: AsyncSession, application_id: UUID, trigger_user_id: UUID = None):
    """
    Checks if the application can move to the next level.
    If completed, TRIGGERS CERTIFICATE GENERATION automatically.
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

    # CHECK 1: IS ANYONE STILL PENDING?
    if any(s.status == ApplicationStatus.PENDING.value for s in current_stages):
        # Ensure status is synced to IN_PROGRESS if it was something else
        if app.status != ApplicationStatus.IN_PROGRESS.value:
            app.status = ApplicationStatus.IN_PROGRESS.value
            session.add(app)
        return 

    # CHECK 2: ARE THERE REJECTIONS?
    rejected_stages = [s for s in current_stages if s.status == ApplicationStatus.REJECTED.value]
    
    if rejected_stages:
        app.status = ApplicationStatus.REJECTED.value
        reject_notes = "; ".join([f"{s.verifier_role}: {s.comments or 'No remarks'}" for s in rejected_stages])
        app.remarks = f"Rejected at Level {current_level}: {reject_notes}"
        session.add(app)
        return

    # CHECK 3: ALL APPROVED -> MOVE NEXT
    # (If we reach here, it means NO rejections and NO pending at this level)
    
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
        # Move to next level
        app.current_stage_order = next_stage.sequence_order
        app.status = ApplicationStatus.IN_PROGRESS.value
        session.add(app)
    else:
        # NO NEXT STAGE -> COMPLETED
        # Only trigger completion logic if it wasn't already completed
        if str(app.status) != str(ApplicationStatus.COMPLETED.value):
            app.status = ApplicationStatus.COMPLETED.value
            app.is_completed = True
            app.current_stage_order = 999 
            app.remarks = "All stages cleared. Certificate Issued."
            app.updated_at = datetime.utcnow()
            
            session.add(app)
            # CRITICAL: Flush status to DB before generating PDF
            await session.flush() 

            # --- AUTO-TRIGGER CERTIFICATE GENERATION ---
            print(f"✅ App {app.display_id} is COMPLETE. Generating Certificate...")
            try:
                # We pass trigger_user_id if available, or just the app.student_id if needed by your logic
                # Ensure generate_certificate_pdf handles the logic for signer ID
                await generate_certificate_pdf(session, app.id, trigger_user_id)
            except Exception as e:
                print(f"⚠️ Certificate Generation Failed: {e}")
                # Optional: You could log this error to an audit table
                # We do NOT raise here to avoid rolling back the 'Completed' status

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

    # 1. Fetch Stage + App + Student (Crucial for correct validation)
    query = (
        select(ApplicationStage, Application, Student)
        .join(Application, ApplicationStage.application_id == Application.id)
        .join(Student, Application.student_id == Student.id)
        .where(ApplicationStage.id == stage_uuid)
    )
    result = await session.execute(query)
    row = result.first()

    if not row:
        raise ValueError("Stage not found")

    stage, application, student = row

    if stage.status == ApplicationStatus.APPROVED.value: 
        raise ValueError("Already approved.")

    if stage.sequence_order != application.current_stage_order:
         raise ValueError("Cannot approve: Application is not currently at this stage level.")

    reviewer = await _fetch_user(session, reviewer_id)
    if not reviewer: 
        raise ValueError("Reviewer user not found")

    # ---------------------------------------------------------
    # PERMISSION CHECKS (Same as your original code)
    # ---------------------------------------------------------
    if reviewer.role == UserRole.Admin:
        pass # Admin bypass
    elif reviewer.role == UserRole.Dean:
        if not getattr(reviewer, 'school_id', None):
             raise ValueError("Your Dean account has no School assigned.")
        if reviewer.school_id != student.school_id:
             raise ValueError("You are not the Dean of this student's school.")
    elif reviewer.role == UserRole.Staff:
        if not getattr(reviewer, 'department_id', None):
             raise ValueError("Your Staff account has no Department assigned.")
        if not stage.department_id:
             raise ValueError("Staff cannot approve generic stages.")
        if reviewer.department_id != stage.department_id:
             raise ValueError("You do not belong to the department for this stage.")
    else:
        reviewer_role_str = reviewer.role.value if hasattr(reviewer.role, "value") else reviewer.role
        if stage.verifier_role != reviewer_role_str:
            raise ValueError(f"Access Denied: You are {reviewer_role_str}, but this stage requires {stage.verifier_role}.")

    # ---------------------------------------------------------
    # UPDATE STAGE
    # ---------------------------------------------------------
    stage.status = ApplicationStatus.APPROVED.value
    stage.verified_by = reviewer.id
    stage.verified_at = datetime.utcnow()
    stage.comments = "Approved via Portal"
    
    session.add(stage)

    # CRITICAL: Flush to DB so update_status sees the change
    await session.flush()
    
    # Update Global Status (Passing reviewer_id for Cert Generation)
    await _update_application_status(session, stage.application_id, trigger_user_id=reviewer.id)

    # COMMIT
    await session.commit()
    await session.refresh(stage)
    
    return stage


# ----------------------------------------------------------------
# ACTION: REJECT STAGE
# ----------------------------------------------------------------
async def reject_stage(session: AsyncSession, stage_id: str, reviewer_id, remarks: str):
    stage_uuid = UUID(stage_id) if isinstance(stage_id, str) else stage_id

    # Fetch with joins to ensure consistency
    result = await session.execute(
        select(ApplicationStage, Application)
        .join(Application, ApplicationStage.application_id == Application.id)
        .where(ApplicationStage.id == stage_uuid)
    )
    row = result.first()
    
    if not row: raise ValueError("Stage not found")
    stage, application = row

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
    
    await session.flush()
    
    # Update Global Status
    await _update_application_status(session, stage.application_id, trigger_user_id=reviewer.id)

    await session.commit()
    await session.refresh(stage)

    return stage