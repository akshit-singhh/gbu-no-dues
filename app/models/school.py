# app/models/school.py

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Integer, String
from typing import Optional, List, TYPE_CHECKING

# Prevent circular imports
if TYPE_CHECKING:
    from app.models.student import Student

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
    # This matches the 'school' relationship in the Student model
    students: List["Student"] = Relationship(back_populates="school")