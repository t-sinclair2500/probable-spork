#!/usr/bin/env python3
"""
Legacy fetch_assets.py shim - routes to legacy implementation or no-ops based on config
"""

import os
import sys

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger, load_config

log = get_logger("fetch_assets")

def main():
    """Main entry point - routes to legacy or no-ops"""
    try:
        cfg = load_config()
        
        # Check if animatics_only mode is enabled
        animatics_only = cfg.get("video", {}).get("animatics_only", True)
        enable_legacy = cfg.get("video", {}).get("enable_legacy_stock", False)
        
        if animatics_only and not enable_legacy:
            log.warning("LEGACY DISABLED (animatics_only=true); skipping fetch_assets")
            log.info("Pipeline is in animatics-only mode - stock assets not needed")
            return 0
        
        # Legacy mode enabled - delegate to legacy implementation
        log.info("Legacy mode enabled - delegating to legacy fetch_assets")
        
        # Import and run legacy implementation
        sys.path.insert(0, os.path.join(ROOT, "legacy"))
        from fetch_assets import main as legacy_main
        return legacy_main()
        
    except Exception as e:
        log.error(f"Error in fetch_assets shim: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
