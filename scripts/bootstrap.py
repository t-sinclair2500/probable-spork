#!/usr/bin/env python3
"""
Bootstrap script for Probable Spork development environment.
Validates configuration and creates required local directories.
"""

import os
import sys
import shutil
from pathlib import Path

def check_env_file():
    """Check for environment configuration file."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("✅ Environment file (.env) found")
        return True
    elif env_example.exists():
        print("⚠️  .env file missing!")
        print("   Copy .env.example to .env and configure your settings:")
        print("   cp .env.example .env")
        print("   # Edit .env with your API keys and configuration")
        return False
    else:
        print("⚠️  No .env or .env.example found")
        print("   Create a .env file with your configuration:")
        print("   # Example .env contents:")
        print("   # PIXABAY_API_KEY=your_key_here")
        print("   # PEXELS_API_KEY=your_key_here")
        print("   # BLOG_DRY_RUN=true")
        print("   # YOUTUBE_UPLOAD_DRY_RUN=true")
        return False

def create_local_directories():
    """Create required local directories if they don't exist."""
    directories = [
        "data",
        "data/cache",
        "data/analytics",
        "logs",
        "temp",
        "exports",
        "exports/blog",
        "runs",
        "assets",
        "videos",
        "voiceovers",
        "thumbnails"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created directory: {directory}")
        else:
            print(f"📁 Directory exists: {directory}")

def check_python_version():
    """Check Python version compatibility."""
    version = sys.version_info
    if version.major == 3 and version.minor in [9, 10, 11]:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - compatible")
        return True
    else:
        print(f"⚠️  Python {version.major}.{version.minor}.{version.micro} - may have compatibility issues")
        print("   This project is tested with Python 3.9, 3.10, and 3.11")
        return True  # Don't fail, just warn

def check_virtual_environment():
    """Check if running in a virtual environment."""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Running in virtual environment")
        return True
    else:
        print("⚠️  Not running in virtual environment")
        print("   Consider using: make setup")
        return True  # Don't fail, just warn

def check_requirements():
    """Check if requirements.txt exists."""
    if Path("requirements.txt").exists():
        print("✅ Requirements file found")
        return True
    else:
        print("⚠️  No requirements.txt found")
        return False

def main():
    """Main bootstrap function."""
    print("🚀 Probable Spork - Development Environment Bootstrap")
    print("=" * 50)
    
    # Check Python version
    check_python_version()
    print()
    
    # Check virtual environment
    check_virtual_environment()
    print()
    
    # Check requirements
    check_requirements()
    print()
    
    # Check environment file
    env_ok = check_env_file()
    print()
    
    # Create local directories
    print("📁 Setting up local directories...")
    create_local_directories()
    print()
    
    # Summary
    if env_ok:
        print("✅ Bootstrap complete! Environment is ready.")
        print("   Run 'make start' to begin development.")
    else:
        print("⚠️  Bootstrap complete with warnings.")
        print("   Please configure your .env file before proceeding.")
        print("   Run 'make start' when ready.")
    
    return 0 if env_ok else 1

if __name__ == "__main__":
    sys.exit(main())
