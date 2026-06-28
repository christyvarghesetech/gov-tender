import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import datetime

class VerificationLog(Base):
    __tablename__ = "verification_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    credential_id = Column(UUID(as_uuid=True), nullable=False)
    verified_by = Column(String, nullable=True)
    verification_result = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    verified_at = Column(DateTime, default=datetime.datetime.utcnow)
