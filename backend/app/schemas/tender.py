from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class TenderBase(BaseModel):
    tender_number: str
    title: str
    description: Optional[str] = None
    budget: Optional[float] = None
    department: Optional[str] = None
    status: Optional[str] = "pending"

class TenderCreate(TenderBase):
    created_by: UUID

class TenderResponse(TenderBase):
    id: UUID
    created_by: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
