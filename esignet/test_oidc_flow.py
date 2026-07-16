import httpx
import time
import uuid
import base64
import hashlib
from jose import jwt

def main():
    print("Testing OIDC Flow with local eSignet container...")
    
    # 1. Load private key
    with open("esignet/private_key.pem", "r") as f:
        private_key_pem = f.read()
    
    client_id = "govtender-local-client"
    base_url = "http://localhost:8088/v1/esignet"
    redirect_uri = "http://localhost:8080/auth/esignet/callback"
    
    client = httpx.Client(follow_redirects=True)
    
    # 2. Call PAR
    print("\n--- 1. Calling PAR ---")
    token_url = f"{base_url}/oauth/v2/token"
    
    audiences = [
        token_url,
        base_url,
        "http://localhost:8088/v1/esignet/oauth/v2/token",
        "http://localhost:8088/v1/esignet",
        "http://localhost:8088",
        client_id
    ]
    
    par_res = None
    request_uri = None
    
    for aud in audiences:
        print(f"\nTrying aud: {aud}")
        now = int(time.time())
        assertion_payload = {
            "iss": client_id,
            "sub": client_id,
            "aud": aud,
            "jti": str(uuid.uuid4()),
            "exp": now + 300,
            "iat": now
        }
        client_assertion = jwt.encode(assertion_payload, private_key_pem, algorithm="RS256", headers={"kid": "govtender-local-key"})
        
        par_data = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid profile email",
            "state": "state-12345",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": client_assertion
        }
        
        res = client.post(f"{base_url}/oauth/par", data=par_data)
        print(f"PAR status: {res.status_code}")
        print(f"PAR body: {res.text}")
        if res.status_code == 201 or res.status_code == 200:
            par_res = res
            request_uri = res.json()["request_uri"]
            break
            
    if not request_uri:
        print("All audiences failed.")
        return
        
    request_uri = par_res.json()["request_uri"]
    
    # 3. Call Get OAuth Details
    print("\n--- 2. Getting OAuth Details ---")
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    details_payload = {
        "requestTime": req_time,
        "request": {
            "clientId": client_id,
            "requestUri": request_uri
        }
    }
    details_res = client.post(f"{base_url}/authorization/par-oauth-details", json=details_payload)
    print(f"OAuth Details status: {details_res.status_code}")
    print(f"OAuth Details body: {details_res.text}")
    if details_res.status_code != 200:
        return
        
    details_json = details_res.json()
    if "response" in details_json:
        transaction_id = details_json["response"]["transactionId"]
    else:
        transaction_id = details_json["transactionId"]
    
    # Compute SHA-256 hash of OAuth Details response JSON body
    # eSignet expects the Base64url encoded SHA-256 hash of the exact JSON response body
    raw_body = details_res.content
    h = hashlib.sha256(raw_body).digest()
    oauth_details_hash = base64.urlsafe_b64encode(h).decode('utf-8').rstrip('=')
    print(f"Computed oauth-details-hash: {oauth_details_hash}")
    
    headers = {
        "oauth-details-key": transaction_id,
        "oauth-details-hash": oauth_details_hash,
        "Content-Type": "application/json"
    }
    
    # 4. Call Send OTP
    print("\n--- 3. Sending OTP ---")
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    send_otp_payload = {
        "requestTime": req_time,
        "request": {
            "transactionId": transaction_id,
            "individualId": "8267411572", # UIN of Officer Jane Doe
            "otpChannels": ["email"]
        }
    }
    
    send_otp_res = client.post(f"{base_url}/authorization/send-otp", json=send_otp_payload, headers=headers)
    print(f"Send OTP status: {send_otp_res.status_code}")
    print(f"Send OTP body: {send_otp_res.text}")
    if send_otp_res.status_code != 200:
        return
        
    # 5. Call Authenticate
    print("\n--- 4. Authenticating ---")
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    auth_payload = {
        "requestTime": req_time,
        "request": {
            "transactionId": transaction_id,
            "individualId": "8267411572",
            "challengeList": [
                {
                    "authFactorType": "OTP",
                    "challenge": "111111",
                    "format": "alpha-numeric"
                }
            ]
        }
    }
    
    # Try /v2/authenticate
    auth_res = client.post(f"{base_url}/authorization/v2/authenticate", json=auth_payload, headers=headers)
    print(f"Authenticate status: {auth_res.status_code}")
    print(f"Authenticate body: {auth_res.text}")
    if auth_res.status_code != 200:
        print("Trying /authenticate (v1)...")
        auth_res = client.post(f"{base_url}/authorization/authenticate", json=auth_payload, headers=headers)
        print(f"v1 Authenticate status: {auth_res.status_code}")
        print(f"v1 Authenticate body: {auth_res.text}")
        if auth_res.status_code != 200:
            return
            
    # 6. Call Get Auth Code
    print("\n--- 5. Getting Auth Code ---")
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    code_payload = {
        "requestTime": req_time,
        "request": {
            "transactionId": transaction_id,
            "acceptedClaims": ["email"],
            "permittedAuthorizeScopes": []
        }
    }
    code_res = client.post(f"{base_url}/authorization/auth-code", json=code_payload, headers=headers)
    print(f"Auth Code status: {code_res.status_code}")
    print(f"Auth Code body: {code_res.text}")
    if code_res.status_code != 200:
        return
        
    code = code_res.json()["response"]["code"]
    print(f"Received authorization code: {code}")
    
    # 7. Exchange code for token
    print("\n--- 6. Exchanging Code for Tokens ---")
    now = int(time.time())
    assertion_payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": token_url,
        "jti": str(uuid.uuid4()),
        "exp": now + 300,
        "iat": now
    }
    client_assertion = jwt.encode(assertion_payload, private_key_pem, algorithm="RS256", headers={"kid": "govtender-local-key"})
    
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion
    }
    
    token_res = client.post(f"{base_url}/oauth/v2/token", data=token_data)
    print(f"Token status: {token_res.status_code}")
    print(f"Token body: {token_res.text}")
    if token_res.status_code != 200:
        return
        
    id_token = token_res.json().get("id_token")
    print(f"Received ID Token: {id_token}")
    
    # Decode ID Token
    unverified_claims = jwt.get_unverified_claims(id_token)
    print("\n--- Success! ID Token Claims Decoded ---")
    print(unverified_claims)

if __name__ == "__main__":
    main()
