import httpx

urls = [
    "http://localhost:8088/authorize",
    "http://localhost:8088/v1/esignet/authorize",
    "http://localhost:8088/oauth/authorize",
    "http://localhost:8088/v1/esignet/oauth/authorize"
]

params = {
    "response_type": "code",
    "client_id": "govtender-local-client",
    "redirect_uri": "http://localhost:8080/auth/esignet/callback",
    "scope": "openid profile email",
    "state": "state-12345"
}

for url in urls:
    try:
        res = httpx.get(url, params=params, follow_redirects=False)
        print(f"URL: {url} -> Status: {res.status_code}")
        if res.status_code in (302, 307):
            print(f"  Location Header: {res.headers.get('Location')}")
        else:
            print(f"  Response: {res.text[:300]}")
        print("="*40)
    except Exception as e:
        print(f"URL: {url} -> Error: {e}")
