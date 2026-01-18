# app/models/student.py

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4
from datetime import date, datetime
from typing import Optional, List
import uuid

# Forward references for type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.school import School
    from app.models.application import Application

class Student(SQLModel, table=True):
    __tablename__ = "students"

    id: uuid.UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )

    # ----------------------
    # Identity Fields
    # ----------------------
    enrollment_number: str = Field(sa_column=Column(String, nullable=False, unique=True))
    roll_number: str = Field(sa_column=Column(String, nullable=False, unique=True))
    full_name: str = Field(sa_column=Column(String, nullable=False))
    mobile_number: str = Field(sa_column=Column(String, nullable=False))
    email: str = Field(sa_column=Column(String, nullable=False, unique=True))

    # ----------------------
    # Foreign Keys
    # ----------------------
    school_id: int = Field(
        sa_column=Column(Integer, ForeignKey("schools.id"), nullable=False)
    )

    # ----------------------
    # Personal Details
    # ----------------------
    father_name: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    mother_name: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    gender: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    category: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    dob: Optional[date] = Field(default=None)
    
    permanent_address: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    domicile: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    # ----------------------
    # Hostel Info
    # ----------------------
    is_hosteller: Optional[bool] = Field(default=False)
    hostel_name: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    hostel_room: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))

    # ----------------------
    # Academic Details
    # ----------------------
    section: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    batch: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    admission_year: Optional[int] = Field(default=None)
    admission_type: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # ----------------------
    # Relationships
    # ----------------------
    user: Optional["User"] = Relationship(back_populates="student")
    school: Optional["School"] = Relationship(back_populates="students")
    
    
    applications: List["Application"] = Relationship(back_populates="student")