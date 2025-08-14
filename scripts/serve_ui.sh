#!/bin/bash

# Probable Spork Operator Console UI
# Gradio interface for pipeline management

set -e

# Configuration
PORT=${UI_PORT:-7860}
SHARE=${UI_SHARE:-false}
DEBUG=${UI_DEBUG:-false}

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check if required packages are installed
if ! python -c "import gradio" 2>/dev/null; then
    echo "Installing required packages..."
    pip install gradio
fi

echo "Starting Probable Spork Operator Console UI..."
echo "Port: $PORT"
echo "Share: $SHARE"
echo "Debug: $DEBUG"

# Start Gradio UI
exec python -m ui.gradio_app
