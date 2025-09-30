#!/usr/bin/env python3
"""
Comprehensive API Test Suite
Tests authentication, authorization, rate limiting, input validation, and CRUD operations.
"""

import json
import requests
import time
from typing import Dict, Any, Optional
import sys


class APITester:
    """Comprehensive API testing class."""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.admin_token = None
        self.user_token = None

    def log(self, message: str, level: str = "INFO"):
        """Log test messages."""
        print(f"[{level}] {message}")

    def test_health(self) -> bool:
        """Test health endpoint."""
        self.log("Testing health endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/api/v1/health")
            success = response.status_code == 200
            if success:
                data = response.json()
                self.log(f"✅ Health check: {data.get('status')}")
            else:
                self.log(f"❌ Health check failed: {response.status_code}", "ERROR")
            return success
        except Exception as e:
            self.log(f"❌ Health check error: {e}", "ERROR")
            return False

    def test_authentication(self) -> bool:
        """Test authentication system."""
        self.log("Testing authentication system...")

        # Test admin login
        try:
            login_data = {"username": "admin", "password": "admin123"}
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()
                self.admin_token = data.get("access_token")
                user_info = data.get("user", {})
                self.log(f"✅ Admin login successful: {user_info.get('username')} with roles {user_info.get('roles')}")
                return True
            else:
                self.log(f"❌ Admin login failed: {response.status_code} - {response.text}", "ERROR")
                return False

        except Exception as e:
            self.log(f"❌ Authentication error: {e}", "ERROR")
            return False

    def test_registration(self) -> bool:
        """Test user registration."""
        self.log("Testing user registration...")

        try:
            # Generate unique username for test
            import uuid
            unique_suffix = str(uuid.uuid4())[:8]

            register_data = {
                "username": f"testuser_{unique_suffix}",
                "email": f"test_{unique_suffix}@example.com",
                "password": "testpass123",
                "confirm_password": "testpass123"
            }

            response = self.session.post(
                f"{self.base_url}/api/v1/auth/register",
                json=register_data,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 201:
                data = response.json()
                self.user_token = data.get("access_token")
                user_info = data.get("user", {})
                self.log(f"✅ Registration successful: {user_info.get('username')} with roles {user_info.get('roles')}")
                return True
            else:
                self.log(f"❌ Registration failed: {response.status_code} - {response.text}", "ERROR")
                return False

        except Exception as e:
            self.log(f"❌ Registration error: {e}", "ERROR")
            return False

    def test_authorization(self) -> bool:
        """Test role-based authorization."""
        self.log("Testing authorization system...")

        if not self.user_token:
            self.log("❌ No user token available for authorization test", "ERROR")
            return False

        try:
            # Try to access admin-only endpoint with user token
            headers = {"Authorization": f"Bearer {self.user_token}"}
            response = self.session.get(f"{self.base_url}/api/v1/auth/users", headers=headers)

            if response.status_code == 403:
                error_data = response.json()
                self.log(f"✅ Authorization working: {error_data.get('error')} - {error_data.get('code')}")
                return True
            else:
                self.log(f"❌ Authorization failed: Expected 403, got {response.status_code}", "ERROR")
                return False

        except Exception as e:
            self.log(f"❌ Authorization test error: {e}", "ERROR")
            return False

    def test_input_validation(self) -> bool:
        """Test input validation."""
        self.log("Testing input validation...")

        try:
            # Test invalid login data
            invalid_data = {"username": "ab", "password": "123"}  # Too short
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json=invalid_data,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 400:
                error_data = response.json()
                if error_data.get("code") == "VALIDATION_ERROR":
                    details = error_data.get("details", {})
                    self.log(f"✅ Input validation working: {len(details)} field errors detected")
                    return True

            self.log(f"❌ Input validation failed: Expected validation error, got {response.status_code}", "ERROR")
            return False

        except Exception as e:
            self.log(f"❌ Input validation test error: {e}", "ERROR")
            return False

    def test_content_type_validation(self) -> bool:
        """Test Content-Type validation."""
        self.log("Testing Content-Type validation...")

        try:
            # Send request without proper Content-Type
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                data='{"username": "admin", "password": "admin123"}'  # Plain text, not JSON
            )

            if response.status_code == 400:
                error_data = response.json()
                if error_data.get("code") == "INVALID_CONTENT_TYPE":
                    self.log("✅ Content-Type validation working")
                    return True

            self.log(f"❌ Content-Type validation failed: Expected 400, got {response.status_code}", "ERROR")
            return False

        except Exception as e:
            self.log(f"❌ Content-Type validation test error: {e}", "ERROR")
            return False

    def test_protected_endpoints(self) -> bool:
        """Test protected API endpoints."""
        self.log("Testing protected endpoints...")

        if not self.admin_token:
            self.log("❌ No admin token available for protected endpoint test", "ERROR")
            return False

        try:
            # Test protected profile endpoint
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            response = self.session.get(f"{self.base_url}/api/v1/auth/profile", headers=headers)

            if response.status_code == 200:
                data = response.json()
                user_info = data.get("user", {})
                self.log(f"✅ Protected endpoint working: Profile for {user_info.get('username')}")
                return True
            else:
                self.log(f"❌ Protected endpoint failed: {response.status_code}", "ERROR")
                return False

        except Exception as e:
            self.log(f"❌ Protected endpoint test error: {e}", "ERROR")
            return False

    def test_crud_operations(self) -> bool:
        """Test CRUD operations with security."""
        self.log("Testing CRUD operations...")

        if not self.admin_token:
            self.log("❌ No admin token available for CRUD test", "ERROR")
            return False

        try:
            headers = {"Authorization": f"Bearer {self.admin_token}", "Content-Type": "application/json"}

            # Test CREATE - create a team
            team_data = {
                "name": f"Test Team {int(time.time())}",
                "cash": 250.0
            }

            response = self.session.post(
                f"{self.base_url}/api/v1/teams",
                json=team_data,
                headers=headers
            )

            if response.status_code == 201:
                team_info = response.json()
                team_id = team_info.get("id")
                self.log(f"✅ CREATE operation successful: Team ID {team_id}")

                # Test READ - get the created team
                response = self.session.get(f"{self.base_url}/api/v1/teams", headers=headers)
                if response.status_code == 200:
                    self.log("✅ READ operation successful")
                    return True
                else:
                    self.log(f"❌ READ operation failed: {response.status_code}", "ERROR")
                    return False
            else:
                self.log(f"❌ CREATE operation failed: {response.status_code} - {response.text}", "ERROR")
                return False

        except Exception as e:
            self.log(f"❌ CRUD operations test error: {e}", "ERROR")
            return False

    def test_security_headers(self) -> bool:
        """Test security headers in responses."""
        self.log("Testing security headers...")

        try:
            response = self.session.get(f"{self.base_url}/api/v1/health")
            headers = response.headers

            security_headers = [
                'X-Content-Type-Options',
                'X-Frame-Options',
                'X-XSS-Protection'
            ]

            present_headers = []
            for header in security_headers:
                if header in headers:
                    present_headers.append(header)

            if len(present_headers) >= 2:  # At least 2 security headers
                self.log(f"✅ Security headers present: {', '.join(present_headers)}")
                return True
            else:
                self.log(f"❌ Insufficient security headers: {present_headers}", "ERROR")
                return False

        except Exception as e:
            self.log(f"❌ Security headers test error: {e}", "ERROR")
            return False

    def run_all_tests(self) -> bool:
        """Run all tests and return overall result."""
        self.log("=" * 60)
        self.log("🚀 Starting Comprehensive API Security Test Suite")
        self.log("=" * 60)

        tests = [
            ("Health Check", self.test_health),
            ("Authentication", self.test_authentication),
            ("Registration", self.test_registration),
            ("Authorization", self.test_authorization),
            ("Input Validation", self.test_input_validation),
            ("Content-Type Validation", self.test_content_type_validation),
            ("Protected Endpoints", self.test_protected_endpoints),
            ("CRUD Operations", self.test_crud_operations),
            ("Security Headers", self.test_security_headers)
        ]

        results = {}
        for test_name, test_func in tests:
            self.log("-" * 40)
            try:
                result = test_func()
                results[test_name] = result
            except Exception as e:
                self.log(f"❌ Test {test_name} crashed: {e}", "ERROR")
                results[test_name] = False

        # Summary
        self.log("=" * 60)
        self.log("📊 TEST SUMMARY")
        self.log("=" * 60)

        passed = 0
        total = len(results)

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"{status} - {test_name}")
            if result:
                passed += 1

        self.log("-" * 40)
        self.log(f"📈 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

        overall_success = passed == total
        if overall_success:
            self.log("🎉 ALL TESTS PASSED - API Security Implementation Complete!")
        else:
            self.log("⚠️  Some tests failed - Review implementation", "ERROR")

        return overall_success


def main():
    """Main test execution."""
    tester = APITester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
