#!/usr/bin/env python3
"""
Tests OpenAPI documentation availability and rate limiting behavior.
- Checks OpenAPI JSON is available and contains expected metadata
- Performs burst requests against an auth endpoint to verify 429 when limit exceeded
"""
import requests
import time
import sys

BASE = "http://localhost:5000"


def check_openapi():
    urls = [f"{BASE}/swagger.json", f"{BASE}/docs/swagger.json", f"{BASE}/docs/swagger/", f"{BASE}/swagger/"]
    for url in urls:
        try:
            r = requests.get(url, timeout=3)
        except Exception:
            continue
        if r.status_code == 200:
            try:
                spec = r.json()
                title = spec.get('info', {}).get('title')
                version = spec.get('info', {}).get('version')
                print(f"[OK] OpenAPI available at {url} - title={title} version={version}")
                return True
            except Exception:
                print(f"[WARN] {url} returned 200 but not JSON")
                return False
    print("[FAIL] OpenAPI JSON not found at common locations")
    return False


def test_rate_limit_auth_login():
    # Auth login endpoint rate limit configured to 10 per minute in our tests
    url = f"{BASE}/api/v1/auth/login"
    payload = {"username": "admin", "password": "admin123"}
    headers = {"Content-Type": "application/json"}

    # Perform 12 quick requests to exceed limit of 10/min
    exceeded = False
    statuses = {}
    for i in range(12):
        r = requests.post(url, json=payload, headers=headers)
        statuses[r.status_code] = statuses.get(r.status_code, 0) + 1
        if r.status_code == 429:
            exceeded = True
            print(f"[OK] Received 429 on attempt {i+1}")
            break
        time.sleep(0.2)

    print(f"Status counts: {statuses}")
    return exceeded


if __name__ == '__main__':
    all_ok = True
    print("Checking OpenAPI documentation...")
    ok = check_openapi()
    all_ok = all_ok and ok

    print("Testing rate limit on login endpoint...")
    ok = test_rate_limit_auth_login()
    all_ok = all_ok and ok

    if all_ok:
        print("ALL OK")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED")
        sys.exit(2)
