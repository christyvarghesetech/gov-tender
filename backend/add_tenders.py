import uuid
import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.tender import Tender

def add_more_tenders():
    db: Session = SessionLocal()
    
    t4 = Tender(
        id=uuid.uuid4(),
        tender_number="GOV-2026-8812",
        title="National High-Speed Rail Network",
        description="Construction of the first phase of the national high-speed rail corridor connecting major metropolitan areas.",
        budget=1250000000,
        department="Ministry of Transportation",
        status="verified",
        created_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        date=datetime.datetime(2027, 11, 30),
        issuer="Ministry of Transportation",
        category="Infrastructure",
        location="National Corridor"
    )

    t5 = Tender(
        id=uuid.uuid4(),
        tender_number="GOV-2027-1105",
        title="Smart City AI Surveillance System",
        description="Implementation of AI-driven traffic and security surveillance cameras across the smart city pilot zone.",
        budget=32000000,
        department="Ministry of Home Affairs",
        status="verified",
        created_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        date=datetime.datetime(2027, 2, 28),
        issuer="Ministry of Home Affairs",
        category="Technology",
        location="Smart City Pilot Zone"
    )

    db.add_all([t4, t5])
    
    # Generate credentials for the verified tenders
    from app.services.qr_service import generate_credential_qr
    from app.services.inji_service import issue_inji_verifiable_credential
    from app.models.credential import Credential

    inji_c4 = issue_inji_verifiable_credential(t4.tender_number, t4.department, "Approved")
    inji_c5 = issue_inji_verifiable_credential(t5.tender_number, t5.department, "Approved")

    c4 = Credential(
        id=uuid.uuid4(),
        credential_id="VC-1B4A-99FF-ABCD",
        tender_id=t4.id,
        issued_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        status="verified",
        qr_code_url=generate_credential_qr("VC-1B4A-99FF-ABCD"),
        vc_id=inji_c4["vc_id"],
        issuer_did=inji_c4["issuer_did"],
        credential_json=inji_c4["credential_json"]
    )

    c5 = Credential(
        id=uuid.uuid4(),
        credential_id="VC-2C5B-88EE-BCDE",
        tender_id=t5.id,
        issued_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        status="verified",
        qr_code_url=generate_credential_qr("VC-2C5B-88EE-BCDE"),
        vc_id=inji_c5["vc_id"],
        issuer_did=inji_c5["issuer_did"],
        credential_json=inji_c5["credential_json"]
    )

    db.add_all([c4, c5])
    db.commit()
    print("Added 2 new verified tenders with credentials!")

if __name__ == "__main__":
    add_more_tenders()
