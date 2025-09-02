#!/usr/bin/env python3
"""
Start script for Probable Spork development environment.
Detects project type and starts the appropriate services.
"""

import json
import shutil
import subprocess
import sys

from pathlib import Path


def detect_project_type():
    """Detect the type of project and return appropriate startup method."""

    # Check for FastAPI + Gradio setup (current project structure)
    if Path("fastapi_app").exists() and Path("ui/gradio_app.py").exists():
        return "fastapi_gradio"

    # Check for Streamlit app
    if Path("streamlit_app.py").exists():
        return "streamlit"

    # Check for Node.js web app
    if Path("package.json").exists():
        with open("package.json", "r") as f:
            try:
                pkg_data = json.load(f)
                if "scripts" in pkg_data and "dev" in pkg_data["scripts"]:
                    return "node_dev"
            except json.JSONDecodeError:
                pass

    # Check for simple Python app
    if Path("app/main.py").exists():
        return "python_app"

    # Check for basic Python script
    if Path("main.py").exists():
        return "python_main"

    return "unknown"


def start_fastapi_gradio():
    """Start FastAPI + Gradio development environment."""
    print("🚀 Starting FastAPI + Gradio development environment...")
    print("   FastAPI: http://127.0.0.1:8008")
    print("   Gradio UI: http://127.0.0.1:7860")
    print("   Admin token: default-admin-token-change-me")
    print()

    # Start FastAPI server in background
    print("Starting FastAPI server...")
    try:
        fastapi_process = subprocess.Popen(
            [sys.executable, "run_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("✅ FastAPI server started (PID: {})".format(fastapi_process.pid))
    except Exception as e:
        print(f"❌ Failed to start FastAPI server: {e}")
        return False

    # Wait a moment for FastAPI to start
    import time

    time.sleep(3)

    # Start Gradio UI
    print("Starting Gradio UI...")
    try:
        gradio_process = subprocess.Popen([sys.executable, "-m", "ui.gradio_app"])
        print("✅ Gradio UI started (PID: {})".format(gradio_process.pid))
    except Exception as e:
        print(f"❌ Failed to start Gradio UI: {e}")
        fastapi_process.terminate()
        return False

    print()
    print("🎉 Development environment started successfully!")
    print("   Press Ctrl+C to stop all services")

    try:
        # Wait for user to stop
        fastapi_process.wait()
        gradio_process.terminate()
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
        fastapi_process.terminate()
        gradio_process.terminate()
        print("✅ Services stopped")

    return True


def start_streamlit():
    """Start Streamlit development server."""
    print("🚀 Starting Streamlit development server...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "streamlit", "run", "streamlit_app.py"]
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Streamlit: {e}")
        return False
    except FileNotFoundError:
        print("❌ Streamlit not installed. Install with: pip install streamlit")
        return False


def start_node_dev():
    """Start Node.js development server."""
    print("🚀 Starting Node.js development server...")

    # Detect package manager
    package_managers = ["pnpm", "yarn", "npm"]
    active_manager = None

    for manager in package_managers:
        if shutil.which(manager):
            active_manager = manager
            break

    if not active_manager:
        print("❌ No Node.js package manager found. Install Node.js first.")
        return False

    print(f"Using {active_manager}...")
    try:
        subprocess.check_call([active_manager, "run", "dev"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Node.js dev server: {e}")
        return False


def start_python_app():
    """Start Python application from app/main.py."""
    print("🚀 Starting Python application...")
    try:
        subprocess.check_call([sys.executable, "app/main.py"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Python app: {e}")
        return False


def start_python_main():
    """Start Python application from main.py."""
    print("🚀 Starting Python application...")
    try:
        subprocess.check_call([sys.executable, "main.py"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Python app: {e}")
        return False


def show_todo():
    """Show TODO message for unknown project types."""
    print("❓ Project type not recognized")
    print()
    print("📋 Next steps:")
    print("   1. Create a FastAPI + Gradio setup:")
    print("      - Add fastapi_app/ directory with FastAPI app")
    print("      - Add ui/gradio_app.py for Gradio interface")
    print("      - Add run_server.py for FastAPI server")
    print()
    print("   2. Or create a Streamlit app:")
    print("      - Add streamlit_app.py")
    print("      - Install streamlit: pip install streamlit")
    print()
    print("   3. Or create a Node.js web app:")
    print("      - Add package.json with 'dev' script")
    print("      - Install Node.js and npm/yarn/pnpm")
    print()
    print("   4. Or create a simple Python app:")
    print("      - Add app/main.py or main.py")
    print()
    print("   Then run 'make start' again!")


def main():
    """Main start function."""
    print("🚀 Probable Spork - Development Environment Starter")
    print("=" * 50)

    # Detect project type
    project_type = detect_project_type()
    print(f"🔍 Detected project type: {project_type}")
    print()

    # Start appropriate service
    success = False

    if project_type == "fastapi_gradio":
        success = start_fastapi_gradio()
    elif project_type == "streamlit":
        success = start_streamlit()
    elif project_type == "node_dev":
        success = start_node_dev()
    elif project_type == "python_app":
        success = start_python_app()
    elif project_type == "python_main":
        success = start_python_main()
    else:
        show_todo()
        return 1

    if success:
        print("✅ Development environment started successfully!")
        return 0
    else:
        print("❌ Failed to start development environment")
        return 1


if __name__ == "__main__":
    sys.exit(main())
