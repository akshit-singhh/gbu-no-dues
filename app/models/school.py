# app/models/school.py

from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Integer, String

# Prevent circular imports
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.student import Student
    from app.models.application_stage import ApplicationStage

class School(SQLModel, table=True):
    __tablename__ = "schools"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )

    name: str = Field(
        sa_column=Column(String, nullable=False, unique=True)
    )

    code: Optional[str] = Field(
        default=None,
        sa_column=Column(String, unique=True, nullable=True)
    )

    # --------------------------------------------------------
    # RELATIONSHIPS
    # --------------------------------------------------------
    
    # Users assigned to this school (Deans, Office Staff)
    users: List["User"] = Relationship(back_populates="school")

    # Students enrolled in this school
    students: List["Student"] = Relationship(back_populates="school")
    
    # Approval Stages assigned to this school (Fixes the crash)
    stages: List["ApplicationStage"] = Relationship(back_populates="school")