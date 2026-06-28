import uuid
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import datetime

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject = Column(String, nullable=False)
    category = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String, default="open")
    date = Column(String, default=lambda: datetime.datetime.utcnow().strftime("%Y-%m-%d"))
    owner_email = Column(String, nullable=False)
