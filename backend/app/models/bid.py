import uuid
import datetime
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class Bid(Base):
    __tablename__ = "bids"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), nullable=False)
    encrypted_bid_value = Column(Text, nullable=False)
    proposal_doc_path = Column(Text, nullable=True)
    proposal_doc_hash = Column(String, nullable=True)
    status = Column(String, default="locked") # 'locked', 'opened', 'approved', 'rejected'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
