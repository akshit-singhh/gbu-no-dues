#app/models/audit.py

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    application_id: Optional[UUID] = Field(default=None, foreign_key="applications.id")
    actor_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    actor_role: Optional[str] = None
    
    # 1. NEW FIELD: Actor Name (Snapshot)
    actor_name: Optional[str] = None 
    
    action: str
    remarks: Optional[str] = None
    
    # Stores {"student_roll": "...", "stage": "..."}
    details: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB)) 
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)