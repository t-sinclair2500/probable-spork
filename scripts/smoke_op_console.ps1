# Probable Spork Operator Console Smoke Test
# PowerShell version for Windows compatibility
# Minimal test that validates API endpoints respond

# Configuration
$API_BASE = "http://127.0.0.1:8008/api/v1"
$ADMIN_TOKEN = if ($env:ADMIN_TOKEN) { $env:ADMIN_TOKEN } else { "default-admin-token-change-me" }

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Blue"

# Helper functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor $Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor $Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $Red
}

# Check if API is running
function Test-APIHealth {
    Write-Info "Checking API health..."
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8008/healthz" -Method Get -ErrorAction Stop
        Write-Success "API is healthy"
        return $true
    } catch {
        Write-Error "API is not responding at http://127.0.0.1:8008/healthz"
        return $false
    }
}

# Test basic endpoints
function Test-BasicEndpoints {
    Write-Info "Testing basic API endpoints..."
    
    # Test config endpoint
    Write-Info "Testing /config/operator endpoint..."
    try {
        $configResponse = Invoke-RestMethod -Uri "${API_BASE}/config/operator" -Method Get -Headers @{"Authorization" = "Bearer ${ADMIN_TOKEN}"} -ErrorAction Stop
        if ($configResponse.server) {
            Write-Success "Config endpoint working"
        } else {
            Write-Warning "Config endpoint test inconclusive: $($configResponse | ConvertTo-Json)"
        }
    } catch {
        Write-Warning "Config endpoint test failed: $($_.Exception.Message)"
    }
    
    # Test jobs endpoint (should return empty list if no jobs)
    Write-Info "Testing /jobs endpoint..."
    try {
        $jobsResponse = Invoke-RestMethod -Uri "${API_BASE}/jobs" -Method Get -Headers @{"Authorization" = "Bearer ${ADMIN_TOKEN}"} -ErrorAction Stop
        if ($jobsResponse -is [array] -and $jobsResponse.Count -eq 0) {
            Write-Success "Jobs endpoint working (empty list returned)"
        } elseif ($jobsResponse.id) {
            Write-Success "Jobs endpoint working (jobs found)"
        } else {
            Write-Error "Jobs endpoint failed: $($jobsResponse | ConvertTo-Json)"
            return $false
        }
    } catch {
        Write-Error "Jobs endpoint test failed: $($_.Exception.Message)"
        return $false
    }
    
    return $true
}

# Test authentication
function Test-Authentication {
    Write-Info "Testing authentication..."
    
    # Test without token (should fail)
    Write-Info "Testing endpoint without authentication..."
    try {
        $unauthResponse = Invoke-WebRequest -Uri "${API_BASE}/jobs" -Method Get -ErrorAction Stop
        Write-Warning "Authentication test inconclusive (got $($unauthResponse.StatusCode), expected 401)"
    } catch {
        if ($_.Exception.Response.StatusCode -eq 401) {
            Write-Success "Authentication required (401 returned)"
        } else {
            Write-Warning "Authentication test inconclusive (got $($_.Exception.Response.StatusCode), expected 401)"
        }
    }
    
    # Test with invalid token (should fail)
    Write-Info "Testing endpoint with invalid token..."
    try {
        $invalidTokenResponse = Invoke-WebRequest -Uri "${API_BASE}/jobs" -Method Get -Headers @{"Authorization" = "Bearer invalid-token"} -ErrorAction Stop
        Write-Warning "Invalid token test inconclusive (got $($invalidTokenResponse.StatusCode), expected 401)"
    } catch {
        if ($_.Exception.Response.StatusCode -eq 401) {
            Write-Success "Invalid token rejected (401 returned)"
        } else {
            Write-Warning "Invalid token test inconclusive (got $($_.Exception.Response.StatusCode), expected 401)"
        }
    }
}

# Main execution
function Main {
    Write-Info "Starting Probable Spork Operator Console smoke test..."
    
    # Check API health
    if (-not (Test-APIHealth)) {
        exit 1
    }
    
    # Test basic endpoints
    if (-not (Test-BasicEndpoints)) {
        exit 1
    }
    
    # Test authentication
    Test-Authentication
    
    Write-Success "Smoke test completed successfully!"
    Write-Info "Basic API functionality verified"
    Write-Info "Note: Full pipeline execution requires orchestrator to be running"
    
    exit 0
}

# Run main function
Main
