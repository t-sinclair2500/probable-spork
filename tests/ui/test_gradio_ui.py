#!/usr/bin/env python3
"""Test script for Gradio UI"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_gradio_import():
    """Test that Gradio can be imported"""
    try:
        import gradio as gr
        print("✅ Gradio imported successfully")
        print(f"Gradio version: {gr.__version__}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import Gradio: {e}")
        return False

def test_ui_creation():
    """Test that the UI can be created"""
    try:
        from ui.gradio_app import create_ui
        print("✅ UI module imported successfully")
        
        # Create UI (this will test the creation logic)
        ui = create_ui()
        print("✅ UI created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create UI: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_client():
    """Test API client creation"""
    try:
        from ui.gradio_app import APIClient
        print("✅ API client class imported successfully")
        
        # Test client creation
        client = APIClient("test-token")
        print("✅ API client created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create API client: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("Testing Gradio UI components...")
    print("=" * 50)
    
    tests = [
        ("Gradio Import", test_gradio_import),
        ("UI Creation", test_ui_creation),
        ("API Client", test_api_client),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Testing: {test_name}")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All tests passed! Gradio UI is ready to use.")
        print("\nTo launch the UI:")
        print("  make gradio-ui          # Launch Gradio UI only")
        print("  make op-console-full    # Launch FastAPI + Gradio UI")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
