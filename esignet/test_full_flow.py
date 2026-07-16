import httpx
import time
import uuid
import base64
import hashlib
import json
from jose import jwt

def main():
    print("Testing End-to-End OIDC Flow...")
    
    # 1. Load private key
    with open("esignet/private_key.pem", "r") as f:
        private_key_pem = f.read()
    
    client_id = "govtender-local-client"
    base_url = "http://localhost:8088/v1/esignet"
    redirect_uri = "http://localhost:8080/auth/esignet/callback"
    
    client = httpx.Client(follow_redirects=True)
    
    # --- 1. Calling PAR ---
    print("\n--- 1. Calling PAR ---")
    token_url = f"{base_url}/oauth/v2/token"
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
    if res.status_code not in (200, 201):
        print("PAR failed.")
        return
        
    request_uri = res.json()["request_uri"]
    print(f"Got request_uri: {request_uri}")
    
    # --- 2. Getting CSRF Token ---
    print("\n--- 2. Getting CSRF Token ---")
    csrf_res = client.get(f"{base_url}/csrf/token")
    csrf_json = csrf_res.json()
    csrf_token = csrf_json["token"]
    print(f"CSRF token obtained: {csrf_token[:20]}...")
    
    # --- 3. Getting OAuth Details ---
    print("\n--- 3. Getting OAuth Details ---")
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    details_payload = {
        "requestTime": req_time,
        "request": {
            "clientId": client_id,
            "requestUri": request_uri
        }
    }
    headers = {
        "X-XSRF-TOKEN": csrf_token,
        "Content-Type": "application/json"
    }
    details_res = client.post(f"{base_url}/authorization/par-oauth-details", json=details_payload, headers=headers)
    print(f"OAuth Details status: {details_res.status_code}")
    print(f"OAuth Details body: {details_res.text[:300]}...")
    if details_res.status_code != 200:
        return
        
    details_json = details_res.json()
    transaction_id = details_json["response"]["transactionId"]
    print(f"Transaction ID: {transaction_id}")
    
    # Compute SHA-256 hash of OAuth Details response JSON response object
    response_obj = details_json["response"]
    serialized = json.dumps(response_obj, sort_keys=False, separators=(',', ':'))
    h = hashlib.sha256(serialized.encode('utf-8')).digest()
    oauth_details_hash = base64.urlsafe_b64encode(h).decode('utf-8').rstrip('=')
    print(f"Computed oauth-details-hash: {oauth_details_hash}")
    
    # Base headers for transaction-related endpoints
    txn_headers = {
        "X-XSRF-TOKEN": csrf_token,
        "oauth-details-key": transaction_id,
        "oauth-details-hash": oauth_details_hash,
        "Content-Type": "application/json"
    }
    
    # --- 4. Call Send OTP ---
    print("\n--- 4. Sending OTP ---")
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    send_otp_payload = {
        "requestTime": req_time,
        "request": {
            "transactionId": transaction_id,
            "individualId": "8267411572", # UIN of Officer Jane Doe
            "otpChannels": ["email"]
        }
    }
    send_otp_res = client.post(f"{base_url}/authorization/send-otp", json=send_otp_payload, headers=txn_headers)
    print(f"Send OTP status: {send_otp_res.status_code}")
    print(f"Send OTP body: {send_otp_res.text}")
    if send_otp_res.status_code != 200:
        return
        
    # --- 5. Call Authenticate ---
    print("\n--- 5. Authenticating ---")
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
    auth_res = client.post(f"{base_url}/authorization/v2/authenticate", json=auth_payload, headers=txn_headers)
    print(f"Authenticate status: {auth_res.status_code}")
    print(f"Authenticate body: {auth_res.text}")
    if auth_res.status_code != 200:
        print("Trying v1 authenticate...")
        auth_res = client.post(f"{base_url}/authorization/authenticate", json=auth_payload, headers=txn_headers)
        print(f"v1 Authenticate status: {auth_res.status_code}")
        print(f"v1 Authenticate body: {auth_res.text}")
        if auth_res.status_code != 200:
            return
            
    # --- 6. Call Get Auth Code ---
    print("\n--- 6. Getting Auth Code ---")
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    code_payload = {
        "requestTime": req_time,
        "request": {
            "transactionId": transaction_id,
            "acceptedClaims": ["email"],
            "permittedAuthorizeScopes": []
        }
    }
    code_res = client.post(f"{base_url}/authorization/auth-code", json=code_payload, headers=txn_headers)
    print(f"Auth Code status: {code_res.status_code}")
    print(f"Auth Code body: {code_res.text}")
    if code_res.status_code != 200:
        return
        
    code = code_res.json()["response"]["code"]
    print(f"Received authorization code: {code}")
    
    # --- 7. Exchange code for token ---
    print("\n--- 7. Exchanging Code for Tokens ---")
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
