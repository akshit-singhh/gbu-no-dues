from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class StageActionRequest(BaseModel):
    remarks: Optional[str] = None


class StageActionResponse(BaseModel):
    id: UUID
    application_id: UUID
    department_id: int
    status: str
    remarks: Optional[str]
    reviewer_id: Optional[UUID]

    class Config:
        from_attributes = True
        extra = "ignore"
