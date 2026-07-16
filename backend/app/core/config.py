import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:9605441280@localhost:5432/govtender")

# Server configuration
PORT = int(os.getenv("PORT", "8080"))

# eSignet (OIDC) Configurations
ESIGNET_BASE_URL = os.getenv("ESIGNET_BASE_URL", "https://esignet.collab.mosip.net").strip()
ESIGNET_AUTHORIZE_URL = os.getenv("ESIGNET_AUTHORIZE_URL", "http://localhost:3000/authorize").strip()
ESIGNET_CLIENT_ID = os.getenv("ESIGNET_CLIENT_ID", "your-esignet-client-id").strip()
ESIGNET_CLIENT_SECRET = os.getenv("ESIGNET_CLIENT_SECRET", "your-esignet-client-secret").strip()
ESIGNET_REDIRECT_URI = os.getenv("ESIGNET_REDIRECT_URI", "http://localhost:8080/api/auth/esignet/callback").strip()
ESIGNET_PRIVATE_KEY_PATH = os.getenv("ESIGNET_PRIVATE_KEY_PATH", "").strip()
ESIGNET_PRIVATE_KEY = os.getenv("ESIGNET_PRIVATE_KEY", "").strip()

if not ESIGNET_PRIVATE_KEY and ESIGNET_PRIVATE_KEY_PATH:
    # Resolve relative path to project root
    # Since config.py is in backend/app/core, project root is two levels up from backend/app
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    full_path = os.path.join(project_root, ESIGNET_PRIVATE_KEY_PATH)
    if os.path.exists(full_path):
        try:
            with open(full_path, "r") as f:
                ESIGNET_PRIVATE_KEY = f.read().strip()
        except Exception as e:
            print(f"Warning: Failed to load eSignet private key from path {full_path}: {e}")


# Inji Certify (Issuance) Configurations
INJI_CERTIFY_BASE_URL = os.getenv("INJI_CERTIFY_BASE_URL", "https://inji-certify.collab.mosip.net").strip()
INJI_CERTIFY_API_KEY = os.getenv("INJI_CERTIFY_API_KEY", "your-inji-certify-api-key").strip()
INJI_CERTIFY_TEMPLATE_ID = os.getenv("INJI_CERTIFY_TEMPLATE_ID", "GovernmentTenderCredential").strip()

# Inji Verify (Verification) Configurations
INJI_VERIFY_BASE_URL = os.getenv("INJI_VERIFY_BASE_URL", "https://inji-verify.collab.mosip.net").strip()
INJI_VERIFY_JWKS_URL = os.getenv("INJI_VERIFY_JWKS_URL", "https://inji-certify.collab.mosip.net/.well-known/jwks.json").strip()

# MOSIP IDA (Identity Authentication) Configurations
MOSIP_IDA_BASE_URL = os.getenv("MOSIP_IDA_BASE_URL", "https://ida.collab.mosip.net").strip()
MOSIP_IDA_CLIENT_ID = os.getenv("MOSIP_IDA_CLIENT_ID", "your-ida-client-id").strip()
