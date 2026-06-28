import uuid
from sqlalchemy import Column, String, DateTime, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import datetime

class Tender(Base):
    __tablename__ = "tenders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_number = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    budget = Column(Numeric, nullable=True)
    department = Column(String, nullable=True)
    status = Column(String, nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    date = Column(DateTime, nullable=True)
    issuer = Column(String, nullable=True)
    category = Column(String, nullable=True)
    location = Column(String, nullable=True)
    public_key = Column(Text, nullable=True)
    private_key = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
