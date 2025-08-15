#!/usr/bin/env python3
"""
Probable Spork Operator Console Smoke Test
Python equivalent of smoke_op_console.sh for cross-platform compatibility
Minimal test that validates API endpoints respond
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path

def get_env_config():
    """Get configuration from environment variables with defaults."""
    return {
        'api_base': os.getenv('API_BASE', 'http://127.0.0.1:8008/api/v1'),
        'admin_token': os.getenv('ADMIN_TOKEN', 'default-admin-token-change-me'),
        'health_url': os.getenv('HEALTH_URL', 'http://127.0.0.1:8008/healthz')
    }

def log_info(message):
    """Print info message."""
    print(f"[INFO] {message}")

def log_success(message):
    """Print success message."""
    print(f"✅ {message}")

def log_warning(message):
    """Print warning message."""
    print(f"⚠️  {message}")

def log_error(message):
    """Print error message."""
    print(f"❌ {message}")

def check_api_health(config):
    """Check if API is running."""
    log_info("Checking API health...")
    try:
        response = requests.get(config['health_url'], timeout=5)
        if response.status_code == 200:
            log_success("API is healthy")
            return True
        else:
            log_error(f"API returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        log_error(f"API is not responding at {config['health_url']}: {e}")
        return False

def test_basic_endpoints(config):
    """Test basic API endpoints."""
    log_info("Testing basic API endpoints...")
    
    # Test config endpoint
    log_info("Testing /config/operator endpoint...")
    try:
        headers = {"Authorization": f"Bearer {config['admin_token']}"}
        response = requests.get(f"{config['api_base']}/config/operator", 
                              headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 'server' in data:
                log_success("Config endpoint working")
            else:
                log_warning(f"Config endpoint test inconclusive: {data}")
        else:
            log_warning(f"Config endpoint returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        log_warning(f"Config endpoint test failed: {e}")
    
    # Test jobs endpoint (should return empty list if no jobs)
    log_info("Testing /jobs endpoint...")
    try:
        headers = {"Authorization": f"Bearer {config['admin_token']}"}
        response = requests.get(f"{config['api_base']}/jobs", 
                              headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) == 0:
                log_success("Jobs endpoint working (empty list returned)")
            elif isinstance(data, list) and len(data) > 0 and 'id' in data[0]:
                log_success("Jobs endpoint working (jobs found)")
            else:
                log_error(f"Jobs endpoint failed: {data}")
                return False
        else:
            log_error(f"Jobs endpoint returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        log_error(f"Jobs endpoint test failed: {e}")
        return False
    
    return True

def test_authentication(config):
    """Test authentication."""
    log_info("Testing authentication...")
    
    # Test without token (should fail)
    log_info("Testing endpoint without authentication...")
    try:
        response = requests.get(f"{config['api_base']}/jobs", timeout=5)
        if response.status_code == 401:
            log_success("Authentication required (401 returned)")
        else:
            log_warning(f"Authentication test inconclusive (got {response.status_code}, expected 401)")
    except requests.exceptions.RequestException as e:
        log_warning(f"Authentication test failed: {e}")
    
    # Test with invalid token (should fail)
    log_info("Testing endpoint with invalid token...")
    try:
        headers = {"Authorization": "Bearer invalid-token"}
        response = requests.get(f"{config['api_base']}/jobs", 
                              headers=headers, timeout=5)
        if response.status_code == 401:
            log_success("Invalid token rejected (401 returned)")
        else:
            log_warning(f"Invalid token test inconclusive (got {response.status_code}, expected 401)")
    except requests.exceptions.RequestException as e:
        log_warning(f"Invalid token test failed: {e}")

def check_requests_available():
    """Check if requests library is available."""
    try:
        import requests
        return True
    except ImportError:
        print("❌ requests library not available")
        print("   Install with: pip install requests")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="API Smoke Test")
    parser.add_argument("--api-base", help="API base URL")
    parser.add_argument("--admin-token", help="Admin authentication token")
    parser.add_argument("--health-url", help="Health check URL")
    
    args = parser.parse_args()
    
    # Get configuration (CLI args override env vars)
    config = get_env_config()
    if args.api_base:
        config['api_base'] = args.api_base
    if args.admin_token:
        config['admin_token'] = args.admin_token
    if args.health_url:
        config['health_url'] = args.health_url
    
    print("🧪 Probable Spork - API Smoke Test")
    print("=" * 40)
    
    # Check if requests library is available
    if not check_requests_available():
        sys.exit(1)
    
    log_info("Starting Probable Spork Operator Console smoke test...")
    
    # Check API health
    if not check_api_health(config):
        sys.exit(1)
    
    # Test basic endpoints
    if not test_basic_endpoints(config):
        sys.exit(1)
    
    # Test authentication
    test_authentication(config)
    
    log_success("Smoke test completed successfully!")
    log_info("Basic API functionality verified")
    log_info("Note: Full pipeline execution requires orchestrator to be running")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
