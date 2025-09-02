#!/usr/bin/env python3
"""Run the FastAPI operator console server"""

import sys

import uvicorn
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastapi_app.config import operator_config
from fastapi_app.security import get_security_summary, validate_binding_config


def main():
    """Run the FastAPI server"""
    host = operator_config.get("server.host", "127.0.0.1")
    port = operator_config.get("server.port", 8008)
    log_level = operator_config.get("server.log_level", "info")

    print("Starting Probable Spork Orchestrator")
    print(f"Server: {host}:{port}")
    print(f"Log level: {log_level}")

    # Validate security configuration
    if not validate_binding_config():
        print("❌ Security configuration validation failed!")
        print(
            "   External binding not allowed but host is configured for external access"
        )
        print(
            "   Set 'allow_external_bind: true' in conf/operator.yaml to enable external binding"
        )
        sys.exit(1)

    # Show security information
    security_summary = get_security_summary()
    print("Security:")
    print(f"  CORS: {'Enabled' if security_summary['cors_enabled'] else 'Disabled'}")
    print(
        f"  Rate Limiting: {'Enabled' if security_summary['rate_limiting_enabled'] else 'Disabled'}"
    )
    print(
        f"  Security Headers: {'Enabled' if security_summary['security_headers_enabled'] else 'Disabled'}"
    )
    print(
        f"  Binding: {host} ({'External' if security_summary['allow_external_bind'] else 'Local-only'})"
    )
    print(
        f"  Admin Token: {'Environment' if security_summary['admin_token_set'] else 'Default (change me!)'}"
    )

    if not security_summary["admin_token_set"]:
        print(
            "⚠️  WARNING: Using default admin token. Set ADMIN_TOKEN environment variable for production!"
        )

    print("-" * 50)

    # Run the server
    uvicorn.run(
        "fastapi_app:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=True,  # Enable auto-reload for development
    )


if __name__ == "__main__":
    main()
