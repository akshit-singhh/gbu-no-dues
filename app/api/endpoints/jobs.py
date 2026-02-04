# app/api/endpoints/jobs.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from datetime import datetime, timedelta
from collections import defaultdict
import os

from app.api.deps import get_db_session
from app.core.config import settings
from app.models.application_stage import ApplicationStage
from app.models.user import User
from app.models.department import Department
from app.services.email_service import send_pending_reminder_email

router = APIRouter(prefix="/api/jobs", tags=["Background Jobs"])

@router.post("/trigger-stale-notifications")
async def trigger_stale_notifications(
    secret_key: str, 
    session: AsyncSession = Depends(get_db_session)
):
    """
    Scans for applications pending > 7 days and emails the department heads.
    """
    # 1. Security Check
    EXPECTED_KEY = os.getenv("JOB_SECRET", "my_super_secret_job_key_123")
    if secret_key != EXPECTED_KEY:
        raise HTTPException(status_code=403, detail="Invalid Secret Key")

    # 2. Define "Stale" Threshold (7 days ago)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    # 3. Query Pending Stages older than 7 days
    query = (
        select(ApplicationStage)
        .where(ApplicationStage.status == "pending")
        .where(ApplicationStage.created_at <= seven_days_ago)
    )
    result = await session.execute(query)
    stale_stages = result.scalars().all()

    if not stale_stages:
        return {"message": "No stale applications found."}

    # 4. Group by Department/Role
    grouped_stale = defaultdict(list)
    
    for stage in stale_stages:
        key = f"DEPT_{stage.department_id}" if stage.department_id else f"ROLE_{stage.verifier_role}"
        grouped_stale[key].append(stage)

    # 5. Notify Users (With Deduplication)
    notifications_sent = 0

    for key, stages in grouped_stale.items():
        count = len(stages)
        target_role = stages[0].verifier_role
        dept_id = stages[0].department_id
        
        # Find Verifiers
        user_query = select(User).where(User.role == target_role)
        
        if dept_id:
            user_query = user_query.where(User.department_id == dept_id)
            dept_obj = await session.get(Department, dept_id)
            dept_name = dept_obj.name if dept_obj else target_role.capitalize()
        else:
            dept_name = target_role.capitalize()

        user_res = await session.execute(user_query)
        verifiers = user_res.scalars().all()

        # Track sent emails for this group to prevent duplicates
        sent_emails_for_this_group = set()

        for verifier in verifiers:
            # Skip if user has no email or we already emailed this address for this department
            if not verifier.email or verifier.email in sent_emails_for_this_group:
                continue

            await send_pending_reminder_email(
                verifier_name=verifier.name,
                verifier_email=verifier.email,
                pending_count=count,
                department_name=dept_name
            )
            
            # Mark this email as sent
            sent_emails_for_this_group.add(verifier.email)
            notifications_sent += 1

    return {
        "status": "success", 
        "stale_stages_found": len(stale_stages), 
        "emails_sent": notifications_sent
    }