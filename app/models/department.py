# app/models/department.py

from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Integer, String

# Prevent circular imports
if TYPE_CHECKING:
    from app.models.user import User

class Department(SQLModel, table=True):
    __tablename__ = "departments"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )

    name: str = Field(
        sa_column=Column(String(128), nullable=False, unique=True)
    )

    # Changed from sequence_order to phase_number (2=Parallel, 3=Accounts)
    phase_number: int = Field(
        default=2,
        sa_column=Column(Integer, nullable=False, default=2)
    )

    # This matches: department = Relationship(back_populates="users") in User model
    users: List["User"] = Relationship(back_populates="department")