#!/usr/bin/env python3
"""
Wrapper script to ensure correct Python version (3.11) is used for compatibility.
This script checks the Python version and provides helpful guidance.
"""

import sys
import subprocess
import os

def check_python_version():
    """Check if we're running the correct Python version."""
    version = sys.version_info
    if version.major == 3 and version.minor == 11:
        return True, f"✓ Using Python {version.major}.{version.minor}.{version.micro} (compatible)"
    else:
        return False, f"✗ Using Python {version.major}.{version.minor}.{version.micro} (incompatible - need 3.11.x)"

def get_venv_python():
    """Get the path to the virtual environment Python."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    venv_python = os.path.join(project_root, "venv", "bin", "python")
    
    if os.path.exists(venv_python):
        return venv_python
    return None

def main():
    """Main function to check Python version and provide guidance."""
    print("Python Version Compatibility Check")
    print("=" * 40)
    
    # Check current Python version
    is_compatible, version_msg = check_python_version()
    print(version_msg)
    
    # Get virtual environment path
    venv_python = get_venv_python()
    
    if is_compatible:
        print("\n✅ You're using the correct Python version!")
        print("   You can run your scripts directly.")
        return 0
    
    else:
        print("\n⚠️  Python version compatibility issue detected!")
        print("   This project requires Python 3.11.x for stability.")
        
        if venv_python and os.path.exists(venv_python):
            print(f"\n💡 Solution: Use the virtual environment Python:")
            print(f"   {venv_python}")
            print("\n   Examples:")
            print(f"   {venv_python} bin/assemble_video.py")
            print(f"   {venv_python} bin/generate_captions.py")
            print(f"   {venv_python} bin/test_hardware_acceleration.py")
            
            # Check if virtual environment Python is 3.11
            try:
                result = subprocess.run([venv_python, "--version"], 
                                     capture_output=True, text=True, check=True)
                venv_version = result.stdout.strip()
                if "3.11" in venv_version:
                    print(f"\n✅ Virtual environment has correct version: {venv_version}")
                else:
                    print(f"\n⚠️  Virtual environment version: {venv_version}")
            except Exception as e:
                print(f"\n❌ Error checking virtual environment: {e}")
        else:
            print("\n❌ Virtual environment not found!")
            print("   Run: python3 -m venv venv")
            print("   Then: source venv/bin/activate")
        
        print("\n📚 For more information, see: video_encoding_optimizations.md")
        return 1

if __name__ == "__main__":
    sys.exit(main())
