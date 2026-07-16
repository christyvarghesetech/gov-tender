import uuid
import datetime
import os
import random
import httpx

# Load Configurations
from app.core import config
from app.services.qr_service import generate_credential_qr

INJI_CERTIFY_BASE_URL = config.INJI_CERTIFY_BASE_URL
INJI_CERTIFY_API_KEY = config.INJI_CERTIFY_API_KEY
INJI_CERTIFY_TEMPLATE_ID = config.INJI_CERTIFY_TEMPLATE_ID

def get_normalized_inji_url() -> str:
    """
    Ensures the Inji Certify base URL ends with '/v1/certify'.
    """
    base_url = INJI_CERTIFY_BASE_URL.strip().rstrip('/')
    if not base_url.endswith('/v1/certify'):
        base_url = f"{base_url}/v1/certify"
    return base_url

def issue_inji_preauthorized_offer(credential_config_id: str, claims: dict) -> dict:
    """
    Initiates the Pre-Authorized Code flow with Inji Certify.
    Returns:
        dict: {
            "credential_offer_uri": str,
            "qr_code_url": str,
            "tx_code": str,
            "pre_auth_code": str,
            "status": str ("active" / "mock")
        }
    """
    # Generate a random 4-digit transaction code for authorization
    tx_code = f"{random.randint(1000, 9999)}"
    
    # Try using real Inji Certify service
    if INJI_CERTIFY_API_KEY and INJI_CERTIFY_API_KEY != "your-inji-certify-api-key":
        try:
            base_url = get_normalized_inji_url()
            pre_auth_endpoint = f"{base_url}/pre-authorized-data"
            
            headers = {
                "Authorization": f"Bearer {INJI_CERTIFY_API_KEY}",
                "Content-Type": "application/json"
            }
            
            # Match PreAuthorizedRequest DTO fields in Inji Certify
            body = {
                "credential_configuration_id": credential_config_id,
                "claims": claims,
                "expires_in": 600,
                "tx_code": tx_code
            }
            
            print(f"[INJI SERVICE] Sending pre-auth request to: {pre_auth_endpoint}")
            res = httpx.post(pre_auth_endpoint, json=body, headers=headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            offer_uri = data.get("credentialOfferUri")
            if offer_uri:
                # Generate local QR code for the wallet to scan
                qr_url = generate_credential_qr(offer_uri)
                return {
                    "credential_offer_uri": offer_uri,
                    "qr_code_url": qr_url,
                    "tx_code": tx_code,
                    "status": "active"
                }
        except Exception as e:
            print(f"[INJI SERVICE WARNING] Real Inji Certify call failed: {e}. Falling back to mock...")

    # Mock Fallback Flow
    mock_offer_id = str(uuid.uuid4())
    mock_issuer = get_normalized_inji_url()
    
    # Construct a mock OpenID Credential Offer URI
    mock_offer_uri = f"openid-credential-offer://?credential_offer_uri=http://localhost:8080/api/ca/mock-offer/{mock_offer_id}"
    qr_url = generate_credential_qr(mock_offer_uri)
    
    return {
        "credential_offer_uri": mock_offer_uri,
        "qr_code_url": qr_url,
        "tx_code": tx_code,
        "status": "mock"
    }

def issue_inji_verifiable_credential(tender_number: str, department: str, status_str: str) -> dict:
    """
    Original function maintained for backwards compatibility.
    """
    if INJI_CERTIFY_API_KEY and INJI_CERTIFY_API_KEY != "your-inji-certify-api-key":
        try:
            base_url = get_normalized_inji_url()
            issuance_url = f"{base_url}/issuance/credentials"
            headers = {
                "Authorization": f"Bearer {INJI_CERTIFY_API_KEY}",
                "Content-Type": "application/json"
            }
            body = {
                "templateId": INJI_CERTIFY_TEMPLATE_ID,
                "credentialSubject": {
                    "tenderNumber": tender_number,
                    "department": department,
                    "status": status_str
                }
            }
            res = httpx.post(issuance_url, json=body, headers=headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            return {
                "vc_id": data.get("id", f"urn:uuid:{uuid.uuid4()}"),
                "issuer_did": data.get("issuer", "did:inji:gov-tender-authority"),
                "credential_json": data.get("credential", body)
            }
        except Exception as e:
            print(f"Error calling real Inji Certify service: {str(e)}")
            
    # Mock / Sandbox fallback
    mock_vc_id = f"urn:uuid:{uuid.uuid4()}"
    mock_issuer_did = "did:inji:gov-tender-authority"
    
    credential_json = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://schema.org"
        ],
        "id": mock_vc_id,
        "type": ["VerifiableCredential", "GovernmentTenderCredential"],
        "issuer": mock_issuer_did,
        "issuanceDate": datetime.datetime.utcnow().isoformat() + "Z",
        "credentialSubject": {
            "tenderNumber": tender_number,
            "department": department,
            "status": status_str
        }
    }
    
    return {
        "vc_id": mock_vc_id,
        "issuer_did": mock_issuer_did,
        "credential_json": credential_json
    }
