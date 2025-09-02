#!/usr/bin/env python3
"""
Probable Spork Operator Console UI
Python equivalent of serve_ui.sh for cross-platform compatibility
Gradio interface for pipeline management
"""

import argparse
import os
import subprocess
import sys

from pathlib import Path


def get_env_config():
    """Get configuration from environment variables with defaults."""
    return {
        "port": int(os.getenv("UI_PORT", "7860")),
        "share": os.getenv("UI_SHARE", "false").lower() == "true",
        "debug": os.getenv("UI_DEBUG", "false").lower() == "true",
    }


def check_virtual_environment():
    """Check if virtual environment exists."""
    venv_paths = [
        Path("venv"),
        Path(".venv"),
        Path("venv/bin/activate"),
        Path(".venv/Scripts/activate"),
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
        print("✅ Gradio package found")
        return True
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        print("Installing required packages...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "gradio"])
            print("✅ Gradio installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install Gradio: {e}")
            return False


def check_gradio_app():
    """Check if the Gradio app file exists."""
    app_path = Path("ui/gradio_app.py")
    if app_path.exists():
        print(f"✅ Gradio app found: {app_path}")
        return True
    else:
        print(f"❌ Gradio app not found: {app_path}")
        print("   Make sure ui/gradio_app.py exists")
        return False


def start_gradio(config):
    """Start the Gradio UI."""
    print("🚀 Starting Probable Spork Operator Console UI...")
    print(f"   Port: {config['port']}")
    print(f"   Share: {config['share']}")
    print(f"   Debug: {config['debug']}")
    print()

    # Build environment variables for Gradio
    env = os.environ.copy()
    env["GRADIO_SERVER_PORT"] = str(config["port"])
    env["GRADIO_SERVER_NAME"] = "127.0.0.1"

    if config["share"]:
        env["GRADIO_SHARE"] = "true"

    if config["debug"]:
        env["GRADIO_DEBUG"] = "true"

    # Start Gradio app
    try:
        print("Starting Gradio UI...")
        cmd = [sys.executable, "-m", "ui.gradio_app"]
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Gradio failed to start: {e}")
        return False
    except KeyboardInterrupt:
        print("\n🛑 Gradio stopped by user")
        return True

    return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Start Gradio UI")
    parser.add_argument("--port", type=int, help="Port to bind to")
    parser.add_argument("--share", action="store_true", help="Enable public sharing")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Get configuration (CLI args override env vars)
    config = get_env_config()
    if args.port:
        config["port"] = args.port
    if args.share:
        config["share"] = True
    if args.debug:
        config["debug"] = True

    print("🎨 Probable Spork - Gradio UI")
    print("=" * 40)

    # Check environment
    if not check_virtual_environment():
        print("⚠️  Continuing without virtual environment...")

    if not check_packages():
        print("❌ Cannot start UI without Gradio")
        sys.exit(1)

    if not check_gradio_app():
        print("❌ Cannot start UI without app file")
        sys.exit(1)

    # Start Gradio
    success = start_gradio(config)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
