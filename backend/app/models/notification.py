import uuid
from sqlalchemy import Column, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    desc = Column(Text, nullable=False)
    time = Column(String, default="Just now")
    unread = Column(Boolean, default=True)
    owner_email = Column(String, nullable=False)
