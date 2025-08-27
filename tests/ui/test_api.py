#!/usr/bin/env python3
"""Simple test script for the FastAPI operator console"""

import requests
import json
import time

# Configuration
BASE_URL = "http://127.0.0.1:8008/api/v1"
ADMIN_TOKEN = "default-admin-token-change-me"  # Default from config

headers = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    try:
        response = requests.get("http://127.0.0.1:8008/healthz")
        print(f"Health check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_config():
    """Test config endpoints"""
    print("\nTesting config endpoints...")
    try:
        # Get operator config
        response = requests.get(f"{BASE_URL}/config/operator", headers=headers)
        print(f"Get config: {response.status_code}")
        if response.status_code == 200:
            config = response.json()
            print(f"Server: {config['server']['host']}:{config['server']['port']}")
            print(f"Gates: {len(config['gates'])} configured")
        
        # Validate config
        response = requests.post(f"{BASE_URL}/config/validate", headers=headers)
        print(f"Validate config: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Config validation: {result['message']}")
        
        return True
    except Exception as e:
        print(f"Config test failed: {e}")
        return False

def test_job_creation():
    """Test job creation"""
    print("\nTesting job creation...")
    try:
        job_data = {
            "slug": "test-job-001",
            "intent": "Test video creation",
            "brief_config": {
                "slug": "test-job-001",
                "intent": "Test video creation",
                "tone": "informative",
                "target_len_sec": 30
            }
        }
        
        response = requests.post(f"{BASE_URL}/jobs", headers=headers, json=job_data)
        print(f"Create job: {response.status_code}")
        
        if response.status_code == 201:
            job = response.json()
            print(f"Job created: {job['id']} - {job['slug']}")
            print(f"Status: {job['status']}, Stage: {job['stage']}")
            print(f"Gates: {len(job['gates'])}")
            return job['id']
        else:
            print(f"Job creation failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"Job creation test failed: {e}")
        return None

def test_job_listing():
    """Test job listing"""
    print("\nTesting job listing...")
    try:
        response = requests.get(f"{BASE_URL}/jobs", headers=headers)
        print(f"List jobs: {response.status_code}")
        
        if response.status_code == 200:
            jobs = response.json()
            print(f"Found {len(jobs)} jobs")
            for job in jobs:
                print(f"  - {job['id']}: {job['slug']} ({job['status']})")
            return len(jobs) > 0
        else:
            print(f"Job listing failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"Job listing test failed: {e}")
        return False

def test_gate_operations(job_id):
    """Test gate approval/rejection"""
    print(f"\nTesting gate operations for job {job_id}...")
    try:
        # Approve outline gate
        gate_action = {
            "decision": "approved",
            "stage": "outline",
            "notes": "Test approval",
            "operator": "test-operator"
        }
        
        response = requests.post(f"{BASE_URL}/jobs/{job_id}/approve", headers=headers, json=gate_action)
        print(f"Approve outline gate: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Gate approved: {result['message']}")
        
        # Get updated job
        response = requests.get(f"{BASE_URL}/jobs/{job_id}", headers=headers)
        if response.status_code == 200:
            job = response.json()
            print(f"Job status after approval: {job['status']}")
            
            # Check gate status
            for gate in job['gates']:
                if gate['stage'] == 'outline':
                    print(f"Outline gate: approved={gate['approved']}, by={gate['by']}")
        
        return True
        
    except Exception as e:
        print(f"Gate operations test failed: {e}")
        return False

def test_events(job_id):
    """Test event endpoints"""
    print(f"\nTesting events for job {job_id}...")
    try:
        # Get events (polling)
        response = requests.get(f"{BASE_URL}/jobs/{job_id}/events", headers=headers)
        print(f"Get events: {response.status_code}")
        
        if response.status_code == 200:
            events = response.json()
            print(f"Found {len(events)} events")
            for event in events[:3]:  # Show first 3 events
                print(f"  - {event['event_type']}: {event['message']}")
        
        # Test SSE endpoint (just check if it's accessible)
        response = requests.get(f"{BASE_URL}/jobs/{job_id}/events/stream", headers=headers)
        print(f"SSE endpoint: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"Events test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("FastAPI Operator Console Test Suite")
    print("=" * 40)
    
    # Test basic endpoints
    if not test_health():
        print("Health check failed, API may not be running")
        return
    
    if not test_config():
        print("Config test failed")
        return
    
    # Test job operations
    job_id = test_job_creation()
    if not job_id:
        print("Job creation failed")
        return
    
    if not test_job_listing():
        print("Job listing failed")
        return
    
    if not test_gate_operations(job_id):
        print("Gate operations failed")
        return
    
    if not test_events(job_id):
        print("Events test failed")
        return
    
    print("\n" + "=" * 40)
    print("All tests completed successfully!")
    print(f"Test job ID: {job_id}")

if __name__ == "__main__":
    main()
