# app/models/application.py

from enum import Enum
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# Use TYPE_CHECKING to avoid circular import errors at runtime
if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.application_stage import ApplicationStage

class ApplicationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

# ----------------------------------------------------------------
# 1. The Main Application Table
# ----------------------------------------------------------------
class Application(SQLModel, table=True):
    __tablename__ = "applications"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )

    student_id: UUID = Field(foreign_key="students.id", nullable=False)
    
    status: str = Field(default=ApplicationStatus.PENDING.value)
    remarks: Optional[str] = Field(default=None)

    # ✅ NEW FIELD: Stores the Supabase Public URL for the uploaded PDF
    # We keep it nullable=True for safety, but your Schema enforces it as mandatory.
    proof_document_url: Optional[str] = Field(default=None, nullable=True)

    current_stage_order: int = Field(default=1)
    is_completed: bool = Field(default=False)
    
    # Legacy field (kept for backward compatibility, can be removed later)
    current_department_id: Optional[int] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    student: "Student" = Relationship(back_populates="applications")
    
    # Forward reference to ApplicationStage
    stages: List["ApplicationStage"] = Relationship(back_populates="application")