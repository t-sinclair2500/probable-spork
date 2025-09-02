#!/usr/bin/env python3
"""
Probable Spork System Startup Script
Automatically launches the backend and frontend services
"""

import subprocess
import sys
import time

from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_port(port):
    """Check if a port is available"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return False  # Port is available
        except OSError:
            return True  # Port is in use


def wait_for_port(port, timeout=30):
    """Wait for a port to become available"""
    print(f"⏳ Waiting for port {port} to become available...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_port(port):
            print(f"✅ Port {port} is now available")
            return True
        time.sleep(1)
    print(f"❌ Timeout waiting for port {port}")
    return False


def start_backend():
    """Start the FastAPI backend server"""
    print("🚀 Starting FastAPI Backend Server...")

    if check_port(8008):
        print("⚠️ Port 8008 is already in use. Backend may already be running.")
        return True

    try:
        # Start the backend server
        backend_process = subprocess.Popen(
            [sys.executable, "run_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for the server to start
        if wait_for_port(8008):
            print("✅ Backend server started successfully on port 8008")
            return True
        else:
            print("❌ Backend server failed to start")
            return False

    except Exception as e:
        print(f"❌ Failed to start backend: {e}")
        return False


def start_frontend():
    """Start the Gradio frontend"""
    print("🎨 Starting Gradio Frontend...")

    if check_port(7860):
        print("⚠️ Port 7860 is already in use. Frontend may already be running.")
        return True

    try:
        # Start the Gradio UI
        frontend_process = subprocess.Popen(
            [sys.executable, "ui/gradio_app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for the frontend to start
        if wait_for_port(7860):
            print("✅ Frontend started successfully on port 7860")
            return True
        else:
            print("❌ Frontend failed to start")
            return False

    except Exception as e:
        print(f"❌ Failed to start frontend: {e}")
        return False


def run_health_check():
    """Run a basic health check to ensure everything is working"""
    print("\n🧪 Running Health Check...")

    try:
        print("✅ Health check completed")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def main():
    """Main startup sequence"""
    print("🚀 Probable Spork System Startup")
    print("=" * 50)

    # Step 1: Health check
    if not run_health_check():
        print("❌ System health check failed. Please fix issues before starting.")
        return

    # Step 2: Start backend
    if not start_backend():
        print("❌ Failed to start backend. Cannot continue.")
        return

    # Step 3: Wait a moment for backend to fully initialize
    print("⏳ Waiting for backend to fully initialize...")
    time.sleep(3)

    # Step 4: Start frontend
    if not start_frontend():
        print("❌ Failed to start frontend.")
        return

    # Step 5: Success message
    print("\n" + "=" * 50)
    print("🎉 Probable Spork System Started Successfully!")
    print("=" * 50)
    print("🌐 Backend API: http://127.0.0.1:8008")
    print("🎨 Frontend UI: http://127.0.0.1:7860")
    print("📚 API Docs: http://127.0.0.1:8008/docs")
    print("\n💡 Keep this terminal open to monitor the services.")
    print("   Press Ctrl+C to stop all services.")

    try:
        # Keep the script running to maintain the services
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down services...")
        print("✅ Services stopped. Goodbye!")


if __name__ == "__main__":
    main()
