# Probable Spork Operator Console UI
# PowerShell version for Windows compatibility
# Gradio interface for pipeline management

# Configuration
$env:UI_PORT = if ($env:UI_PORT) { $env:UI_PORT } else { "7860" }
$env:UI_SHARE = if ($env:UI_SHARE) { $env:UI_SHARE } else { "false" }
$env:UI_DEBUG = if ($env:UI_DEBUG) { $env:UI_DEBUG } else { "false" }

# Check if virtual environment exists
if (Test-Path "venv") {
    Write-Host "Activating virtual environment..."
    & "venv\Scripts\Activate.ps1"
}

# Check if required packages are installed
try {
    python -c "import gradio" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Package not found"
    }
} catch {
    Write-Host "Installing required packages..."
    pip install gradio
}

Write-Host "Starting Probable Spork Operator Console UI..."
Write-Host "Port: $env:UI_PORT"
Write-Host "Share: $env:UI_SHARE"
Write-Host "Debug: $env:UI_DEBUG"

# Start Gradio UI
& python -m ui.gradio_app
