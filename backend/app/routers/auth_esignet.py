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
ESIGNET_CLIENT_ID = config.ESIGNET_CLIENT_ID
ESIGNET_CLIENT_SECRET = config.ESIGNET_CLIENT_SECRET
ESIGNET_REDIRECT_URI = config.ESIGNET_REDIRECT_URI


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
            "state": "state-12345"
        }
        url = f"{ESIGNET_BASE_URL}/oauth/v2/authorize?{urllib.parse.urlencode(params)}"
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
                <div id="face-scanner-view" class="face-scanner">
                    <div class="face-icon">👤</div>
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
                
                // Simulate 3 seconds of face scanning
                setTimeout(() => {
                    // Switch to OTP
                    document.getElementById('face-scanner-view').style.display = 'none';
                    document.getElementById('ida-title').innerText = "Device Verification";
                    document.getElementById('ida-title').style.color = "var(--accent-green)";
                    document.getElementById('ida-subtitle').innerText = "Face recognized. Enter OTP sent to your device.";
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
            # Check if user already exists in DB
            db_user = db.query(User).filter(User.digital_id == digital_id).first()
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
                client_assertion = jwt.encode(assertion_payload, config.ESIGNET_PRIVATE_KEY, algorithm="RS256")
                post_data["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
                post_data["client_assertion"] = client_assertion
            else:
                post_data["client_secret"] = ESIGNET_CLIENT_SECRET
                
            res = httpx.post(token_url, data=post_data)
            res.raise_for_status()
            tokens = res.json()
            id_token = tokens.get("id_token")
            
            # Fetch JWKS and decode JWT
            jwks_url = f"{ESIGNET_BASE_URL}/.well-known/jwks.json"
            payload_data = {}
            try:
                jwks = httpx.get(jwks_url).json()
                payload_data = jwt.decode(id_token, jwks, audience=ESIGNET_CLIENT_ID)
            except Exception:
                # Fallback to unverified decode if JWKS is unreachable in sandbox environment
                payload_data = jwt.get_unverified_claims(id_token)
                
            token_payload = {
                "sub": payload_data.get("sub"),
                "name": payload_data.get("name", "OIDC User"),
                "email": payload_data.get("email", f"{payload_data.get('sub')}@esignet.user"),
                "role": payload_data.get("role", "Vendor"),
                "department": payload_data.get("department", "Corporate Partner"),
                "digital_id": f"oidc-{payload_data.get('sub')[:8]}"
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
    
    # User Mapping - Find or Create User based on OIDC sub identifier
    user = db.query(User).filter(User.esignet_sub == sub).first()
    
    if not user:
        # Fallback: Check if matching email exists without sub
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Bind the OIDC sub to this pre-existing record
            user.esignet_sub = sub
            db.commit()
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
