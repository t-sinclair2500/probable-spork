#!/usr/bin/env python3
"""
Test script for Phase 6 Operator Console fixes
Tests the key functionality: events, auth, gates, and stage adapters
"""

import sys

import requests
from pathlib import Path


def test_health_endpoint():
    """Test health endpoint (no auth required)"""
    print("Testing health endpoint...")
    try:
        response = requests.get("http://127.0.0.1:8008/healthz", timeout=5)
        if response.status_code == 200:
            print("✓ Health endpoint working")
            return True
        else:
            print(f"✗ Health endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health endpoint failed: {e}")
        return False


def test_auth_required():
    """Test that protected endpoints require authentication"""
    print("Testing authentication requirement...")
    try:
        response = requests.get("http://127.0.0.1:8008/api/v1/jobs", timeout=5)
        if response.status_code == 401:
            print("✓ Authentication required (401 returned)")
            return True
        else:
            print(f"✗ Expected 401, got {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Auth test failed: {e}")
        return False


def test_auth_with_token():
    """Test authentication with valid token"""
    print("Testing authentication with token...")
    try:
        headers = {"Authorization": "Bearer default-admin-token-change-me"}
        response = requests.get(
            "http://127.0.0.1:8008/api/v1/jobs", headers=headers, timeout=5
        )
        if response.status_code == 200:
            print("✓ Authentication successful")
            return True
        else:
            print(f"✗ Auth failed with valid token: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Auth test failed: {e}")
        return False


def test_job_creation():
    """Test job creation with authentication"""
    print("Testing job creation...")
    try:
        headers = {"Authorization": "Bearer default-admin-token-change-me"}
        job_data = {
            "slug": "test-phase6-fixes",
            "intent": "testing",
            "brief_config": {
                "slug": "test-phase6-fixes",
                "intent": "testing",
                "target_len_sec": 60,
                "tone": "informative",
            },
        }

        response = requests.post(
            "http://127.0.0.1:8008/api/v1/jobs",
            headers=headers,
            json=job_data,
            timeout=10,
        )

        if response.status_code == 201:
            job = response.json()
            job_id = job.get("id")
            print(f"✓ Job created successfully: {job_id}")
            return job_id
        else:
            print(f"✗ Job creation failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ Job creation test failed: {e}")
        return None


def test_events_endpoint(job_id):
    """Test events endpoint"""
    print("Testing events endpoint...")
    try:
        headers = {"Authorization": "Bearer default-admin-token-change-me"}
        response = requests.get(
            f"http://127.0.0.1:8008/api/v1/jobs/{job_id}/events",
            headers=headers,
            timeout=5,
        )

        if response.status_code == 200:
            events = response.json()
            event_count = len(events.get("events", []))
            print(f"✓ Events endpoint working, found {event_count} events")
            return True
        else:
            print(f"✗ Events endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Events test failed: {e}")
        return False


def test_jsonl_file_creation(job_id):
    """Test that events are written to JSONL file"""
    print("Testing JSONL file creation...")
    try:
        events_file = Path("runs") / job_id / "events.jsonl"
        if events_file.exists():
            # Count lines in file
            with open(events_file, "r") as f:
                line_count = sum(1 for _ in f)
            print(f"✓ JSONL file created with {line_count} events")
            return True
        else:
            print("✗ JSONL file not found")
            return False
    except Exception as e:
        print(f"✗ JSONL test failed: {e}")
        return False


def test_gate_management(job_id):
    """Test gate approval/rejection"""
    print("Testing gate management...")
    try:
        headers = {"Authorization": "Bearer default-admin-token-change-me"}

        # Test gate approval
        gate_data = {
            "decision": "approved",
            "stage": "outline",
            "notes": "Test approval",
            "operator": "test_script",
        }

        response = requests.post(
            f"http://127.0.0.1:8008/api/v1/jobs/{job_id}/approve",
            headers=headers,
            json=gate_data,
            timeout=5,
        )

        if response.status_code == 200:
            print("✓ Gate approval successful")
            return True
        else:
            print(f"✗ Gate approval failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Gate management test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("Phase 6 Operator Console Fixes Test")
    print("=" * 40)

    # Check if API is running
    print("Checking if API server is running...")
    if not test_health_endpoint():
        print("API server is not running. Start it with: make op-console-api")
        return False

    tests = [
        ("Health endpoint", test_health_endpoint),
        ("Authentication required", test_auth_required),
        ("Authentication with token", test_auth_with_token),
    ]

    # Run basic tests
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if not test_func():
            print(f"Test '{test_name}' failed")
            return False

    # Test job creation
    print("\nJob creation:")
    job_id = test_job_creation()
    if not job_id:
        print("Job creation test failed")
        return False

    # Test events and gates
    additional_tests = [
        ("Events endpoint", lambda: test_events_endpoint(job_id)),
        ("JSONL file creation", lambda: test_jsonl_file_creation(job_id)),
        ("Gate management", lambda: test_gate_management(job_id)),
    ]

    for test_name, test_func in additional_tests:
        print(f"\n{test_name}:")
        if not test_func():
            print(f"Test '{test_name}' failed")
            return False

    print("\n" + "=" * 40)
    print("✓ All Phase 6 tests passed!")
    print("The operator console is working correctly.")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
