# app/models/system_audit.py

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

class SystemAuditLog(SQLModel, table=True):
    __tablename__ = "system_audit_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # Who did it (can be null if it's an anonymous action, like a failed login attempt)
    actor_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    
    # ✅ NEW: What was their role at the time of the action?
    actor_role: Optional[str] = None
    
    # What kind of event (e.g., "USER_LOGIN", "ROLE_CHANGED", "SETTINGS_UPDATED")
    event_type: str = Field(index=True)
    
    # What resource was affected (e.g., "User", "Department", "SystemConfig")
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    
    # Security context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # The actual changes made (using JSONB just like your audit_logs details)
    old_values: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    new_values: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    
    # Outcome (e.g., "SUCCESS", "FAILURE")
    status: str = Field(default="SUCCESS")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)