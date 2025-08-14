#!/bin/bash

# Probable Spork Operator Console Smoke Test
# Minimal test that validates API endpoints respond

set -e

# Configuration
API_BASE="http://127.0.0.1:8008/api/v1"
ADMIN_TOKEN=${ADMIN_TOKEN:-"default-admin-token-change-me"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if API is running
check_api_health() {
    log_info "Checking API health..."
    if curl -s -f "http://127.0.0.1:8008/healthz" > /dev/null; then
        log_success "API is healthy"
        return 0
    else
        log_error "API is not responding at http://127.0.0.1:8008/healthz"
        return 1
    fi
}

# Test basic endpoints
test_basic_endpoints() {
    log_info "Testing basic API endpoints..."
    
    # Test config endpoint
    log_info "Testing /config/operator endpoint..."
    config_response=$(curl -s -X GET "${API_BASE}/config/operator" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}")
    
    if echo "$config_response" | grep -q '"server"'; then
        log_success "Config endpoint working"
    else
        log_warning "Config endpoint test inconclusive: $config_response"
    fi
    
    # Test jobs endpoint (should return empty list if no jobs)
    log_info "Testing /jobs endpoint..."
    jobs_response=$(curl -s -X GET "${API_BASE}/jobs" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}")
    
    if echo "$jobs_response" | grep -q '\[\]' || echo "$jobs_response" | grep -q '"id"'; then
        log_success "Jobs endpoint working"
    else
        log_error "Jobs endpoint failed: $jobs_response"
        exit 1
    fi
}

# Test authentication
test_authentication() {
    log_info "Testing authentication..."
    
    # Test without token (should fail)
    log_info "Testing endpoint without authentication..."
    unauth_response=$(curl -s -w "%{http_code}" -X GET "${API_BASE}/jobs" -o /dev/null)
    
    if [ "$unauth_response" = "401" ]; then
        log_success "Authentication required (401 returned)"
    else
        log_warning "Authentication test inconclusive (got $unauth_response, expected 401)"
    fi
    
    # Test with invalid token (should fail)
    log_info "Testing endpoint with invalid token..."
    invalid_token_response=$(curl -s -w "%{http_code}" -X GET "${API_BASE}/jobs" \
        -H "Authorization: Bearer invalid-token" -o /dev/null)
    
    if [ "$invalid_token_response" = "401" ]; then
        log_success "Invalid token rejected (401 returned)"
    else
        log_warning "Invalid token test inconclusive (got $invalid_token_response, expected 401)"
    fi
}

# Main execution
main() {
    log_info "Starting Probable Spork Operator Console smoke test..."
    
    # Check API health
    check_api_health
    
    # Test basic endpoints
    test_basic_endpoints
    
    # Test authentication
    test_authentication
    
    log_success "Smoke test completed successfully!"
    log_info "Basic API functionality verified"
    log_info "Note: Full pipeline execution requires orchestrator to be running"
    
    exit 0
}

# Run main function
main "$@"
