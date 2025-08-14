#!/usr/bin/env python3
"""Run the FastAPI operator console server"""

import uvicorn
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastapi_app.config import operator_config

def main():
    """Run the FastAPI server"""
    host = operator_config.get("server.host", "127.0.0.1")
    port = operator_config.get("server.port", 8008)
    log_level = operator_config.get("server.log_level", "info")
    
    print(f"Starting Probable Spork Orchestrator")
    print(f"Server: {host}:{port}")
    print(f"Log level: {log_level}")
    print(f"Admin token: {operator_config.get('security.default_token', 'Not set')}")
    print(f"CORS: {'Enabled' if operator_config.get('security.cors.enabled') else 'Disabled'}")
    print("-" * 50)
    
    # Run the server
    uvicorn.run(
        "fastapi_app:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=True  # Enable auto-reload for development
    )

if __name__ == "__main__":
    main()
