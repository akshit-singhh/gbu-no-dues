# app/services/audit_service.py

from uuid import UUID
from typing import Optional, Dict, Any
from app.models.audit import AuditLog
from app.core.database import AsyncSessionLocal

# Note: We REMOVED 'session' from the arguments. 
# This function manages its own session now.
async def log_activity(
    action: str,
    actor_id: UUID,
    actor_role: Optional[str] = None,
    actor_name: Optional[str] = None,
    application_id: Optional[UUID] = None,
    remarks: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """
    Creates an audit log entry in a separate DB session.
    Safe for use in BackgroundTasks.
    """
    # Create a FRESH session just for this log
    async with AsyncSessionLocal() as session:
        try:
            log_entry = AuditLog(
                actor_id=actor_id,
                actor_role=actor_role,
                actor_name=actor_name,
                application_id=application_id,
                action=action,
                remarks=remarks,
                details=details or {}
            )
            
            session.add(log_entry)
            await session.commit()
            # No need to refresh unless we need the ID back immediately
            
        except Exception as e:
            # Fail silently to not crash the background worker
            print(f"❌ AUDIT LOG ERROR: {str(e)}")
            # Rollback to keep the connection pool healthy
            await session.rollback()
        
        # Session closes automatically here due to 'async with'