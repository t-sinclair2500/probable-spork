# Probable Spork Orchestrator API Server
# PowerShell version for Windows compatibility

# Configuration
$env:PORT = if ($env:PORT) { $env:PORT } else { "8008" }
$env:HOST = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$env:WORKERS = if ($env:WORKERS) { $env:WORKERS } else { "1" }
$env:LOG_LEVEL = if ($env:LOG_LEVEL) { $env:LOG_LEVEL } else { "info" }

# Check if virtual environment exists
if (Test-Path "venv") {
    Write-Host "Activating virtual environment..."
    & "venv\Scripts\Activate.ps1"
}

# Check if required packages are installed
try {
    python -c "import fastapi, uvicorn" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Packages not found"
    }
} catch {
    Write-Host "Installing required packages..."
    pip install fastapi uvicorn
}

Write-Host "Starting Probable Spork Orchestrator API server..."
Write-Host "Host: $env:HOST"
Write-Host "Port: $env:PORT"
Write-Host "Log level: $env:LOG_LEVEL"

# Start uvicorn server
& python -m uvicorn fastapi_app:app --host $env:HOST --port $env:PORT --workers $env:WORKERS --log-level $env:LOG_LEVEL --reload
