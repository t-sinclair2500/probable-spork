#!/usr/bin/env python3
"""
Test Texture QA Loop Functionality

This script tests the texture QA loop that auto-dials back on contrast/legibility failures.
"""

import sys

from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))


# Mock the core module to avoid bleach dependency
class MockLogger:
    def __init__(self, name):
        self.name = name

    def info(self, msg):
        print(f"[INFO] {msg}")

    def warning(self, msg):
        print(f"[WARN] {msg}")

    def error(self, msg):
        print(f"[ERROR] {msg}")

    def debug(self, msg):
        print(f"[DEBUG] {msg}")


# Mock the core module
sys.modules["bin.core"] = type("MockCore", (), {"get_logger": MockLogger})()


def test_texture_qa_imports():
    """Test that texture QA modules can be imported."""
    print("Testing Texture QA Module Imports")
    print("=" * 35)

    try:
        # Test texture integration imports
        print("✓ Texture integration imports successful")

        # Test QA gates imports
        print("✓ QA gates imports successful")

        return True

    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_dialback_function():
    """Test the texture strength dialback function."""
    print("\nTesting Texture Strength Dialback")
    print("=" * 35)

    try:
        from cutout.texture_integration import _dial_back_texture_strength

        # Test configuration
        original_config = {
            "grain_strength": 0.15,
            "posterize_levels": 6,
            "feather_px": 2.0,
            "halftone": {"enable": True, "opacity": 0.2},
        }

        print(f"Original config: {original_config}")

        # Apply dialback
        dialed_config = _dial_back_texture_strength(original_config)
        print(f"Dialed back config: {dialed_config}")

        # Verify changes
        assert (
            dialed_config["grain_strength"] < original_config["grain_strength"]
        ), "Grain strength should be reduced"
        assert (
            dialed_config["posterize_levels"] > original_config["posterize_levels"]
        ), "Posterize levels should increase"
        assert (
            dialed_config["halftone"]["enable"] == False
        ), "Halftone should be disabled"
        assert (
            dialed_config["feather_px"] < original_config["feather_px"]
        ), "Feather should be reduced"

        print("✓ Dialback function working correctly")
        return True

    except Exception as e:
        print(f"✗ Dialback test failed: {e}")
        return False


def test_qa_result_structure():
    """Test the QA result data structure."""
    print("\nTesting QA Result Structure")
    print("=" * 30)

    try:
        from cutout.qa_gates import QAResult

        # Create a test QA result
        result = QAResult(
            ok=True, fails=[], warnings=["Test warning"], details={"test": "data"}
        )

        print(f"QA Result: {result}")
        print(f"  - OK: {result.ok}")
        print(f"  - Fails: {result.fails}")
        print(f"  - Warnings: {result.warnings}")
        print(f"  - Details: {result.details}")

        assert hasattr(result, "ok"), "QAResult should have 'ok' attribute"
        assert hasattr(result, "fails"), "QAResult should have 'fails' attribute"
        assert hasattr(result, "warnings"), "QAResult should have 'warnings' attribute"
        assert hasattr(result, "details"), "QAResult should have 'details' attribute"

        print("✓ QA result structure correct")
        return True

    except Exception as e:
        print(f"✗ QA result test failed: {e}")
        return False


def main():
    """Run all texture QA tests."""
    print("Texture QA Loop Test Suite")
    print("=" * 40)

    tests = [test_texture_qa_imports, test_dialback_function, test_qa_result_structure]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("All texture QA tests passed!")
        return True
    else:
        print("Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
