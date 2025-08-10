#!/usr/bin/env python3
"""
Test script to verify hardware acceleration availability.
Run this to check if VideoToolbox is available on your Mac.
"""

import subprocess
import sys

def check_videotoolbox():
    """Check if VideoToolbox hardware acceleration is available."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        
        if result.returncode == 0:
            if "h264_videotoolbox" in result.stdout:
                print("✓ VideoToolbox hardware acceleration is available")
                print("  - Codec: h264_videotoolbox")
                print("  - This will provide 3-5x faster video encoding")
                return True
            else:
                print("✗ VideoToolbox hardware acceleration is NOT available")
                print("  - Falling back to software encoding (libx264)")
                return False
        else:
            print("✗ Could not run ffmpeg -encoders")
            print(f"  - Error: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("✗ ffmpeg not found in PATH")
        print("  - Install ffmpeg to use hardware acceleration")
        return False
    except Exception as e:
        print(f"✗ Error checking VideoToolbox: {e}")
        return False

def check_ffmpeg_version():
    """Check ffmpeg version and build info."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            version_line = lines[0] if lines else "Unknown"
            print(f"ffmpeg version: {version_line}")
            
            # Check for VideoToolbox in build info
            if "videotoolbox" in result.stdout.lower():
                print("✓ VideoToolbox support compiled into ffmpeg")
            else:
                print("⚠ VideoToolbox support not found in ffmpeg build")
                
        else:
            print("Could not get ffmpeg version")
            
    except Exception as e:
        print(f"Error checking ffmpeg version: {e}")

if __name__ == "__main__":
    print("Hardware Acceleration Test for Video Encoding")
    print("=" * 50)
    
    check_ffmpeg_version()
    print()
    
    has_hw = check_videotoolbox()
    print()
    
    if has_hw:
        print("Your system is ready for hardware-accelerated video encoding!")
        print("Update your conf/global.yaml to use:")
        print("  codec: 'h264_videotoolbox'")
        print("  use_hardware_acceleration: true")
    else:
        print("Hardware acceleration not available.")
        print("Your system will use software encoding (slower but compatible).")
        print("Update your conf/global.yaml to use:")
        print("  codec: 'libx264'")
        print("  use_hardware_acceleration: false")
    
    print()
    print("Run 'python bin/assemble_video.py' to test with your configuration.")
