# app/models/user.py

from enum import Enum
from typing import Optional, TYPE_CHECKING, List
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# Prevent circular imports
if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.application_stage import ApplicationStage

class UserRole(str, Enum):
    # System Roles
    SuperAdmin = "super_admin"   # System Owner
    Admin = "admin"              # Generic Admin
    Student = "student"          # Students
    
    # Generic Staff Role
    Staff = "staff"

    # Specific Authority Roles (For No Dues Approvals)
    Dean = "dean"                # Dean of School
    HOD = "hod"                  # Head of Department
    Library = "library"          # Library Staff
    Hostel = "hostel"            # Hostel Warden
    Lab = "lab"                  # Lab In-charge
    Account = "account"          # Accounts Department
    Sports = "sports"            # Sports Officer
    CRC = "crc"                  # Corporate Resource Center

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )

    name: str = Field(sa_column=Column(String, nullable=False))
    email: str = Field(sa_column=Column(String, unique=True, index=True, nullable=False))
    password_hash: str = Field(sa_column=Column(String, nullable=False))
    
    # default to Student, but can be any role
    role: UserRole = Field(sa_column=Column(String, default=UserRole.Student.value))
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # --------------------------------------------------------
    # FOREIGN KEYS
    # --------------------------------------------------------
    # Link to Student Profile
    student_id: Optional[UUID] = Field(default=None, foreign_key="students.id")

    # Routing Foreign Keys
    school_id: Optional[int] = Field(default=None, foreign_key="schools.id")
    department_id: Optional[int] = Field(default=None, foreign_key="departments.id")

    # --------------------------------------------------------
    #  PASSWORD RESET
    # --------------------------------------------------------
    # These match the columns you added to your database
    otp_code: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    otp_expires_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))

    # --------------------------------------------------------
    # RELATIONSHIPS
    # --------------------------------------------------------
    student: Optional["Student"] = Relationship(back_populates="user")
    
    # Optional: Relationship to stages verified by this user
    verified_stages: List["ApplicationStage"] = Relationship(back_populates="verifier")