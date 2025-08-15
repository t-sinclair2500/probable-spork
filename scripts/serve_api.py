#!/usr/bin/env python3
"""
Probable Spork Orchestrator API Server
Python equivalent of serve_api.sh for cross-platform compatibility
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def get_env_config():
    """Get configuration from environment variables with defaults."""
    return {
        'port': int(os.getenv('PORT', '8008')),
        'host': os.getenv('HOST', '127.0.0.1'),
        'workers': int(os.getenv('WORKERS', '1')),
        'log_level': os.getenv('LOG_LEVEL', 'info')
    }

def check_virtual_environment():
    """Check if virtual environment exists and activate if needed."""
    venv_paths = [
        Path("venv"),
        Path(".venv"),
        Path("venv/bin/activate"),
        Path(".venv/Scripts/activate")
    ]
    
    for venv_path in venv_paths:
        if venv_path.exists():
            print(f"✅ Virtual environment found: {venv_path}")
            return True
    
    print("⚠️  No virtual environment found")
    print("   Consider running: make setup")
    return False

def check_packages():
    """Check if required packages are installed."""
    try:
        import fastapi
        import uvicorn
        print("✅ Required packages found")
        return True
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        print("Installing required packages...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"
            ])
            print("✅ Packages installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install packages: {e}")
            return False

def start_server(config):
    """Start the uvicorn server."""
    print("🚀 Starting Probable Spork Orchestrator API server...")
    print(f"   Host: {config['host']}")
    print(f"   Port: {config['port']}")
    print(f"   Workers: {config['workers']}")
    print(f"   Log level: {config['log_level']}")
    print()
    
    # Build uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn",
        "fastapi_app:app",
        "--host", config['host'],
        "--port", str(config['port']),
        "--workers", str(config['workers']),
        "--log-level", config['log_level'],
        "--reload"
    ]
    
    try:
        print("Starting uvicorn server...")
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        return False
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        return True
    
    return True

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Start FastAPI server")
    parser.add_argument("--port", type=int, help="Port to bind to")
    parser.add_argument("--host", help="Host to bind to")
    parser.add_argument("--workers", type=int, help="Number of worker processes")
    parser.add_argument("--log-level", help="Log level")
    
    args = parser.parse_args()
    
    # Get configuration (CLI args override env vars)
    config = get_env_config()
    if args.port:
        config['port'] = args.port
    if args.host:
        config['host'] = args.host
    if args.workers:
        config['workers'] = args.workers
    if args.log_level:
        config['log_level'] = args.log_level
    
    print("🔧 Probable Spork - FastAPI Server")
    print("=" * 40)
    
    # Check environment
    if not check_virtual_environment():
        print("⚠️  Continuing without virtual environment...")
    
    if not check_packages():
        print("❌ Cannot start server without required packages")
        sys.exit(1)
    
    # Start server
    success = start_server(config)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
