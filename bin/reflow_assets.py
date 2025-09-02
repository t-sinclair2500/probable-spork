#!/usr/bin/env python3
"""
Asset Reflow Wrapper

This script is a compatibility wrapper for the storyboard reflow functionality.
It maintains the CLI interface expected by the Makefile while calling the
underlying storyboard_reflow.py module.
"""

import subprocess
import sys

from pathlib import Path


def main():
    """Main entry point that calls storyboard_reflow.py with the same arguments."""
    # Get the script directory
    script_dir = Path(__file__).parent

    # Build the command to call storyboard_reflow.py
    storyboard_reflow_path = script_dir / "storyboard_reflow.py"

    if not storyboard_reflow_path.exists():
        print(f"Error: storyboard_reflow.py not found at {storyboard_reflow_path}")
        sys.exit(1)

    # Pass through all arguments
    cmd = [sys.executable, str(storyboard_reflow_path)] + sys.argv[1:]

    try:
        # Run the storyboard reflow script
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error running storyboard_reflow.py: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
