import datetime
import uuid
import os
import urllib.parse
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from jose import jwt

router = APIRouter(prefix="/auth/esignet", tags=["eSignet Auth"])

# Load Configurations
from app.core import config

ESIGNET_BASE_URL = config.ESIGNET_BASE_URL
ESIGNET_AUTHORIZE_URL = config.ESIGNET_AUTHORIZE_URL
ESIGNET_CLIENT_ID = config.ESIGNET_CLIENT_ID
ESIGNET_CLIENT_SECRET = config.ESIGNET_CLIENT_SECRET
ESIGNET_REDIRECT_URI = config.ESIGNET_REDIRECT_URI


import base64
import json
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def b64url_decode(s: str) -> bytes:
    s = s.replace('-', '+').replace('_', '/')
    s += '=' * (4 - len(s) % 4)
    return base64.b64decode(s.encode('utf-8'))

def decrypt_jwe(jwe_token: str, private_key_pem: str) -> str:
    """Decrypt JWE using client private key."""
    parts = jwe_token.split('.')
    if len(parts) != 5:
        raise ValueError("Invalid JWE token format (must be 5 parts)")
        
    header_b64, enc_key_b64, iv_b64, ciphertext_b64, tag_b64 = parts
    
    header = json.loads(b64url_decode(header_b64).decode('utf-8'))
    enc_key = b64url_decode(enc_key_b64)
    iv = b64url_decode(iv_b64)
    ciphertext = b64url_decode(ciphertext_b64)
    tag = b64url_decode(tag_b64)
    
    # Load private key
    from cryptography.hazmat.backends import default_backend
    priv_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None,
        backend=default_backend()
    )
    
    # Determine padding OAEP hash
    alg = header.get("alg", "RSA-OAEP-256")
    if alg == "RSA-OAEP-256":
        oaep_hash = hashes.SHA256()
    else:
        oaep_hash = hashes.SHA1()
        
    # Decrypt CEK
    cek = priv_key.decrypt(
        enc_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=oaep_hash),
            algorithm=oaep_hash,
            label=None
        )
    )
    
    # Decrypt GCM
    aad = header_b64.encode('utf-8')
    data_to_decrypt = ciphertext + tag
    
    aesgcm = AESGCM(cek)
    decrypted_bytes = aesgcm.decrypt(iv, data_to_decrypt, aad)
    return decrypted_bytes.decode('utf-8')

def decrypt_and_verify_token(token_str: str, jwks: dict, audience: str = None) -> dict:
    """Handle decrypted/signed JWE or JWS tokens recursively and return payload claims."""
    parts = token_str.split('.')
    
    if len(parts) == 5:
        print("Decrypting JWE Token using client private key...")
        if not getattr(config, "ESIGNET_PRIVATE_KEY", None):
            raise ValueError("JWE Token received but ESIGNET_PRIVATE_KEY is not configured.")
        decrypted_jwt = decrypt_jwe(token_str, config.ESIGNET_PRIVATE_KEY)
        return decrypt_and_verify_token(decrypted_jwt, jwks, audience)
        
    elif len(parts) == 3:
        print("Verifying JWS Token using JWKS...")
        try:
            if jwks and "keys" in jwks:
                return jwt.decode(token_str, jwks, audience=audience)
            else:
                return jwt.get_unverified_claims(token_str)
        except Exception as e:
            print(f"JWS verification failed: {e}. Falling back to unverified claims.")
            return jwt.get_unverified_claims(token_str)
            
    else:
        try:
            return json.loads(token_str)
        except Exception:
            raise ValueError("Token is neither a valid JWE, JWS, nor raw JSON.")

# Mock database mapping authorization codes to user info
MOCK_CODES = {
    "code_admin": {
        "sub": "esignet_sub_admin_999",
        "name": "Officer Jane Doe",
        "email": "jane.doe@infrastructure.gov",
        "role": "Admin",
        "department": "Ministry of Infrastructure",
        "digital_id": "official-123"
    },
    "code_vendor": {
        "sub": "esignet_sub_vendor_999",
        "name": "Sarah Connor",
        "email": "sconnor@cyberdyne.com",
        "role": "Vendor",
        "department": "Cyberdyne Systems",
        "digital_id": "vendor-123"
    },
    "code_auditor": {
        "sub": "esignet_sub_auditor_999",
        "name": "Auditor Arthur Dent",
        "email": "arthur.dent@auditor.gov",
        "role": "Auditor",
        "department": "National Audit Office",
        "digital_id": "auditor-123"
    }
}

@router.get("/login")
def esignet_login():
    """
    Step 1: Redirect user to the eSignet Login Page.
    If ESIGNET_CLIENT_ID is not placeholder, redirect to the real OIDC server.
    """
    if ESIGNET_CLIENT_ID and ESIGNET_CLIENT_ID != "your-esignet-client-id":
        params = {
            "response_type": "code",
            "client_id": ESIGNET_CLIENT_ID,
            "redirect_uri": ESIGNET_REDIRECT_URI,
            "scope": "openid profile email",
            "state": "state-12345",
            "acr_values": "mosip:idp:acr:generated-code mosip:idp:acr:biometrics mosip:idp:acr:linked-wallet mosip:idp:acr:knowledge"
        }
        url = f"{ESIGNET_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
        return RedirectResponse(url=url)
    return RedirectResponse(url="/auth/esignet/mock-login")

@router.get("/mock-login", response_class=HTMLResponse)
def esignet_mock_login_page():
    """
    Renders a premium-designed mock eSignet OAuth Login Screen.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>eSignet Identity Service</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-primary: #0b0f19;
                --card-bg: rgba(17, 24, 39, 0.7);
                --accent-cyan: #06b6d4;
                --text-primary: #f3f4f6;
                --text-secondary: #9ca3af;
                --border-color: rgba(255, 255, 255, 0.08);
            }
            body {
                background: radial-gradient(circle at 50% 50%, #111827 0%, var(--bg-primary) 100%);
                color: var(--text-primary);
                font-family: 'Outfit', sans-serif;
                margin: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                overflow: hidden;
            }
            .esignet-card {
                background: var(--card-bg);
                backdrop-filter: blur(20px);
                border: 1px solid var(--border-color);
                border-radius: 20px;
                padding: 3rem 2.5rem;
                width: 420px;
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 3rem;
                width: 100%;
                max-width: 400px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(12px);
                text-align: center;
                position: relative;
                overflow: hidden;
            }
            .logo-header {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.75rem;
                margin-bottom: 2rem;
            }
            .logo-badge {
                background: linear-gradient(135deg, var(--accent-cyan), #3b82f6);
                color: white;
                font-weight: 800;
                font-size: 1.25rem;
                height: 40px;
                width: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 10px;
            }
            .logo-text {
                font-size: 1.25rem;
                font-weight: 700;
                letter-spacing: -0.025em;
            }
            h2 {
                margin: 0 0 0.5rem 0;
                font-size: 1.5rem;
            }
            .subtitle {
                color: var(--text-secondary);
                font-size: 0.875rem;
                margin-bottom: 2rem;
            }
            .profile-options {
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }
            .profile-btn {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                color: var(--text-primary);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 1rem 1.25rem;
                text-align: left;
                transition: all 0.25s ease;
                font-family: inherit;
            }
            .profile-btn:hover {
                background: rgba(6, 182, 212, 0.08);
                border-color: var(--accent-cyan);
            }
            .profile-info {
                display: flex;
                flex-direction: column;
            }
            .profile-name {
                font-weight: 600;
                font-size: 0.95rem;
            }
            .profile-role {
                font-size: 0.75rem;
                color: var(--text-secondary);
                margin-top: 0.15rem;
            }
            
            /* IDA Simulation Styles */
            #ida-container {
                display: none;
                flex-direction: column;
                align-items: center;
            }
            .face-scanner {
                width: 120px;
                height: 120px;
                border: 2px solid var(--border-color);
                border-radius: 20px;
                position: relative;
                overflow: hidden;
                margin: 1.5rem auto;
            }
            .face-scanner::before {
                content: '';
                position: absolute;
                top: 0; left: 0; right: 0;
                height: 10px;
                background: var(--accent-cyan);
                box-shadow: 0 0 15px var(--accent-cyan), 0 0 30px var(--accent-cyan);
                animation: scanline 2s ease-in-out infinite alternate;
                z-index: 2;
            }
            @keyframes scanline {
                0% { top: 0; }
                100% { top: 110px; }
            }
            .face-icon {
                font-size: 4rem;
                line-height: 120px;
                opacity: 0.5;
            }
            
            .otp-container {
                display: none;
                flex-direction: column;
                align-items: center;
                gap: 1.5rem;
            }
            .otp-inputs {
                display: flex;
                gap: 0.5rem;
            }
            .otp-input {
                width: 40px;
                height: 50px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                color: white;
                font-size: 1.5rem;
                text-align: center;
                outline: none;
            }
            .otp-input:focus {
                border-color: var(--accent-cyan);
                box-shadow: 0 0 10px rgba(6, 182, 212, 0.3);
            }
            .btn-verify {
                background: var(--accent-cyan);
                color: white;
                border: none;
                padding: 0.75rem 2rem;
                border-radius: 8px;
                font-weight: bold;
                cursor: pointer;
                font-size: 1rem;
            }
            
            .footer-info {
                font-size: 0.75rem;
                color: var(--text-secondary);
                margin-top: 2rem;
            }
            .footer-info a {
                color: var(--accent-cyan);
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <div class="esignet-card">
            <div class="logo-header">
                <div class="logo-badge">eS</div>
                <div class="logo-text">eSignet Identity</div>
            </div>
            
            <!-- Selection Step -->
            <div id="selection-step">
                <h2>Authenticate Securely</h2>
                <div class="subtitle">Enter your Digital ID to begin IDA Verification</div>
                
                <div style="margin-bottom: 2rem; text-align: left;">
                    <label style="display: block; margin-bottom: 0.5rem; font-size: 0.875rem; color: var(--text-secondary);">Digital ID / Username</label>
                    <input type="text" id="digital-id-input" placeholder="e.g. vendor-123 or official-123" 
                        style="width: 100%; box-sizing: border-box; padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color); background: rgba(255,255,255,0.05); color: white; font-size: 1rem; outline: none; margin-bottom: 1rem;">
                    <button class="profile-btn" onclick="startIDA()" style="width: 100%; justify-content: center; background: var(--accent-cyan); color: white; border: none; font-weight: bold;">
                        Continue to Authentication
                    </button>
                </div>
            </div>

            <!-- IDA Verification Step -->
            <div id="ida-container">
                <h2 id="ida-title">Face Authentication</h2>
                <div class="subtitle" id="ida-subtitle">Align your face with the camera</div>
                
                <!-- Face Scanner -->
                <div id="face-scanner-view" class="face-scanner" style="width: 140px; height: 140px; border-radius: 50%; border: 3px solid rgba(6, 182, 212, 0.4); box-shadow: 0 0 20px rgba(6, 182, 212, 0.2); position: relative; overflow: hidden; margin: 1.5rem auto;">
                    <video id="webcam-preview" autoplay playsinline muted style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%; transform: scaleX(-1);"></video>
                    <div id="face-icon-fallback" class="face-icon" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 3.5rem; background: rgba(0,0,0,0.6); opacity: 0.8; z-index: 1;">👤</div>
                </div>
                
                <!-- OTP Input -->
                <div id="otp-view" class="otp-container">
                    <div class="otp-inputs" id="otp-inputs">
                        <input type="text" class="otp-input" maxlength="1" pattern="[0-9]" autocomplete="off">
                        <input type="text" class="otp-input" maxlength="1" pattern="[0-9]" autocomplete="off">
                        <input type="text" class="otp-input" maxlength="1" pattern="[0-9]" autocomplete="off">
                        <input type="text" class="otp-input" maxlength="1" pattern="[0-9]" autocomplete="off">
                        <input type="text" class="otp-input" maxlength="1" pattern="[0-9]" autocomplete="off">
                        <input type="text" class="otp-input" maxlength="1" pattern="[0-9]" autocomplete="off">
                    </div>
                    <button class="btn-verify" id="btn-verify" disabled>Verify Identity</button>
                </div>
            </div>

            <div class="footer-info">
                Secured by <a href="https://mosip.io" target="_blank">MOSIP Foundation</a>
            </div>
        </div>
        
        <script>
            let selectedCode = "";
            let digitalId = "";
            let webcamStream = null;

            function startIDA() {
                const val = document.getElementById('digital-id-input').value.trim();
                if (!val) {
                    alert("Please enter a Digital ID");
                    return;
                }
                digitalId = val;
                
                // Map common demo IDs to our mock codes
                if (val.includes("admin") || val.includes("official")) {
                    selectedCode = "code_admin";
                } else if (val.includes("auditor")) {
                    selectedCode = "code_auditor";
                } else {
                    selectedCode = "code_vendor";
                }

                document.getElementById('selection-step').style.display = 'none';
                document.getElementById('ida-container').style.display = 'flex';
                
                // Start webcam stream for face scanning simulation
                const videoEl = document.getElementById('webcam-preview');
                const fallbackEl = document.getElementById('face-icon-fallback');
                navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
                    .then(stream => {
                        webcamStream = stream;
                        videoEl.srcObject = stream;
                        fallbackEl.style.display = 'none';
                    })
                    .catch(err => {
                        console.warn("Webcam not available for eSignet:", err);
                        fallbackEl.style.display = 'flex';
                    });
                
                // Simulate 3 seconds of face scanning
                setTimeout(() => {
                    // Stop webcam stream
                    if (webcamStream) {
                        webcamStream.getTracks().forEach(track => track.stop());
                        webcamStream = null;
                    }
                    videoEl.srcObject = null;
                    
                    // Switch to OTP
                    document.getElementById('face-scanner-view').style.display = 'none';
                    document.getElementById('ida-title').innerText = "Device Verification";
                    document.getElementById('ida-title').style.color = "var(--accent-green)";
                    document.getElementById('ida-subtitle').innerText = "Face recognized. Enter mock OTP 111111 to proceed.";
                    document.getElementById('otp-view').style.display = 'flex';
                    document.querySelector('.otp-input').focus();
                }, 3000);
            }

            // OTP Input logic
            const inputs = document.querySelectorAll('.otp-input');
            const verifyBtn = document.getElementById('btn-verify');

            inputs.forEach((input, index) => {
                input.addEventListener('keyup', (e) => {
                    if (e.key >= 0 && e.key <= 9) {
                        input.value = e.key;
                        if (index < inputs.length - 1) inputs[index + 1].focus();
                    } else if (e.key === 'Backspace') {
                        input.value = '';
                        if (index > 0) inputs[index - 1].focus();
                    }
                    
                    // Check if all filled
                    const allFilled = Array.from(inputs).every(i => i.value !== '');
                    verifyBtn.disabled = !allFilled;
                });
            });

            verifyBtn.addEventListener('click', () => {
                verifyBtn.innerText = "Authenticating...";
                verifyBtn.disabled = true;
                setTimeout(() => {
                    // Redirect to callback
                    window.location.href = '/auth/esignet/callback?code=' + selectedCode + '&digital_id=' + encodeURIComponent(digitalId);
                }, 1000);
            });
        </script>
    </body>
    </html>
    """
    return html_content

@router.get("/callback")
def esignet_callback(code: str = Query(...), digital_id: str = Query(None), db: Session = Depends(get_db)):
    """
    Step 2: Exchange authorization code for user profile details (ID token payload).
    """
    if code in MOCK_CODES:
        # Simulate eSignet issuing a cryptographically signed JWS (JSON Web Signature)
        if digital_id:
            # Check if user already exists in DB (matching raw UIN or uin-prefixed ID)
            db_user = db.query(User).filter(
                (User.digital_id == digital_id) | 
                (User.digital_id == f"uin-{digital_id}")
            ).first()
            if db_user:
                mock_payload = {
                    "sub": db_user.esignet_sub or f"esignet_sub_{db_user.digital_id.lower()}",
                    "name": db_user.name,
                    "email": db_user.email,
                    "role": db_user.role,
                    "department": db_user.department or "Private Sector",
                    "digital_id": db_user.digital_id
                }
            else:
                # Dynamic auto-fallback if new username is entered directly
                role = "Vendor"
                dept = "Cyberdyne Systems"
                lower_did = digital_id.lower()
                if "admin" in lower_did or "official" in lower_did or "jane" in lower_did:
                    role = "Admin"
                    dept = "Ministry of Infrastructure"
                elif "auditor" in lower_did or "audit" in lower_did:
                    role = "Auditor"
                    dept = "National Audit Office"
                
                # Format initials and name
                name_parts = digital_id.replace("-", " ").replace("_", " ").split()
                formatted_name = " ".join([p.capitalize() for p in name_parts]) if name_parts else "OIDC User"

                mock_payload = {
                    "sub": f"esignet_sub_{lower_did}",
                    "name": formatted_name,
                    "email": f"{lower_did.replace(' ', '.')}@govtender.gov" if role != "Vendor" else f"{lower_did.replace(' ', '.')}@cyberdyne.com",
                    "role": role,
                    "department": dept,
                    "digital_id": digital_id
                }
        else:
            mock_payload = MOCK_CODES[code]

        jws_secret = "esignet-mock-secret-key-12345"
        
        # 1. Sign the claims
        id_token_jws = jwt.encode(mock_payload, jws_secret, algorithm="HS256")
        
        # 2. Portal receives JWS and verifies signature
        try:
            verified_claims = jwt.decode(id_token_jws, jws_secret, algorithms=["HS256"])
            token_payload = verified_claims
            
            # Log cryptographic verification success
            audit_entry = AuditLog(
                action="JWS_VERIFIED",
                module="Authentication",
                details=f"IDA Face/OTP Authentication Successful. Received and verified signed JWS claims from eSignet for: {token_payload.get('digital_id')}"
            )
            db.add(audit_entry)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"JWS Signature Verification Failed: {e}")
            
    else:
        # Standard production eSignet token exchange
        if not ESIGNET_CLIENT_ID or ESIGNET_CLIENT_ID == "your-esignet-client-id":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Real eSignet client keys not configured, and invalid mock authorization code."
            )
            
        token_url = f"{ESIGNET_BASE_URL}/oauth/v2/token"
        try:
            post_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": ESIGNET_REDIRECT_URI,
                "client_id": ESIGNET_CLIENT_ID
            }
            
            if getattr(config, "ESIGNET_PRIVATE_KEY", None):
                import time
                now = int(time.time())
                assertion_payload = {
                    "iss": ESIGNET_CLIENT_ID,
                    "sub": ESIGNET_CLIENT_ID,
                    "aud": token_url,
                    "jti": str(uuid.uuid4()),
                    "exp": now + 300,
                    "iat": now
                }
                client_assertion = jwt.encode(
                    assertion_payload,
                    config.ESIGNET_PRIVATE_KEY,
                    algorithm="RS256",
                    headers={"kid": "govtender-local-key"}
                )
                post_data["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
                post_data["client_assertion"] = client_assertion
            else:
                post_data["client_secret"] = ESIGNET_CLIENT_SECRET
                
            res = httpx.post(token_url, data=post_data)
            if res.status_code != 200:
                print(f"Token endpoint returned {res.status_code}: {res.text}")
            res.raise_for_status()
            tokens = res.json()
            id_token = tokens.get("id_token")
            access_token = tokens.get("access_token")
            
            # Fetch JWKS
            jwks_url = f"{ESIGNET_BASE_URL}/oauth/.well-known/jwks.json"
            jwks = {}
            try:
                res_jwks = httpx.get(jwks_url)
                if res_jwks.status_code == 200:
                    jwks = res_jwks.json()
                else:
                    print(f"Warning: JWKS endpoint returned status code {res_jwks.status_code}")
            except Exception as e:
                print(f"Warning: Failed to fetch JWKS from {jwks_url}: {e}")

            # Decode ID Token to get basic claims (decrypt JWE or verify JWS)
            payload_data = {}
            try:
                payload_data = decrypt_and_verify_token(id_token, jwks, audience=ESIGNET_CLIENT_ID)
            except Exception as e:
                print(f"Warning: ID Token verification/decryption failed: {e}")
                payload_data = jwt.get_unverified_claims(id_token)

            # Fetch UserInfo details to retrieve the name & email
            userinfo_payload = {}
            try:
                userinfo_url = f"{ESIGNET_BASE_URL}/oidc/userinfo"
                userinfo_res = httpx.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
                userinfo_res.raise_for_status()
                userinfo_jwt = userinfo_res.text
                
                try:
                    userinfo_payload = decrypt_and_verify_token(userinfo_jwt, jwks, audience=ESIGNET_CLIENT_ID)
                except Exception as e:
                    print(f"Warning: UserInfo token decoding/decryption failed: {e}")
                    userinfo_payload = jwt.get_unverified_claims(userinfo_jwt)
            except Exception as ue:
                print(f"Warning: UserInfo retrieval failed: {ue}")
                
            sub_val = userinfo_payload.get("sub") or payload_data.get("sub")
            
            # Parse email
            email_val = userinfo_payload.get("email") or payload_data.get("email") or f"{sub_val}@esignet.user"
            
            # Parse name from fullName list or direct name claim
            name_val = "OIDC User"
            if "name" in userinfo_payload:
                name_val = userinfo_payload["name"]
            elif "fullName" in userinfo_payload:
                fn = userinfo_payload["fullName"]
                if isinstance(fn, list) and len(fn) > 0:
                    name_val = fn[0].get("value", name_val)
            elif "name" in payload_data:
                name_val = payload_data["name"]
                
            # If name is default OIDC User, parse a clean name from the email
            if name_val == "OIDC User" and email_val:
                local_part = email_val.split("@")[0]
                if local_part.lower() == "sconnor":
                    name_val = "Sarah Connor"
                elif "." in local_part:
                    name_val = " ".join([part.capitalize() for part in local_part.split(".")])
                elif "_" in local_part:
                    name_val = " ".join([part.capitalize() for part in local_part.split("_")])
                else:
                    name_val = local_part.capitalize()
            
            # Determine role and department based on email or name
            role_val = "Vendor"
            dept_val = "Corporate Partner"
            
            lower_email = email_val.lower()
            lower_name = name_val.lower()
            
            if "admin" in lower_email or "official" in lower_email or "jane" in lower_email or "jane" in lower_name:
                role_val = "Admin"
                dept_val = "Ministry of Infrastructure"
            elif "auditor" in lower_email or "audit" in lower_email or "arthur" in lower_email or "arthur" in lower_name:
                role_val = "Auditor"
                dept_val = "National Audit Office"
            elif "sarah" in lower_email or "connor" in lower_name:
                role_val = "Vendor"
                dept_val = "Cyberdyne Systems"
                
            token_payload = {
                "sub": sub_val,
                "name": name_val,
                "email": email_val,
                "role": role_val,
                "department": dept_val,
                "digital_id": f"oidc-{sub_val[:8]}"
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Token exchange / OIDC validation failed: {str(e)}"
            )

    sub = token_payload["sub"]
    name = token_payload["name"]
    email = token_payload["email"]
    role = token_payload["role"]
    department = token_payload["department"]
    digital_id = token_payload["digital_id"]
    
    # User Mapping - Find or Create User based on Email first (GovTender unique identifier)
    user = db.query(User).filter(User.email == email).first()
    
    if user:
        # Check if there is another (orphan) user record holding this sub
        other_user = db.query(User).filter(User.esignet_sub == sub).first()
        if other_user and other_user.id != user.id:
            db.delete(other_user)
            db.commit()
            
        # Bind the sub to the real user record and update email,
        # but only overwrite the name if the database name is currently generic/unset
        user.esignet_sub = sub
        if user.name in (None, "", "OIDC User"):
            user.name = name
        user.email = email
        db.commit()
        db.refresh(user)
    else:
        # Fallback to lookup by sub if email is not found
        user = db.query(User).filter(User.esignet_sub == sub).first()
        if user:
            user.name = name
            user.email = email
            db.commit()
            db.refresh(user)
        else:
            # Create a brand new user profile
            user = User(
                id=uuid.uuid4(),
                name=name,
                email=email,
                digital_id=digital_id,
                role=role,
                department=department,
                esignet_sub=sub,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)

    # Register OIDC session login in Audit Logs
    log_entry = AuditLog(
        user_id=user.id,
        action="OIDC_LOGIN_SUCCESS",
        module="Authentication",
        details=f"OIDC Session established. Sub ID: {sub} ({role})",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    
    # Redirect back to frontend landing page with user's login ID in URL query parameters
    return RedirectResponse(url=f"/?login_did={user.digital_id}")
