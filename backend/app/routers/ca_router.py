from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import require_role
from app.models.audit_log import AuditLog
import datetime
import os

from app.services import ca_service

router = APIRouter(prefix="/ca", tags=["CA"])

@router.get("/status")
def get_ca_status(current_user=Depends(require_role("ADMIN"))):
    """
    Returns the current department CA/CSR keystore configuration status.
    """
    return ca_service.get_keystore_status()

@router.post("/csr/generate")
def generate_csr_endpoint(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN"))):
    """
    Generates a new department private key and Certificate Signing Request (CSR).
    """
    cn = payload.get("common_name", "govtender-department-authority").strip()
    org = payload.get("organization", "Dept. of Infrastructure").strip()
    country = payload.get("country", "IN").strip()

    if not cn or not org or not country:
        raise HTTPException(status_code=400, detail="common_name, organization, and country are required.")

    try:
        res = ca_service.generate_key_and_csr(cn, org, country)
        
        # Log action
        log = AuditLog(
            user_id=current_user.id,
            action="CSR_GENERATED",
            module="Identity",
            details=f"New signing key generated & CSR created. CN: {cn}, Org: {org}",
            timestamp=datetime.datetime.utcnow()
        )
        db.add(log)
        db.commit()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate CSR: {str(e)}")

@router.post("/certificate/upload")
def upload_certificate_endpoint(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN"))):
    """
    Uploads the CA-signed certificate PEM and compiles the PKCS12 keystore.
    """
    cert_pem = payload.get("certificate_pem", "").strip()
    if not cert_pem:
        raise HTTPException(status_code=400, detail="certificate_pem is required.")

    try:
        res = ca_service.import_ca_signed_certificate(cert_pem)
        
        log = AuditLog(
            user_id=current_user.id,
            action="CERTIFICATE_IMPORTED",
            module="Identity",
            details="CA-signed certificate imported successfully. Keystore local.p12 updated.",
            timestamp=datetime.datetime.utcnow()
        )
        db.add(log)
        db.commit()
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import certificate: {str(e)}")

@router.post("/mock-sign")
def mock_sign_endpoint(db: Session = Depends(get_db), current_user=Depends(require_role("ADMIN"))):
    """
    Mock signs the current CSR using a self-generated sandbox root CA.
    Makes local testing seamless without requiring an external CA.
    """
    try:
        res = ca_service.mock_sign_csr()
        
        log = AuditLog(
            user_id=current_user.id,
            action="CERTIFICATE_MOCK_SIGNED",
            module="Identity",
            details="Department CSR signed by Sandbox Root CA. local.p12 generated.",
            timestamp=datetime.datetime.utcnow()
        )
        db.add(log)
        db.commit()
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mock-sign CSR: {str(e)}")


@router.get("/certs/jwks.json")
def get_jwks():
    """
    Public JWKS endpoint exposing the department's public signing keys
    for Inji Verify signature verification.
    """
    status = ca_service.get_keystore_status()
    if not status.get("has_certificate"):
        return {"keys": []}

    try:
        from jose import jwk
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        cert_pem = status["certificate_pem"]
        cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        pub_key = cert.public_key()
        
        # Convert public key to PEM
        pub_pem = pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")

        # Construct Jose JWK
        # Alg can be RS256 for RSA keys
        jose_key = jwk.construct(pub_pem, algorithm="RS256")
        jwk_dict = jose_key.to_dict()
        
        # Add metadata headers
        jwk_dict["kid"] = "govtender-department-key"
        jwk_dict["use"] = "sig"
        jwk_dict["alg"] = "RS256"

        return {"keys": [jwk_dict]}
    except Exception as e:
        print(f"[JWKS ERROR] Failed to construct JWKS: {e}")
        return {"keys": []}
