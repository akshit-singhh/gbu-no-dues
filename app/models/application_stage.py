# app/models/application_stage.py

from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.application import ApplicationStatus

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.user import User

class ApplicationStage(SQLModel, table=True):
    __tablename__ = "application_stages"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )

    application_id: UUID = Field(foreign_key="applications.id", nullable=False)
    
    # --------------------------------------------------------
    # (Critical for Dean/School Office)
    # --------------------------------------------------------
    school_id: Optional[int] = Field(default=None, foreign_key="schools.id")

    # This handles Lab/Department specific stages
    department_id: Optional[int] = Field(default=None, foreign_key="departments.id")

    verifier_role: str = Field(nullable=False)
    status: str = Field(default=ApplicationStatus.PENDING.value)
    
    comments: Optional[str] = Field(default=None)

    #Add foreign_key to link to Users table
    verified_by: Optional[UUID] = Field(default=None, foreign_key="users.id")
    
    verified_at: Optional[datetime] = Field(default=None)

    sequence_order: int = Field(default=1, sa_column=Column(Integer, nullable=False))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    application: "Application" = Relationship(back_populates="stages")
    
    #Add the relationship back to User
    # This matches Relationship(back_populates="verifier") in your User model
    verifier: Optional["User"] = Relationship(back_populates="verified_stages")