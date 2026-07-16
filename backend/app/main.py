from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.database import engine, Base, SessionLocal
from app.routers import users, tenders, credentials, auth_esignet, ca_router
from app.services.scheduler import start_scheduler, stop_scheduler
import datetime
import uuid
import os

# Import all models to ensure metadata registration
from app.models.user import User
from app.models.tender import Tender
from app.models.document import Document
from app.models.approval import Approval
from app.models.credential import Credential
from app.models.verification_log import VerificationLog
from app.models.audit_log import AuditLog
from app.models.support_ticket import SupportTicket
from app.models.notification import Notification
from app.models.identity_session import IdentitySession
from app.models.bid import Bid

# Auto-execute schema migrations
Base.metadata.create_all(bind=engine)

# Manual database migrations to add columns if they do not exist
from sqlalchemy import text
with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE tenders ADD COLUMN public_key TEXT;"))
    except Exception as e:
        print(f"Migration warning: public_key column check: {e}")
    try:
        conn.execute(text("ALTER TABLE tenders ADD COLUMN private_key TEXT;"))
    except Exception as e:
        print(f"Migration warning: private_key column check: {e}")


# Seed database on boot if empty
db = SessionLocal()
try:
    if db.query(User).count() == 0:
        # Seed users
        admin = User(
            id=uuid.uuid4(),
            name="Officer Jane Doe",
            email="jane.doe@infrastructure.gov",
            digital_id="official-123",
            role="Admin",
            department="Ministry of Infrastructure"
        )
        vendor = User(
            id=uuid.uuid4(),
            name="Sarah Connor",
            email="sconnor@cyberdyne.com",
            digital_id="vendor-123",
            role="Vendor",
            department="Cyberdyne Systems"
        )
        auditor = User(
            id=uuid.uuid4(),
            name="Auditor Arthur Dent",
            email="arthur.dent@auditor.gov",
            digital_id="auditor-123",
            role="Auditor",
            department="National Audit Office"
        )
        db.add_all([admin, vendor, auditor])
        db.commit()
        
    if db.query(Tender).count() == 0:
        # Seed tenders
        t1 = Tender(
            id=uuid.UUID("8f2a19cc-beef-4a30-8012-32aa8f2ab19c"),
            tender_number="GOV-2024-1187",
            title="National Highway Expansion Project - Route 4B",
            description="Construction and widening of the Highway Route 4B to a four-lane dual carriageway including bridges and modern tolling systems.",
            budget=45000000,
            department="Ministry of Public Works",
            status="verified",
            created_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            date=datetime.datetime(2026, 12, 31),
            issuer="Ministry of Public Works",
            category="Works",
            location="Route 4B"
        )
        t2 = Tender(
            id=uuid.UUID("3e7d921a-09ff-4112-921a-3e7d921a09ff"),
            tender_number="GOV-2025-4492",
            title="Solar Power Grid Installation Phase 2",
            description="Procurement and setup of a 150MW photovoltaic solar field with adjacent industrial battery storage systems.",
            budget=82000000,
            department="Ministry of Energy & Minerals",
            status="verified",
            created_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            date=datetime.datetime(2027, 6, 30),
            issuer="Ministry of Energy & Minerals",
            category="Energy",
            location="Solar Grid Phase 2"
        )
        t3 = Tender(
            id=uuid.uuid4(),
            tender_number="GOV-2026-1049",
            title="Metropolitan Water Filtration Upgrades",
            description="Installation of modern membrane bioreactors and automated chemical monitoring systems at the city filtration facility.",
            budget=9500000,
            department="Ministry of Public Works",
            status="pending",
            created_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            date=datetime.datetime(2026, 8, 15),
            issuer="Ministry of Public Works",
            category="Works",
            location="Metropolitan Water"
        )
        db.add_all([t1, t2, t3])
        
        # Add credentials matching initial tenders
        from app.services.qr_service import generate_credential_qr
        from app.services.inji_service import issue_inji_verifiable_credential
        
        inji_c1 = issue_inji_verifiable_credential(t1.tender_number, t1.department, "Approved")
        inji_c2 = issue_inji_verifiable_credential(t2.tender_number, t2.department, "Approved")
        
        c1 = Credential(
            id=uuid.uuid4(),
            credential_id="VC-8F2A-19CC-BEEF",
            tender_id=t1.id,
            issued_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            status="verified",
            qr_code_url=generate_credential_qr("VC-8F2A-19CC-BEEF"),
            vc_id=inji_c1["vc_id"],
            issuer_did=inji_c1["issuer_did"],
            credential_json=inji_c1["credential_json"]
        )
        c2 = Credential(
            id=uuid.uuid4(),
            credential_id="VC-3E7D-921A-09FF",
            tender_id=t2.id,
            issued_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            status="verified",
            qr_code_url=generate_credential_qr("VC-3E7D-921A-09FF"),
            vc_id=inji_c2["vc_id"],
            issuer_did=inji_c2["issuer_did"],
            credential_json=inji_c2["credential_json"]
        )
        db.add_all([c1, c2])
        
        # Seed notifications
        n1 = Notification(
            id=uuid.uuid4(),
            title="Document Verified Successfully",
            desc="Your 'ISO_9001_Quality_Certificate.pdf' has been approved by the central registry auditor.",
            time="2 hours ago",
            unread=True,
            owner_email="sconnor@cyberdyne.com"
        )
        n2 = Notification(
            id=uuid.uuid4(),
            title="Tender Application Approved",
            desc="Congratulations! Your bid proposal for Solar Power Grid Installation Phase 2 has been approved.",
            time="1 day ago",
            unread=True,
            owner_email="sconnor@cyberdyne.com"
        )
        db.add_all([n1, n2])
        db.commit()

    # Auto-repair credentials with missing VC data (due to schema/seed mismatch)
    empty_creds = db.query(Credential).filter((Credential.credential_json == None) | (Credential.vc_id == None)).all()
    if empty_creds:
        from app.services.inji_service import issue_inji_verifiable_credential
        for cred in empty_creds:
            tender = db.query(Tender).filter(Tender.id == cred.tender_id).first()
            if tender:
                inji_vc = issue_inji_verifiable_credential(tender.tender_number, tender.department or "Ministry of Infrastructure", "Approved")
                cred.vc_id = inji_vc["vc_id"]
                cred.issuer_did = inji_vc["issuer_did"]
                cred.credential_json = inji_vc["credential_json"]
                db.add(cred)
        db.commit()

    # Ensure all tenders have a keypair generated for cryptographic bidding
    from app.services.crypto_service import generate_tender_keypair
    tenders_without_keys = db.query(Tender).filter((Tender.public_key == None) | (Tender.private_key == None)).all()
    if tenders_without_keys:
        for tender_item in tenders_without_keys:
            priv, pub = generate_tender_keypair()
            tender_item.private_key = priv
            tender_item.public_key = pub
        db.commit()
except Exception as e:
    print(f"Warning: Database seeding skipped/failed: {e}")
finally:
    db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background scheduler on startup, stop gracefully on shutdown."""
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="GovTender API Portal", version="1.0.0", lifespan=lifespan)

# Mount uploads directory to serve generated QR codes
uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api")
app.include_router(tenders.router, prefix="/api/tenders")
app.include_router(credentials.router, prefix="/api")
app.include_router(ca_router.router, prefix="/api")
app.include_router(auth_esignet.router)

# Serve frontend landing page and assets at root
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
