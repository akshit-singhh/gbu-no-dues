# app/models/user.py

from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import DateTime, ForeignKey, String  # Added String
from sqlalchemy import Enum as PGEnum
from datetime import datetime
import uuid
from enum import Enum
from typing import Optional

class UserRole(str, Enum):
    Admin = "Admin"
    HOD = "HOD"
    Staff = "Staff"    # any department-level staff (Library, Hostel, Accounts, etc.)
    Student = "Student"

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )

    name: str = Field(nullable=False)
    email: str = Field(nullable=False, index=True, unique=True)
    password_hash: str = Field(nullable=False)

    # role saved as a Postgres ENUM but only the stable values above
    role: UserRole = Field(
        sa_column=Column(PGEnum(UserRole, name="user_role"), nullable=False)
    )

    # department_id is a foreign key to departments table (dynamic list of departments)
    department_id: Optional[int] = Field(
        default=None,
        sa_column=Column(ForeignKey("departments.id"), nullable=True)
    )

    student_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=True)
    )

    # --- New Fields for Forgot Password Feature ---
    otp_code: Optional[str] = Field(
        default=None, 
        sa_column=Column(String, nullable=True)
    )
    otp_expires_at: Optional[datetime] = Field(
        default=None, 
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )