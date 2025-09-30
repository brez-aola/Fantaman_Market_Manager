#!/usr/bin/env python3
"""Smoke test for Auth endpoints using urllib (no external deps).

Usage: python3 scripts/smoke_auth_test.py
"""
import json
import urllib.request
import urllib.error

BASE = 'http://127.0.0.1:5000'

def post_json(path, payload):
    url = BASE + path
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json'
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode('utf-8'), resp.getcode()
    except urllib.error.HTTPError as e:
        return e.read().decode('utf-8'), e.code
    except Exception as e:
        return json.dumps({'error': str(e)}), None

def get_with_token(path, token):
    url = BASE + path
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}'
    }, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode('utf-8'), resp.getcode()
    except urllib.error.HTTPError as e:
        return e.read().decode('utf-8'), e.code
    except Exception as e:
        return json.dumps({'error': str(e)}), None


def main():
    print('Logging in...')
    body, code = post_json('/api/auth/login', {'username': 'admin', 'password': 'fantacalcio123'})
    print('Login HTTP code:', code)
    print('Login body:', body)
    token = ''
    try:
        j = json.loads(body)
        token = j.get('access_token', '')
    except Exception as e:
        print('Failed to parse login JSON:', e)

    if not token:
        print('\nNo token obtained; aborting tests')
        return

    print('\nToken obtained (truncated):', token[:40] + '...' )

    print('\nCalling /api/auth/me')
    body, code = get_with_token('/api/auth/me', token)
    print('HTTP', code)
    print(body)

    print('\nCalling /api/auth/users')
    body, code = get_with_token('/api/auth/users', token)
    print('HTTP', code)
    print(body)

if __name__ == '__main__':
    main()
