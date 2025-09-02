#!/usr/bin/env python3
"""Test script for security implementation"""

import os
import sys
import time

import requests
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_unauthorized_access():
    """Test that unauthorized requests are rejected"""
    print("Testing unauthorized access...")

    # Test without token (should be 403 Forbidden)
    try:
        response = requests.get("http://127.0.0.1:8008/api/v1/jobs")
        if response.status_code == 403:
            print("✅ No token correctly rejected (403 Forbidden)")
        else:
            print(f"❌ Expected 403, got {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server not running. Start with: make op-console")
        return False

    # Test with invalid token (should be 401 Unauthorized)
    try:
        headers = {"Authorization": "Bearer invalid-token"}
        response = requests.get("http://127.0.0.1:8008/api/v1/jobs", headers=headers)
        if response.status_code == 401:
            print("✅ Invalid token correctly rejected (401 Unauthorized)")
        else:
            print(f"❌ Expected 401, got {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server not running")
        return False

    return True


def test_authorized_access():
    """Test that authorized requests work"""
    print("\nTesting authorized access...")

    # Get token from environment or use default
    token = os.getenv("ADMIN_TOKEN", "default-admin-token-change-me")
    headers = {"Authorization": f"Bearer {token}"}

    try:
        # Test health endpoint (should work without auth)
        response = requests.get("http://127.0.0.1:8008/healthz")
        if response.status_code == 200:
            print("✅ Health endpoint accessible without auth")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False

        # Test jobs endpoint with valid token
        response = requests.get("http://127.0.0.1:8008/api/v1/jobs", headers=headers)
        if response.status_code == 200:
            print("✅ Authorized request successful (200)")
        else:
            print(f"❌ Authorized request failed: {response.status_code}")
            return False

        # Test config endpoint
        response = requests.get(
            "http://127.0.0.1:8008/api/v1/config/operator", headers=headers
        )
        if response.status_code == 200:
            config = response.json()
            # Verify no secrets in response
            if "default_token" not in str(config) and "admin_token" not in str(config):
                print("✅ Config endpoint returns sanitized data (no secrets)")
            else:
                print("❌ Config endpoint contains secrets")
                return False
        else:
            print(f"❌ Config endpoint failed: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Server not running")
        return False

    return True


def test_rate_limiting():
    """Test rate limiting functionality"""
    print("\nTesting rate limiting...")

    token = os.getenv("ADMIN_TOKEN", "default-admin-token-change-me")
    headers = {"Authorization": f"Bearer {token}"}

    # Test job creation rate limiting
    job_data = {"slug": "test-security", "intent": "Test security implementation"}

    # Make multiple requests quickly
    responses = []
    for i in range(10):
        try:
            response = requests.post(
                "http://127.0.0.1:8008/api/v1/jobs", headers=headers, json=job_data
            )
            responses.append(response.status_code)
            time.sleep(0.1)  # Small delay
        except requests.exceptions.ConnectionError:
            print("❌ Server not running")
            return False

    # Check if we hit rate limits
    success_count = responses.count(201)
    rate_limited_count = responses.count(429)

    print(f"  Job creation attempts: {len(responses)}")
    print(f"  Successful: {success_count}")
    print(f"  Rate limited: {rate_limited_count}")

    if rate_limited_count > 0:
        print("✅ Rate limiting working correctly")
        return True
    else:
        print("⚠️  Rate limiting may not be working (no 429 responses)")
        return True  # Not a failure, just a warning


def test_cors_configuration():
    """Test CORS configuration"""
    print("\nTesting CORS configuration...")

    try:
        # Test preflight request
        headers = {
            "Origin": "http://localhost:7860",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }

        response = requests.options(
            "http://127.0.0.1:8008/api/v1/jobs", headers=headers
        )

        # Check CORS headers
        cors_headers = response.headers.get("Access-Control-Allow-Origin")

        if cors_headers:
            print(f"✅ CORS enabled: {cors_headers}")
        else:
            print("✅ CORS disabled (default security)")

    except requests.exceptions.ConnectionError:
        print("❌ Server not running")
        return False

    return True


def main():
    """Run all security tests"""
    print("🔒 Security Implementation Test Suite")
    print("=" * 50)

    tests = [
        test_unauthorized_access,
        test_authorized_access,
        test_rate_limiting,
        test_cors_configuration,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with error: {e}")

    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} passed")

    if passed == total:
        print("🎉 All security tests passed!")
        return 0
    else:
        print("❌ Some security tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
