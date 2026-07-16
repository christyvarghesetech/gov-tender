from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.tender import Tender
from app.models.credential import Credential
from app.models.audit_log import AuditLog
from app.models.document import Document
import uuid
import datetime
import random
import os
import hashlib

from app.auth import require_role
from app.core import config

router = APIRouter()

@router.get("")
def get_tenders(db: Session = Depends(get_db)):
    tenders = db.query(Tender).all()
    res = []
    for t in tenders:
        res.append({
            "id": t.id.hex if t.status == 'verified' else t.tender_number, # compatibility with original front
            "tenderNo": t.tender_number,
            "name": t.title,
            "ministry": t.department,
            "issuer": t.issuer if hasattr(t, 'issuer') and t.issuer else "Dept. of Infrastructure",
            "date": t.date.strftime("%Y-%m-%d") if t.date else "",
            "budget": float(t.budget) if t.budget else 0.0,
            "desc": t.description,
            "category": t.category if hasattr(t, 'category') and t.category else "Infrastructure",
            "location": t.location if hasattr(t, 'location') and t.location else "New York",
            "status": t.status
        })
    return res

@router.post("")
def create_tender(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN"))):
    # Payload may use title/name, description/desc, department/ministry
    title = payload.get("name") or payload.get("title")
    desc = payload.get("desc") or payload.get("description")
    ministry = payload.get("ministry") or payload.get("department")
    budget = payload.get("budget")
    date_str = payload.get("date")
    
    # Generate random tender number
    random_no = random.randint(1000, 9999)
    tender_no = f"GOV-2026-{random_no}"
    
    date_val = None
    if date_str:
        try:
            date_val = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            pass
            
    # Dummy admin ID for mock operations
    created_by_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    
    # Generate RSA keys for cryptographic bidding lock
    from app.services.crypto_service import generate_tender_keypair
    priv, pub = generate_tender_keypair()

    new_tender = Tender(
        id=uuid.uuid4(),
        tender_number=tender_no,
        title=title,
        description=desc,
        budget=budget,
        department=ministry,
        status="pending",
        created_by=created_by_id,
        public_key=pub,
        private_key=priv,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    # Set dynamic fields if they exist in schema
    setattr(new_tender, 'issuer', payload.get("issuer", "Dept. of Infrastructure"))
    setattr(new_tender, 'category', payload.get("category", "Infrastructure"))
    setattr(new_tender, 'location', payload.get("location", "New York"))
    setattr(new_tender, 'date', date_val)

    db.add(new_tender)
    
    # Audit log
    log_entry = AuditLog(
        action="TENDER_DRAFT_CREATED",
        module="Procurement",
        details=f"Tender draft created: {title} (#{tender_no})",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    db.refresh(new_tender)
    
    return {
        "id": new_tender.id.hex,
        "tenderNo": new_tender.tender_number,
        "name": new_tender.title,
        "status": new_tender.status
    }

@router.delete("/{tenderNo}")
def delete_tender(tenderNo: str, db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN"))):
    tender = db.query(Tender).filter(Tender.tender_number == tenderNo).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found.")
        
    db.delete(tender)
    
    log_entry = AuditLog(
        action="TENDER_DELETED",
        module="Procurement",
        details=f"Tender deleted: #{tenderNo}",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    return {"status": "success", "tenderNo": tenderNo}

@router.post("/{tenderNo}/sign")
def sign_tender(tenderNo: str, background_tasks: BackgroundTasks, payload: dict = None, db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN"))):
    tender = db.query(Tender).filter(Tender.tender_number == tenderNo).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found.")
        
    # Parse issued_by from payload if available
    issued_by_val = uuid.UUID("00000000-0000-0000-0000-000000000000")
    if payload and "issued_by" in payload:
        try:
            issued_by_val = uuid.UUID(payload["issued_by"])
        except (ValueError, TypeError, AttributeError):
            pass

    # Verify OTP code
    if not payload or "otp" not in payload:
        raise HTTPException(status_code=400, detail="OTP Code required for MOSIP IDA verification.")
    
    otp_code = str(payload.get("otp")).strip()
    
    # Load IDA configurations
    mosip_ida_base = config.MOSIP_IDA_BASE_URL
    mosip_ida_client = config.MOSIP_IDA_CLIENT_ID
    
    is_authenticated = False
    
    if mosip_ida_client and mosip_ida_client != "your-ida-client-id":
        try:
            import httpx
            ind_id = current_user.digital_id if hasattr(current_user, 'digital_id') else "official-VID"
            if ind_id.startswith("uin-"):
                ind_id = ind_id[4:]
                
            # Call actual MOSIP IDA Authentication API
            ida_url = f"{mosip_ida_base}/idauth/v1/auth/{mosip_ida_client}"
            res = httpx.post(ida_url, json={
                "id": "mosip.identity.auth",
                "version": "1.0",
                "requestTime": datetime.datetime.utcnow().isoformat() + "Z",
                "request": {
                    "otp": otp_code,
                    "individualId": ind_id,
                    "individualIdType": "UIN"
                }
            }, timeout=8)
            
            res.raise_for_status()
            auth_data = res.json()
            is_authenticated = auth_data.get("response", {}).get("authStatus", False)
            if not is_authenticated:
                raise HTTPException(status_code=400, detail="MOSIP IDA OTP verification failed.")
        except Exception as e:
            # Fallback to local sandbox code validation if community sandbox fails to respond
            if hasattr(e, 'status_code') and e.status_code == 400:
                raise e
            print(f"Error connecting to real MOSIP IDA service, falling back to mock: {str(e)}")
            is_authenticated = (otp_code == "123456")
    else:
        is_authenticated = (otp_code == "123456")
        
    if not is_authenticated:
        raise HTTPException(status_code=400, detail="Invalid OTP code. MOSIP IDA authentication failed.")
        
    # Store dynamic identity session on approval
    from app.models.identity_session import IdentitySession
    session_id = uuid.uuid4()
    new_session = IdentitySession(
        id=session_id,
        user_id=current_user.id if hasattr(current_user, 'id') else None,
        login_time=datetime.datetime.utcnow(),
        token_reference=f"IDA-REF-{session_id.hex[:6].upper()}"
    )
    db.add(new_session)

    # Generate VC hex parts
    hex_code = "".join([random.choice("0123456789ABCDEF") for _ in range(8)])
    vc_id = f"VC-8F2A-{hex_code[:4]}-{hex_code[4:]}"
    
    # Set status verified
    tender.status = "verified"
    tender.updated_at = datetime.datetime.utcnow()
            
    # Call Inji Certify API (simulated) to issue Verifiable Credential
    from app.services.inji_service import issue_inji_verifiable_credential
    inji_vc = issue_inji_verifiable_credential(
        tender_number=tender.tender_number,
        department=tender.department or "Finance",
        status_str="Approved"
    )

    # Generate QR Code
    from app.services.qr_service import generate_credential_qr
    qr_url = generate_credential_qr(vc_id)

    # Save credential
    new_cred = Credential(
        id=uuid.uuid4(),
        credential_id=vc_id,
        tender_id=tender.id,
        issued_by=issued_by_val,
        issue_date=datetime.datetime.utcnow(),
        status="verified",
        qr_code_url=qr_url,
        vc_id=inji_vc["vc_id"],
        issuer_did=inji_vc["issuer_did"],
        credential_json=inji_vc["credential_json"]
    )
    db.add(new_cred)
    
    log_entry = AuditLog(
        action="TENDER_VC_ISSUED",
        module="Procurement",
        details=f"Tender signed & Verifiable Credential issued: #{tenderNo}. Cred ID: {vc_id}",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()

    # Fire background notifications to all vendors about the newly verified tender
    deadline_str = tender.date.strftime("%B %d, %Y") if tender.date else "TBD"
    category = tender.category if hasattr(tender, 'category') and tender.category else "Infrastructure"
    background_tasks.add_task(
        _notify_new_tender_bg,
        tender_title=tender.title,
        tender_no=tender.tender_number,
        department=tender.department or "Government",
        budget=float(tender.budget or 0),
        deadline=deadline_str,
        category=category,
    )

    return {"status": "verified", "credential_id": vc_id, "id": vc_id}


def _notify_new_tender_bg(
    tender_title: str,
    tender_no: str,
    department: str,
    budget: float,
    deadline: str,
    category: str,
):
    """Background task helper: opens its own DB session to dispatch notifications."""
    from app.database import SessionLocal
    from app.services.notification_service import notify_new_tender
    db = SessionLocal()
    try:
        notify_new_tender(
            db=db,
            tender_title=tender_title,
            tender_no=tender_no,
            department=department,
            budget=budget,
            deadline=deadline,
            category=category,
        )
    except Exception as e:
        print(f"[NOTIFY ERROR] New tender notification failed: {e}")
    finally:
        db.close()

@router.post("/{id}/upload")
async def upload_tender_document(id: str, file: UploadFile = File(...), db: Session = Depends(get_db), current_user=Depends(require_role("VENDOR", "ADMIN"))):
    # Look up the tender by either UUID or tender number
    tender = None
    try:
        tender_uuid = uuid.UUID(id)
        tender = db.query(Tender).filter(Tender.id == tender_uuid).first()
    except ValueError:
        pass
        
    if not tender:
        tender = db.query(Tender).filter(Tender.tender_number == id).first()
        
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Read the file and compute its SHA-256 hash
    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()

    # Prepare upload directory
    UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_path_on_disk = os.path.join(UPLOAD_DIR, file.filename)
    
    # Store the PDF on the filesystem
    with open(file_path_on_disk, "wb") as f:
        f.write(contents)

    # Save details to database
    new_doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        file_name=file.filename,
        file_path=f"uploads/{file.filename}",
        file_hash=file_hash,
        uploaded_at=datetime.datetime.utcnow()
    )
    db.add(new_doc)
    
    # Register action in audit log
    log_entry = AuditLog(
        action="TENDER_DOCUMENT_UPLOADED",
        module="Procurement",
        details=f"Document '{file.filename}' uploaded for tender #{tender.tender_number}",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    db.refresh(new_doc)
    
    return {
        "status": "success",
        "document_id": new_doc.id.hex,
        "tender_id": new_doc.tender_id.hex,
        "file_name": new_doc.file_name,
        "file_path": new_doc.file_path,
        "file_hash": new_doc.file_hash,
        "uploaded_at": new_doc.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")
    }

@router.post("/{tenderNo}/face-auth")
def face_auth_verify(
    tenderNo: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("ADMIN"))
):
    """
    Validates a face biometric scan result before tender signing.
    Accepts confidence score from the frontend camera module.
    In production, this would call MOSIP IDA Biometric Auth API.
    """
    confidence = payload.get("confidence", 0.0)
    face_data = payload.get("face_data", "")

    # Validate tender exists
    tender = db.query(Tender).filter(Tender.tender_number == tenderNo).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found.")

    CONFIDENCE_THRESHOLD = 0.80

    # --- MOSIP IDA Biometric Auth (production path) ---
    mosip_ida_client = config.MOSIP_IDA_CLIENT_ID
    is_authenticated = False

    if mosip_ida_client and mosip_ida_client != "your-ida-client-id":
        try:
            ind_id = current_user.digital_id if hasattr(current_user, "digital_id") else "official-VID"
            if ind_id.startswith("uin-"):
                ind_id = ind_id[4:]
                
            ida_url = f"{config.MOSIP_IDA_BASE_URL}/idauth/v1/auth/{mosip_ida_client}"
            res = httpx.post(ida_url, json={
                "id": "mosip.identity.auth",
                "version": "1.0",
                "requestTime": datetime.datetime.utcnow().isoformat() + "Z",
                "request": {
                    "biometrics": [{"data": face_data, "type": "Face"}],
                    "individualId": ind_id,
                    "individualIdType": "UIN"
                }
            }, timeout=8)
            res.raise_for_status()
            auth_data = res.json()
            is_authenticated = auth_data.get("response", {}).get("authStatus", False)
        except Exception as e:
            print(f"MOSIP IDA face-auth call failed, falling back to mock: {str(e)}")
            is_authenticated = float(confidence) >= CONFIDENCE_THRESHOLD
    else:
        # Sandbox/mock: accept if confidence meets threshold
        is_authenticated = float(confidence) >= CONFIDENCE_THRESHOLD

    if not is_authenticated:
        raise HTTPException(
            status_code=400,
            detail=f"Face authentication failed. Confidence {confidence:.0%} below required threshold."
        )

    # Log the biometric authentication
    log_entry = AuditLog(
        user_id=current_user.id,
        action="FACE_AUTH_PASSED",
        module="Identity",
        details=f"Face biometric authentication passed for tender #{tenderNo}. "
                f"Officer: {current_user.name}. Confidence: {float(confidence)*100:.1f}%.",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()

    # Return a short-lived face-verified session token
    session_token = f"FACE-{uuid.uuid4().hex[:12].upper()}"
    return {
        "face_verified": True,
        "confidence": confidence,
        "session_token": session_token,
        "message": "Face authentication successful. Proceed to OTP verification."
    }
