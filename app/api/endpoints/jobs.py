import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import get_db_session
from app.core.config import settings
from app.models.application_stage import ApplicationStage
from app.models.user import User
from app.models.department import Department
from app.services.email_service import send_pending_reminder_email
from loguru import logger

router = APIRouter(prefix="/api/jobs", tags=["Background Jobs"])

@router.post("/trigger-stale-notifications")
async def trigger_stale_notifications(
    secret_key: str, 
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    """
    CRON JOB ENDPOINT.
    Aggregates pending applications > 7 days old and notifies Department Heads.
    """
    # 1. Security Check
    EXPECTED_KEY = os.getenv("JOB_SECRET")
    if not EXPECTED_KEY or secret_key != EXPECTED_KEY:
        logger.warning(f"Unauthorized access attempt to background job.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Invalid or missing Job Secret Key."
        )

    # 2. Database Aggregation
    # Use timezone-naive datetime for PostgreSQL compatibility
    seven_days_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)

    stmt = (
        select(
            ApplicationStage.department_id,
            ApplicationStage.verifier_role,
            func.count(ApplicationStage.id).label("pending_count")
        )
        .where(ApplicationStage.status == "pending")
        .where(ApplicationStage.created_at <= seven_days_ago) 
        .group_by(ApplicationStage.department_id, ApplicationStage.verifier_role)
    )

    result = await session.execute(stmt)
    stale_groups = result.all() 

    if not stale_groups:
        return {"status": "skipped", "message": "No stale applications found."}

    logger.info(f"Found {len(stale_groups)} department groups with stale applications.")

    # 3. Process Groups & Queue Emails
    emails_triggered = 0

    for dept_id, role, count in stale_groups:
        try:
            # A. Find the Target Verifiers
            user_query = select(User).where(User.role == role)
            
            # Prepare department name
            dept_name = role.replace("_", " ").title()
            
            # Filter by Dept ID if applicable
            if dept_id:
                user_query = user_query.where(User.department_id == dept_id)
                dept_obj = await session.get(Department, dept_id)
                if dept_obj:
                    dept_name = dept_obj.name

            # B. Execute User Fetch
            user_res = await session.execute(user_query)
            verifiers = user_res.scalars().all()

            if not verifiers:
                logger.warning(f"Stale Job: No users found for Role: {role}, Dept: {dept_id}")
                continue

            # C. Send Emails
            for verifier in verifiers:
                if not verifier.email: 
                    continue
                
                # Changed 'verifier.full_name' to 'verifier.name'
                background_tasks.add_task(
                    safe_send_email,
                    verifier_name=verifier.name, 
                    verifier_email=verifier.email,
                    pending_count=count,
                    department_name=dept_name
                )
                emails_triggered += 1

        except Exception as e:
            logger.error(f"Failed to process group {dept_id}/{role}: {e}")
            continue

    return {
        "status": "success",
        "groups_processed": len(stale_groups),
        "emails_queued": emails_triggered
    }

async def safe_send_email(verifier_name: str, verifier_email: str, pending_count: int, department_name: str):
    """
    Wrapper to prevent email failures from crashing the worker.
    """
    try:
        await send_pending_reminder_email(
            verifier_name=verifier_name,
            verifier_email=verifier_email,
            pending_count=pending_count,
            department_name=department_name
        )
        logger.info(f"Reminder sent to {verifier_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {verifier_email}: {e}")