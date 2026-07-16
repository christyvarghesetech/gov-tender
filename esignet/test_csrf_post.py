import httpx
import time

def test_csrf():
    base_url = "http://localhost:8088/v1/esignet"
    client_id = "govtender-local-client"
    
    # 1. First run PAR to get a request_uri
    import uuid
    from jose import jwt
    with open("esignet/private_key.pem", "r") as f:
        private_key_pem = f.read()
    now = int(time.time())
    assertion_payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": f"{base_url}/oauth/v2/token",
        "jti": str(uuid.uuid4()),
        "exp": now + 300,
        "iat": now
    }
    client_assertion = jwt.encode(assertion_payload, private_key_pem, algorithm="RS256", headers={"kid": "govtender-local-key"})
    par_data = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": "http://localhost:8080/auth/esignet/callback",
        "scope": "openid profile email",
        "state": "state-12345",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion
    }
    client = httpx.Client(follow_redirects=True)
    res = client.post(f"{base_url}/oauth/par", data=par_data)
    if res.status_code not in (200, 201):
        print(f"PAR failed: {res.text}")
        return
    request_uri = res.json()["request_uri"]
    print(f"Got request_uri: {request_uri}")
    
    # 2. Get CSRF token
    csrf_res = client.get(f"{base_url}/csrf/token")
    csrf_json = csrf_res.json()
    token_val = csrf_json["token"]
    cookie_val = client.cookies.get("XSRF-TOKEN")
    print(f"CSRF JSON token: {token_val}")
    print(f"CSRF Cookie: {cookie_val}")
    
    req_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    payload = {
        "requestTime": req_time,
        "request": {
            "clientId": client_id,
            "requestUri": request_uri
        }
    }
    
    # Try 1: Send X-XSRF-TOKEN = token_val (from JSON body)
    headers = {
        "X-XSRF-TOKEN": token_val,
        "Content-Type": "application/json"
    }
    res1 = client.post(f"{base_url}/authorization/par-oauth-details", json=payload, headers=headers)
    print(f"Try 1 (header=token_val) status: {res1.status_code}, body: {res1.text}")
    
    # Try 2: Send X-XSRF-TOKEN = cookie_val (from cookie)
    headers2 = {
        "X-XSRF-TOKEN": cookie_val,
        "Content-Type": "application/json"
    }
    res2 = client.post(f"{base_url}/authorization/par-oauth-details", json=payload, headers=headers2)
    print(f"Try 2 (header=cookie_val) status: {res2.status_code}, body: {res2.text}")

if __name__ == '__main__':
    test_csrf()
