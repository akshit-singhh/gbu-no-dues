from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Integer, String
from typing import Optional


class Department(SQLModel, table=True):
    __tablename__ = "departments"

    # Primary Key must be ONLY inside sa_column
    id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )

    name: str = Field(
        sa_column=Column(String(128), nullable=False, unique=True)
    )

    sequence_order: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True)
    )
