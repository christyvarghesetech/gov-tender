import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import datetime

class IdentitySession(Base):
    __tablename__ = "identity_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    login_time = Column(DateTime, default=datetime.datetime.utcnow)
    token_reference = Column(String, nullable=True)
