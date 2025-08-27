#!/usr/bin/env python3
"""
Simple test launcher that sets up the Python path correctly
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_basic_tests():
    """Run basic functionality tests"""
    print("🧪 Running Basic Functionality Tests")
    print("=" * 50)
    
    try:
        from bin.core import get_logger
        print("✅ Core module imported successfully")
        
        log = get_logger('test_runner')
        print("✅ Logger created successfully")
        
        # Test configuration loading
        from bin.core import load_config
        config = load_config()
        print("✅ Configuration loaded successfully")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def run_svg_demo():
    """Run SVG path operations demo"""
    print("\n🎨 Running SVG Path Operations Demo")
    print("=" * 50)
    
    try:
        import demo_svg_path_ops
        print("✅ SVG demo completed")
        return True
    except Exception as e:
        print(f"❌ SVG demo failed: {e}")
        return False

def run_texture_demo():
    """Run texture effects demo"""
    print("\n🎨 Running Texture Effects Demo")
    print("=" * 50)
    
    try:
        import demo_texture_effects
        print("✅ Texture demo completed")
        return True
    except Exception as e:
        print(f"❌ Texture demo failed: {e}")
        return False

def main():
    """Main test runner"""
    print("🚀 Probable Spork Test Suite")
    print("=" * 50)
    
    tests = [
        ("Basic Functionality", run_basic_tests),
        ("SVG Path Operations", run_svg_demo),
        ("Texture Effects", run_texture_demo),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The system is ready to use.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()
