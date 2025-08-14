#!/bin/bash

# Probable Spork Orchestrator API Server
# Default configuration for local development

set -e

# Configuration
PORT=${PORT:-8008}
HOST=${HOST:-127.0.0.1}
WORKERS=${WORKERS:-1}
LOG_LEVEL=${LOG_LEVEL:-info}

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check if required packages are installed
if ! python -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "Installing required packages..."
    pip install fastapi uvicorn
fi

echo "Starting Probable Spork Orchestrator API server..."
echo "Host: $HOST"
echo "Port: $PORT"
echo "Log level: $LOG_LEVEL"

# Start uvicorn server
exec uvicorn fastapi_app:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "$LOG_LEVEL" \
    --reload
