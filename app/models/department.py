# app/models/department.py

from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Integer, String

# Prevent circular imports
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.student import Student
    from app.models.application_stage import ApplicationStage

class Department(SQLModel, table=True):
    __tablename__ = "departments"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )

    name: str = Field(
        sa_column=Column(String(128), nullable=False, unique=True)
    )

    # Stable Identifier (e.g., 'CSE', 'LIB', 'ACC')
    code: str = Field(
        sa_column=Column(String(20), nullable=False, unique=True, index=True)
    )

    # 1 = Academic (HOD), 2 = Parallel (Library/Sports), 3 = Accounts
    phase_number: int = Field(
        default=2,
        sa_column=Column(Integer, nullable=False, default=2)
    )

    # ----------------------
    # Relationships
    # ----------------------
    
    # Users linked to this department (e.g. HODs, Librarians)
    users: List["User"] = Relationship(back_populates="department")

    # Students belonging to this academic department (e.g. CSE Students)
    students: List["Student"] = Relationship(back_populates="department")
    
    # Stages assigned to this department
    stages: List["ApplicationStage"] = Relationship(back_populates="department")