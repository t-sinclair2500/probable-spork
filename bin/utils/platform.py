# bin/utils/platform.py
from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Optional


def is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system().lower() == "darwin"


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system().lower() == "linux"


def is_linux_arm() -> bool:
    """Check if running on Linux ARM (Raspberry Pi, etc.)."""
    if not is_linux():
        return False
    # ARM if machine contains 'arm' or 'aarch64'
    mach = (platform.machine() or "").lower()
    return "arm" in mach or "aarch64" in mach


def has_vcgencmd() -> bool:
    """Check if vcgencmd is available (Raspberry Pi thermal monitoring)."""
    return shutil.which("vcgencmd") is not None


def read_pi_cpu_temp_celsius(default: Optional[float] = None) -> Optional[float]:
    """
    Returns temperature in Celsius using vcgencmd on Raspberry Pi.
    None if unavailable or error.
    """
    if not (is_linux_arm() and has_vcgencmd()):
        return default
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True).strip()
        # example: temp=41.2'C
        if "=" in out:
            val = out.split("=")[1].split("'")[0]
            return float(val)
        return default
    except Exception:
        return default


def get_platform_info() -> dict:
    """Get comprehensive platform information."""
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "is_macos": is_macos(),
        "is_linux": is_linux(),
        "is_linux_arm": is_linux_arm(),
        "has_vcgencmd": has_vcgencmd(),
        "python_version": platform.python_version(),
    }


def get_recommended_profile() -> str:
    """Get recommended profile based on platform detection."""
    if is_macos():
        return "m2_8gb_optimized"
    elif is_linux_arm():
        return "pi_8gb"
    else:
        return "default"  # fallback
