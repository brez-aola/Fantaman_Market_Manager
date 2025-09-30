#!/usr/bin/env python3
"""Test script for authentication API endpoints.

This script starts the Flask app and tests the authentication endpoints.
"""

import json
import os
import sys
import requests
import time
from threading import Thread

# Add the parent directory to Python path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app


def start_test_server():
    """Start Flask test server."""
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


def test_auth_endpoints():
    """Test authentication API endpoints."""
    base_url = "http://127.0.0.1:5000"

    print("🧪 Testing Authentication API Endpoints...")

    # Wait for server to start
    time.sleep(2)

    try:
        # Test 1: Health check
        print("\n1️⃣ Testing health endpoint...")
        response = requests.get(f"{base_url}/api/health")
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")

        # Test 2: Login with admin credentials
        print("\n2️⃣ Testing login...")
        login_data = {
            "username": "admin",
            "password": "fantacalcio123"
        }

        response = requests.post(
            f"{base_url}/api/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            print("✅ Login successful")
            auth_data = response.json()
            access_token = auth_data.get("access_token")
            print(f"   🔑 Access token obtained: {access_token[:20]}...")
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return

        # Test 3: Get current user info
        print("\n3️⃣ Testing user info endpoint...")
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(f"{base_url}/api/auth/me", headers=headers)

        if response.status_code == 200:
            print("✅ User info retrieved successfully")
            user_info = response.json()
            print(f"   👤 User: {user_info['user']['username']}")
            print(f"   🎭 Roles: {user_info['user']['roles']}")
            print(f"   🔐 Permissions: {len(user_info['user']['permissions'])} permissions")
        else:
            print(f"❌ User info failed: {response.status_code}")
            print(f"   Response: {response.text}")

        # Test 4: Test protected endpoint without token
        print("\n4️⃣ Testing protected endpoint without token...")
        response = requests.get(f"{base_url}/api/auth/me")

        if response.status_code == 401:
            print("✅ Protected endpoint correctly rejected unauthorized request")
        else:
            print(f"❌ Protected endpoint security issue: {response.status_code}")

        # Test 5: List users (admin endpoint)
        print("\n5️⃣ Testing admin endpoint...")
        response = requests.get(f"{base_url}/api/auth/users", headers=headers)

        if response.status_code == 200:
            print("✅ Admin endpoint accessible")
            users_data = response.json()
            print(f"   👥 Total users: {len(users_data['users'])}")
        else:
            print(f"❌ Admin endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")

        # Test 6: Logout
        print("\n6️⃣ Testing logout...")
        response = requests.post(f"{base_url}/api/auth/logout", headers=headers)

        if response.status_code == 200:
            print("✅ Logout successful")
        else:
            print(f"❌ Logout failed: {response.status_code}")
            print(f"   Response: {response.text}")

        print("\n🎉 Authentication API testing completed!")

    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to test server. Make sure it's running.")
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main test function."""
    print("🚀 Starting Authentication API Test Suite...")

    # Start server in background thread
    server_thread = Thread(target=start_test_server, daemon=True)
    server_thread.start()

    # Run tests
    test_auth_endpoints()

    print("\n✅ Test suite completed!")


if __name__ == "__main__":
    main()
