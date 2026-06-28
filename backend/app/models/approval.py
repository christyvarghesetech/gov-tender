import uuid
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import datetime

class Approval(Base):
    __tablename__ = "approvals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String, nullable=True)
    remarks = Column(Text, nullable=True)
    approved_at = Column(DateTime, default=datetime.datetime.utcnow)
