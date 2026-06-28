from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.credential import Credential
from app.models.tender import Tender
from app.models.approval import Approval
from app.models.document import Document
from app.models.notification import Notification
from app.models.support_ticket import SupportTicket
from app.models.audit_log import AuditLog
from app.models.verification_log import VerificationLog
from app.models.bid import Bid
from app.models.user import User
import uuid
import datetime
import random
import json
import io

from app.auth import require_role, get_current_user

router = APIRouter()

# --- VC QR VERIFICATION DESK ---
@router.get("/credentials/verify/{query}")
def verify_credential(query: str, db: Session = Depends(get_db)):
    # Strip any leading hashtag that users might copy-paste from UI
    clean_query = query.lstrip("#").strip()
    
    # Search in credentials or tenders
    credential = db.query(Credential).filter(
        (Credential.credential_id.ilike(clean_query)) | 
        (Credential.vc_id.ilike(clean_query))
    ).first()
    tender = None
    
    if credential:
        tender = db.query(Tender).filter(Tender.id == credential.tender_id).first()
    else:
        # Fallback 1: check if it matches tender_number
        tender = db.query(Tender).filter(Tender.tender_number.ilike(clean_query)).first()
        
        # Fallback 2: check if it's a bid reference (first 8 characters of Bid UUID)
        if not tender and len(clean_query) == 8:
            try:
                # We can't do a simple ilike on UUID, so we fetch all bids and check the hex manually 
                # (or since there shouldn't be many bids for a POC, this is acceptable, but let's query all bids)
                # Actually PostgreSQL allows casting UUID to text: cast(Bid.id, String).ilike(f"{clean_query}%")
                from sqlalchemy import cast, String
                bid = db.query(Bid).filter(cast(Bid.id, String).ilike(f"{clean_query}%")).first()
                if bid:
                    tender = db.query(Tender).filter(Tender.id == bid.tender_id).first()
            except Exception:
                pass
                
        if tender and tender.status == 'verified':
            credential = db.query(Credential).filter(Credential.tender_id == tender.id).first()

    # Log the verification attempt & perform integrity verification
    if credential:
        document = db.query(Document).filter(Document.tender_id == tender.id).first()
        document_integrity = "valid"
        
        if document:
            from app.services.integrity_service import verify_document_integrity
            integrity_res = verify_document_integrity(document)
            if integrity_res["status"] == "mismatched":
                document_integrity = "tampered"
            elif integrity_res["status"] == "missing_file":
                document_integrity = "missing"
        else:
            document_integrity = "missing"

        # Inji Verify validation
        from app.services.inji_verify_service import verify_vc_signature
        inji_res = verify_vc_signature(credential.credential_json)
        signature_valid = inji_res.get("signature_valid", False)
        issuer_valid = inji_res.get("issuer_valid", False)
        
        is_verified = (credential.status == "verified") and signature_valid and issuer_valid

        # Determine verification log outcome string
        if is_verified:
            if document_integrity == "tampered":
                log_result = "Credential Verified\nIntegrity Check Failed"
            else:
                log_result = "Credential Verified\nIntegrity Check Passed"
        else:
            log_result = "Credential Invalid or Revoked"

        new_log = VerificationLog(
            id=uuid.uuid4(),
            credential_id=credential.id,
            verified_by="Auditor Portal Client",
            verification_result=log_result,
            ip_address="127.0.0.1",
            verified_at=datetime.datetime.utcnow()
        )
        db.add(new_log)
        db.commit()
        
        return {
            "status": "verified" if is_verified else "revoked",
            "id": credential.credential_id,
            "tenderNo": tender.tender_number,
            "name": tender.title,
            "ministry": tender.department,
            "issuer": tender.issuer if hasattr(tender, 'issuer') and tender.issuer else "Dept. of Infrastructure",
            "date": tender.date.strftime("%Y-%m-%d") if tender.date else "",
            "budget": float(tender.budget) if tender.budget else 0.0,
            "desc": tender.description,
            "qr_code_url": credential.qr_code_url,
            "document_integrity": document_integrity,
            "vc_id": credential.vc_id,
            "issuer_did": credential.issuer_did,
            "credential_json": credential.credential_json,
            "signature_valid": signature_valid,
            "issuer_valid": issuer_valid
        }
    else:
        # Unknown hash log
        new_log = VerificationLog(
            id=uuid.uuid4(),
            credential_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            verified_by="Auditor Portal Client",
            verification_result="FAILURE",
            ip_address="127.0.0.1",
            verified_at=datetime.datetime.utcnow()
        )
        db.add(new_log)
        db.commit()
        
        if tender and tender.status == 'pending':
            return {
                "status": "pending",
                "tenderNo": tender.tender_number,
                "name": tender.title,
                "ministry": tender.department,
                "issuer": tender.issuer if hasattr(tender, 'issuer') and tender.issuer else "Dept. of Infrastructure",
                "date": tender.date.strftime("%Y-%m-%d") if tender.date else "",
                "budget": float(tender.budget) if tender.budget else 0.0,
                "desc": tender.description
            }
            
        raise HTTPException(status_code=404, detail="Revoked or Invalid Credential Hash.")

# --- APPLICATIONS / APPROVALS ---
@router.get("/applications")
def get_applications(db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN", "VENDOR", "AUDITOR"))):
    if current_user.role.lower() in ["admin", "auditor"]:
        bids = db.query(Bid).all()
    else:
        bids = db.query(Bid).filter(Bid.vendor_id == current_user.id).all()
        
    res = []
    for b in bids:
        tender = db.query(Tender).filter(Tender.id == b.tender_id).first()
        vendor = db.query(User).filter(User.id == b.vendor_id).first()
        
        is_closed = tender and tender.date and datetime.datetime.utcnow() > tender.date
        
        bid_value = None
        status = b.status
        
        if is_closed:
            try:
                from app.services.crypto_service import decrypt_with_private_key
                bid_value = float(decrypt_with_private_key(tender.private_key, b.encrypted_bid_value))
                if status == "locked":
                    b.status = "opened"
                    status = "opened"
                    db.add(b)
                    db.commit()
            except Exception as e:
                print(f"Decryption failed for bid {b.id.hex}: {e}")
                bid_value = 0.0
        else:
            status = "locked"
            
        res.append({
            "refNo": b.id.hex[:8].upper(),
            "id": b.id.hex,
            "tenderNo": tender.tender_number if tender else "GOV-UNKNOWN",
            "tenderName": tender.title if tender else "Unknown Tender",
            "bidValue": bid_value,
            "ciphertext": b.encrypted_bid_value,
            "signee": vendor.name if vendor else "Unknown Vendor",
            "email": vendor.email if vendor else "unknown@vendor.com",
            "status": status,
            "date": b.created_at.strftime("%Y-%m-%d") if b.created_at else ""
        })
    return res

@router.post("/applications")
def create_application(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_role("VENDOR"))):
    tender_no = payload.get("tenderNo")
    bid_val = payload.get("bidValue")
    signee = payload.get("signee")
    doc_id_val = payload.get("documentId")
    
    tender = db.query(Tender).filter(Tender.tender_number == tender_no).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender reference not found.")
        
    if tender.status != "verified":
        raise HTTPException(status_code=400, detail="Bids can only be submitted for verified tenders.")
        
    if tender.date and datetime.datetime.utcnow() > tender.date:
        raise HTTPException(status_code=400, detail="Tender closing date has passed. Bid submission closed.")
        
    # Auto-repair keys if missing
    if not tender.public_key or not tender.private_key:
        from app.services.crypto_service import generate_tender_keypair
        priv, pub = generate_tender_keypair()
        tender.private_key = priv
        tender.public_key = pub
        db.commit()
        
    # Encrypt the bid value using public key
    from app.services.crypto_service import encrypt_with_public_key
    encrypted_val = encrypt_with_public_key(tender.public_key, str(bid_val))
    
    # Resolve uploaded document details
    doc_path = None
    doc_hash = None
    if doc_id_val:
        try:
            doc_uuid = uuid.UUID(doc_id_val)
            doc = db.query(Document).filter(Document.id == doc_uuid).first()
            if doc:
                doc_path = doc.file_path
                doc_hash = doc.file_hash
        except ValueError:
            pass
            
    if not doc_path:
        doc = db.query(Document).filter(Document.tender_id == tender.id).order_by(Document.uploaded_at.desc()).first()
        if doc:
            doc_path = doc.file_path
            doc_hash = doc.file_hash
            
    bid_id = uuid.uuid4()
    new_bid = Bid(
        id=bid_id,
        tender_id=tender.id,
        vendor_id=current_user.id,
        encrypted_bid_value=encrypted_val,
        proposal_doc_path=doc_path,
        proposal_doc_hash=doc_hash,
        status="locked",
        created_at=datetime.datetime.utcnow()
    )
    db.add(new_bid)
    
    # Audit log
    log_entry = AuditLog(
        user_id=current_user.id,
        action="APPLICATION_SUBMITTED",
        module="Bidding",
        details=f"Bid proposal submitted for #{tender_no}. Bid value encrypted & cryptographically locked.",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    
    return {
        "refNo": bid_id.hex[:8].upper(),
        "id": bid_id.hex,
        "tenderNo": tender_no,
        "tenderName": tender.title,
        "bidValue": None,
        "signee": signee,
        "status": "locked"
    }

@router.patch("/applications/{app_id}")
def update_application_status(
    app_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("ADMIN"))
):
    try:
        app_uuid = uuid.UUID(app_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID format.")
        
    bid = db.query(Bid).filter(Bid.id == app_uuid).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Application/Bid not found.")
        
    tender = db.query(Tender).filter(Tender.id == bid.tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Associated tender not found.")
        
    is_closed = tender.date and datetime.datetime.utcnow() > tender.date
    if not is_closed:
        raise HTTPException(status_code=400, detail="Cannot process locked bids before the tender closing date has passed.")
        
    status = payload.get("status")
    if status not in ["approved", "rejected", "review", "opened"]:
        raise HTTPException(status_code=400, detail="Invalid status value.")
        
    bid.status = status
    
    # Notify bidder
    vendor = db.query(User).filter(User.id == bid.vendor_id).first()
    bidder_email = vendor.email if vendor else "unknown@vendor.com"
    
    status_label = "Approved & Verified" if status == "approved" else "Rejected"
    notif_title = f"Tender Application {status.capitalize()}"
    notif_desc = f"Your application for '{tender.title}' has been {status} by the official admin."
    
    new_notif = Notification(
        id=uuid.uuid4(),
        title=notif_title,
        desc=notif_desc,
        time="Just now",
        unread=True,
        owner_email=bidder_email
    )
    db.add(new_notif)
    
    # Audit log
    log_entry = AuditLog(
        user_id=current_user.id,
        action="APPLICATION_UPDATED",
        module="Bidding",
        details=f"Bid application {app_id[:8].upper()} for '{tender.title}' was {status} by Admin {current_user.name}.",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    db.refresh(bid)

    # Fire background email + in-app notification for the bidder
    if vendor:
        background_tasks.add_task(
            _notify_bid_status_bg,
            vendor_email=vendor.email,
            vendor_name=vendor.name,
            tender_title=tender.title,
            tender_no=tender.tender_number,
            new_status=status,
            admin_name=current_user.name if hasattr(current_user, 'name') else None,
        )

    return {"status": "success", "id": bid.id.hex, "application_status": bid.status}


def _notify_bid_status_bg(
    vendor_email: str,
    vendor_name: str,
    tender_title: str,
    tender_no: str,
    new_status: str,
    admin_name: str,
):
    """Background task helper: opens its own DB session for bid status notification."""
    from app.database import SessionLocal
    from app.services.notification_service import notify_bid_status_change
    db = SessionLocal()
    try:
        notify_bid_status_change(
            db=db,
            vendor_email=vendor_email,
            vendor_name=vendor_name,
            tender_title=tender_title,
            tender_no=tender_no,
            new_status=new_status,
            admin_name=admin_name,
        )
    except Exception as e:
        print(f"[NOTIFY ERROR] Bid status notification failed: {e}")
    finally:
        db.close()

# --- DOCUMENT MANAGEMENT ---
@router.get("/applications/{bid_id}/certificate")
def download_bid_certificate(
    bid_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("VENDOR", "ADMIN"))
):
    """
    Generate and stream a PDF Bid Award Certificate for an approved bid.
    Embeds: Vendor details, Tender info, Bid value, Signed VC, PixelPass QR code.
    """
    from fastapi.responses import StreamingResponse
    from app.services.certificate_service import generate_bid_certificate_pdf
    from app.services.inji_service import issue_inji_verifiable_credential

    try:
        bid_uuid = uuid.UUID(bid_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bid ID format.")

    bid = db.query(Bid).filter(Bid.id == bid_uuid).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found.")

    if bid.status != "approved":
        raise HTTPException(status_code=403, detail="Certificate is only available for approved bids.")

    # Authorisation: Vendor can only fetch their own certificate
    if hasattr(current_user, 'role') and current_user.role == "Vendor":
        if bid.vendor_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied.")

    tender = db.query(Tender).filter(Tender.id == bid.tender_id).first()
    vendor = db.query(User).filter(User.id == bid.vendor_id).first()

    if not tender or not vendor:
        raise HTTPException(status_code=404, detail="Associated tender or vendor not found.")

    # Decrypt bid value
    bid_value = 0.0
    try:
        from app.services.crypto_service import decrypt_with_private_key
        bid_value = float(decrypt_with_private_key(tender.private_key, bid.encrypted_bid_value))
    except Exception:
        pass

    # Get or issue a Verifiable Credential for this bid
    credential = db.query(Credential).filter(Credential.tender_id == tender.id).first()
    if credential:
        vc_id = credential.vc_id or credential.credential_id
        issuer_did = credential.issuer_did or "did:inji:gov-tender-authority"
        credential_json = credential.credential_json or {}
    else:
        # Issue a fresh bid-award VC
        inji_vc = issue_inji_verifiable_credential(
            tender_number=tender.tender_number,
            department=tender.department or "Government",
            status_str="Bid Awarded"
        )
        vc_id = inji_vc["vc_id"]
        issuer_did = inji_vc["issuer_did"]
        credential_json = inji_vc["credential_json"]

    # Enrich credential_json with bid details
    if isinstance(credential_json, dict):
        credential_json.setdefault("credentialSubject", {})
        credential_json["credentialSubject"].update({
            "bidReference": bid.id.hex[:8].upper(),
            "vendorName": vendor.name,
            "vendorEmail": vendor.email,
            "awardedBidValue": f"{bid_value:,.2f} INR",
            "tenderTitle": tender.title,
        })

    # Generate the PDF
    issue_date = bid.created_at.strftime("%B %d, %Y") if bid.created_at else datetime.datetime.utcnow().strftime("%B %d, %Y")

    pdf_bytes = generate_bid_certificate_pdf(
        bid_id=bid_id,
        bid_ref=bid.id.hex[:8].upper(),
        vendor_name=vendor.name,
        vendor_email=vendor.email,
        tender_title=tender.title,
        tender_no=tender.tender_number,
        department=tender.department or "Government",
        bid_value=bid_value,
        issue_date=issue_date,
        vc_id=vc_id,
        issuer_did=issuer_did,
        credential_json=credential_json,
    )

    # Audit log
    log_entry = AuditLog(
        user_id=current_user.id,
        action="BID_CERTIFICATE_DOWNLOADED",
        module="Procurement",
        details=f"Bid Award Certificate downloaded for Bid #{bid.id.hex[:8].upper()} by {vendor.name}.",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()

    filename = f"BidAwardCertificate_{tender.tender_number}_{bid.id.hex[:8].upper()}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/documents")
def get_documents(db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN", "VENDOR"))):
    docs = db.query(Document).all()
    res = []
    for d in docs:
        res.append({
            "id": d.id.hex,
            "name": d.file_name,
            "status": d.file_hash, # compatibility wrapper
            "expiryDate": d.uploaded_at.strftime("%Y-%m-%d") if d.uploaded_at else ""
        })
    return res

@router.post("/documents")
def upload_document(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_role("VENDOR"))):
    name = payload.get("name")
    expiry = payload.get("expiryDate")
    
    new_doc = Document(
        id=uuid.uuid4(),
        tender_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        file_name=name,
        file_path="uploads/" + name,
        file_hash="pending", # compatibility: stores status badge value ('verified', 'pending', 'expired')
        uploaded_at=datetime.datetime.strptime(expiry, "%Y-%m-%d") if expiry else datetime.datetime.utcnow()
    )
    db.add(new_doc)
    db.commit()
    return {"status": "success", "id": new_doc.id.hex, "name": name}

@router.delete("/documents/{id}")
def delete_document(id: str, db: Session = Depends(get_db), current_user=Depends(require_role("VENDOR"))):
    doc_uuid = uuid.UUID(id)
    doc = db.query(Document).filter(Document.id == doc_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.delete(doc)
    db.commit()
    return {"status": "success"}

# --- HELP & SUPPORT DESK ---
@router.get("/tickets")
def get_tickets(db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN", "VENDOR"))):
    tickets = db.query(SupportTicket).all()
    res = []
    for t in tickets:
        res.append({
            "id": t.id.hex[:8].upper(),
            "subject": t.subject,
            "category": t.category,
            "status": t.status,
            "date": t.date
        })
    return res

@router.post("/tickets")
def create_ticket(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_role("VENDOR"))):
    sub = payload.get("subject")
    cat = payload.get("category")
    msg = payload.get("message")
    
    new_ticket = SupportTicket(
        id=uuid.uuid4(),
        subject=sub,
        category=cat,
        message=msg,
        status="open",
        owner_email="vendor@cyberdyne.com"
    )
    db.add(new_ticket)
    db.commit()
    return {"status": "success", "id": new_ticket.id.hex[:8].upper()}

# --- NOTIFICATIONS INBOX ---
@router.get("/notifications")
def get_notifications(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    notifs = db.query(Notification).filter(Notification.owner_email == current_user.email).all()
    res = []
    for n in notifs:
        res.append({
            "id": n.id.hex,
            "title": n.title,
            "desc": n.desc,
            "time": n.time,
            "unread": n.unread
        })
    return res

@router.post("/notifications/read")
def mark_notifications_read(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db.query(Notification).filter(Notification.owner_email == current_user.email).update({Notification.unread: False})
    db.commit()
    return {"status": "success"}

@router.delete("/notifications/{id}")
def delete_notification(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        notif_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification ID format.")
        
    n = db.query(Notification).filter(Notification.id == notif_uuid, Notification.owner_email == current_user.email).first()
    if n:
        db.delete(n)
        db.commit()
    return {"status": "success"}

# --- SYSTEM AUDIT LOGS ---
@router.get("/logs")
def get_logs(db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN", "AUDITOR"))):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    res = []
    for l in logs:
        time_str = l.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        res.append({
            "time": time_str,
            "desc": l.details
        })
    return res

# --- CREDENTIAL REVOCATION ---
@router.patch("/credentials/{credential_id}/revoke")
def revoke_credential(
    credential_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("ADMIN"))
):
    """
    Revoke a verifiable credential by its credential_id string (e.g. VC-8F2A-19CC-BEEF).
    Sets both the credential and its associated tender to status='revoked'.
    """
    credential = db.query(Credential).filter(Credential.credential_id == credential_id).first()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found.")

    if credential.status == "revoked":
        raise HTTPException(status_code=400, detail="Credential is already revoked.")

    # Revoke the credential
    credential.status = "revoked"

    # Also update the tender status
    tender = db.query(Tender).filter(Tender.id == credential.tender_id).first()
    if tender:
        tender.status = "revoked"
        tender.updated_at = datetime.datetime.utcnow()

    # Audit trail
    log_entry = AuditLog(
        user_id=current_user.id,
        action="CREDENTIAL_REVOKED",
        module="Procurement",
        details=f"Credential {credential_id} revoked by Admin {current_user.name}. "
                f"Tender: {tender.tender_number if tender else 'N/A'}.",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)

    # Notify (optional — for audit clarity)
    notif = Notification(
        id=uuid.uuid4(),
        title="Credential Revoked",
        desc=f"The verifiable credential '{credential_id}' has been revoked by an administrator.",
        time="Just now",
        unread=True,
        owner_email=current_user.email
    )
    db.add(notif)
    db.commit()

    return {
        "status": "revoked",
        "credential_id": credential_id,
        "tender_number": tender.tender_number if tender else None,
        "message": "Credential and associated tender have been revoked successfully."
    }

# --- PDF CERTIFICATE ENDPOINT ---
@router.get("/credentials/{credential_id}/certificate")
def get_certificate_data(
    credential_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns full certificate data for PDF generation (no auth required — public credential lookup).
    """
    credential = db.query(Credential).filter(Credential.credential_id == credential_id).first()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found.")

    tender = db.query(Tender).filter(Tender.id == credential.tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Associated tender not found.")

    return {
        "credential_id": credential.credential_id,
        "vc_id": credential.vc_id,
        "issuer_did": credential.issuer_did,
        "status": credential.status,
        "issue_date": credential.issue_date.strftime("%B %d, %Y") if credential.issue_date else "",
        "qr_code_url": credential.qr_code_url,
        "tender_number": tender.tender_number,
        "tender_title": tender.title,
        "department": tender.department,
        "budget": float(tender.budget) if tender.budget else 0.0,
        "validity_date": tender.date.strftime("%B %d, %Y") if tender.date else "",
        "description": tender.description,
        "issuer_name": tender.issuer if hasattr(tender, "issuer") and tender.issuer else "Dept. of Infrastructure",
        "credential_json": credential.credential_json
    }
