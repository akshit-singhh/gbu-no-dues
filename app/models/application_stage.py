# app/models/application_stage.py

from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Integer, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
import uuid
from datetime import datetime
from typing import Optional

# Match ENUM type in your DB: stage_status
STAGE_STATUS_ENUM = PG_ENUM(
    "Pending",
    "InProgress",
    "Approved",
    "Rejected",
    name="stage_status",
    create_type=False  # DB already has this ENUM
)

PRIORITY_ENUM = PG_ENUM(
    "Low",
    "Medium",
    "High",
    name="priority_level",
    create_type=False
)


class ApplicationStage(SQLModel, table=True):
    __tablename__ = "application_stages"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )

    application_id: uuid.UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    )

    department_id: int = Field(
        sa_column=Column(Integer, ForeignKey("departments.id"), nullable=False)
    )

    # ✔ ENUM FIX here
    status: str = Field(
        sa_column=Column(STAGE_STATUS_ENUM, nullable=False)
    )

    priority: str = Field(
        sa_column=Column(PRIORITY_ENUM, nullable=False, default="Low")
    )

    reviewer_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    )

    remarks: Optional[str] = Field(
        default=None,
        sa_column=Column(String)
    )

    reviewed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )

    sequence_order: int = Field(
        sa_column=Column(Integer, nullable=False)
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True))
    )
