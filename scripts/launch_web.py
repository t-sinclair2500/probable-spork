#!/usr/bin/env python3
"""
Simple web interface launcher for Probable Spork
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def launch_gradio():
    """Launch the Gradio UI"""
    print("🎨 Launching Gradio UI...")
    try:
        import ui.gradio_app
        print("✅ Gradio UI launched successfully")
        print("🌐 Open your browser to: http://127.0.0.1:7860")
    except Exception as e:
        print(f"❌ Failed to launch Gradio UI: {e}")
        return False
    return True

def launch_fastapi():
    """Launch the FastAPI server"""
    print("🚀 Launching FastAPI server...")
    try:
        import run_server
        print("✅ FastAPI server launched successfully")
        print("🌐 Open your browser to: http://127.0.0.1:8008")
    except Exception as e:
        print(f"❌ Failed to launch FastAPI server: {e}")
        return False
    return True

def main():
    """Main launcher"""
    print("🚀 Probable Spork Web Interface Launcher")
    print("=" * 50)
    
    print("Choose an interface to launch:")
    print("1. Gradio UI (Simple web interface)")
    print("2. FastAPI Server (Full backend API)")
    print("3. Run tests first")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        launch_gradio()
    elif choice == "2":
        launch_fastapi()
    elif choice == "3":
        print("\n🧪 Running tests first...")
        import run_tests
        print("\nNow choose an interface to launch:")
        choice = input("Enter your choice (1-2): ").strip()
        if choice == "1":
            launch_gradio()
        elif choice == "2":
            launch_fastapi()
        else:
            print("Invalid choice")
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()
