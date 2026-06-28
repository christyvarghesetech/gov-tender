import uuid
import datetime
import os
import httpx

# Load Configurations
from app.core import config

INJI_CERTIFY_BASE_URL = config.INJI_CERTIFY_BASE_URL
INJI_CERTIFY_API_KEY = config.INJI_CERTIFY_API_KEY
INJI_CERTIFY_TEMPLATE_ID = config.INJI_CERTIFY_TEMPLATE_ID

def issue_inji_verifiable_credential(tender_number: str, department: str, status_str: str) -> dict:
    """
    Calls Inji Certify API to issue a verifiable credential when configured,
    otherwise falls back to a simulated/mock credential payload.
    """
    if INJI_CERTIFY_API_KEY and INJI_CERTIFY_API_KEY != "your-inji-certify-api-key":
        try:
            # Prepare issuance call to actual Inji Certify service
            issuance_url = f"{INJI_CERTIFY_BASE_URL}/issuance/credentials"
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
            
            # Extract returned VC metadata
            return {
                "vc_id": data.get("id", f"urn:uuid:{uuid.uuid4()}"),
                "issuer_did": data.get("issuer", "did:inji:gov-tender-authority"),
                "credential_json": data.get("credential", body)
            }
        except Exception as e:
            # For reliability, log the issue and fail or fallback
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

