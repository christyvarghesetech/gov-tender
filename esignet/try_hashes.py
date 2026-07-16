import httpx
import time
import uuid
import base64
import hashlib
import json
import re
from jose import jwt

def get_expected_hash():
    base_url = "http://localhost:8088/v1/esignet"
    client_id = "govtender-local-client"
    
    with open("esignet/private_key.pem", "r") as f:
        private_key_pem = f.read()
        
    client = httpx.Client(follow_redirects=True)
    
    # 1. PAR
    now = int(time.time())
    assertion_payload = {
        "iss": client_id, "sub": client_id, "aud": f"{base_url}/oauth/v2/token",
        "jti": str(uuid.uuid4()), "exp": now + 300, "iat": now
    }
    client_assertion = jwt.encode(assertion_payload, private_key_pem, algorithm="RS256", headers={"kid": "govtender-local-key"})
    par_data = {
        "response_type": "code", "client_id": client_id,
        "redirect_uri": "http://localhost:8080/auth/esignet/callback",
        "scope": "openid profile email", "state": "state-12345",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion
    }
    res = client.post(f"{base_url}/oauth/par", data=par_data)
    request_uri = res.json()["request_uri"]
    
    # 2. CSRF
    csrf_res = client.get(f"{base_url}/csrf/token")
    csrf_token = csrf_res.json()["token"]
    
    # 3. OAuth Details
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    details_payload = {
        "requestTime": req_time,
        "request": {"clientId": client_id, "requestUri": request_uri}
    }
    headers = {"X-XSRF-TOKEN": csrf_token, "Content-Type": "application/json"}
    details_res = client.post(f"{base_url}/authorization/par-oauth-details", json=details_payload, headers=headers)
    
    details_json = details_res.json()
    transaction_id = details_json["response"]["transactionId"]
    raw_content = details_res.content # bytes
    
    # 4. Trigger send-otp with dummy hash to get the correct expected hash from container logs
    dummy_hash = "dummyhash"
    txn_headers = {
        "X-XSRF-TOKEN": csrf_token,
        "oauth-details-key": transaction_id,
        "oauth-details-hash": dummy_hash,
        "Content-Type": "application/json"
    }
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    send_otp_payload = {
        "requestTime": req_time,
        "request": {
            "transactionId": transaction_id,
            "individualId": "8267411572",
            "otpChannels": ["email"]
        }
    }
    client.post(f"{base_url}/authorization/send-otp", json=send_otp_payload, headers=txn_headers)
    
    # Fetch expected hash from docker logs
    # Give it a tiny bit of time
    time.sleep(0.5)
    import subprocess
    log_out = subprocess.check_output(["docker", "logs", "esignet", "--tail", "20"]).decode('utf-8', errors='ignore')
    match = re.search(r"oauth-details header validation failed, value in transaction:\s*([A-Za-z0-9_-]+)", log_out)
    if not match:
        print("Could not find expected hash in logs. Log output:")
        print(log_out)
        return None, None, None
        
    expected_hash = match.group(1)
    print(f"Found expected hash from server logs: {expected_hash}")
    return raw_content, details_json, expected_hash

def sha256_b64url(data: bytes) -> str:
    h = hashlib.sha256(data).digest()
    return base64.urlsafe_b64encode(h).decode('utf-8').rstrip('=')

def try_all():
    raw_content, details_json, expected = get_expected_hash()
    if not expected:
        return
        
    # Option 1: Hash of raw response body bytes
    h1 = sha256_b64url(raw_content)
    print(f"Option 1 (raw body): {h1}")
    if h1 == expected:
        print("SUCCESS: Option 1!")
        return
        
    # Option 2: Hash of Response object JSON (no whitespace, sorted or unsorted)
    response_obj = details_json["response"]
    
    for sort_keys in [False, True]:
        for separators in [ (',', ':'), (', ', ': ') ]:
            serialized = json.dumps(response_obj, sort_keys=sort_keys, separators=separators)
            h = sha256_b64url(serialized.encode('utf-8'))
            print(f"Option 2 (response obj, sort={sort_keys}, seps={separators}): {h}")
            if h == expected:
                print("SUCCESS: Option 2!")
                return
                
    # Option 3: Check if it hashes without transactionId or other fields
    for key_to_remove in ["transactionId", "logoUrl", "configs"]:
        res_copy = dict(response_obj)
        if key_to_remove in res_copy:
            del res_copy[key_to_remove]
        for sort_keys in [False, True]:
            for separators in [ (',', ':'), (', ', ': ') ]:
                serialized = json.dumps(res_copy, sort_keys=sort_keys, separators=separators)
                h = sha256_b64url(serialized.encode('utf-8'))
                if h == expected:
                    print(f"SUCCESS: Option 3 (removed {key_to_remove}, sort={sort_keys}, seps={separators})")
                    return
                    
    # Option 4: Maybe it hashes only certain fields in response?
    # Let's inspect the fields in OAuthDetailResponseV2 class from class inspector
    # OAuthDetailResponseV2 fields:
    # Let's print response keys:
    print(f"Keys in response: {list(response_obj.keys())}")
    
    # Wait, let's write a loop to try hashing single values or list of values
    # Or maybe it hashes OAuthDetailResponse (V1)?
    # Wait, what if the server is hashing OAuthDetailResponseV2 as serialized by Jackson?
    # Jackson serialization does NOT sort keys! It serializes them in declaration order of fields in the class!
    # Let's list the fields of OAuthDetailResponseV2.class from our find_dtos_anywhere.py output?
    # Oh, find_dtos_anywhere.py didn't print OAuthDetailResponseV2.class, it printed OAuthDetailRequest.class!
    # Let's see if we can find OAuthDetailResponseV2.class in the JAR.
    # Yes, BOOT-INF/classes/io/mosip/esignet/core/dto/OAuthDetailResponseV2.class or similar.
    # Let's check!

if __name__ == '__main__':
    try_all()
