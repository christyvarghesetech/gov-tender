import uuid
from sqlalchemy import Column, String, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
import datetime

class Credential(Base):
    __tablename__ = "credentials"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    credential_id = Column(String, nullable=False)
    tender_id = Column(UUID(as_uuid=True), nullable=False)
    issued_by = Column(UUID(as_uuid=True), nullable=False)
    issue_date = Column(DateTime, default=datetime.datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)
    qr_code_url = Column(Text, nullable=True)
    vc_id = Column(String, nullable=True)
    issuer_did = Column(String, nullable=True)
    credential_json = Column(JSONB, nullable=True)
