# app/models/department.py

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Integer, String
from typing import Optional

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