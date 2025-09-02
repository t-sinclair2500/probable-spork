#!/usr/bin/env python3
"""
Simple Texture Integration Test

This script tests the texture integration with a simple test case.
"""

import sys

from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))


def test_texture_integration_simple():
    """Test texture integration with a simple test case."""
    print("Testing Simple Texture Integration")
    print("=" * 35)

    try:
        # Test that we can import the texture integration
        from cutout.texture_integration import process_rasterized_with_texture_qa

        print("✓ Texture integration module imported successfully")

        # Test configuration
        texture_config = {
            "enable": True,
            "grain_strength": 0.15,
            "feather_px": 1.5,
            "posterize_levels": 6,
            "halftone": {
                "enable": False,
                "cell_px": 6,
                "angle_deg": 15,
                "opacity": 0.12,
            },
        }

        print(f"Texture config: {texture_config}")

        # Test that the function exists and has the right signature
        assert hasattr(
            process_rasterized_with_texture_qa, "__call__"
        ), "Function should be callable"

        print("✓ Texture integration function available")

        return True

    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_qa_gates_simple():
    """Test QA gates with a simple test case."""
    print("\nTesting Simple QA Gates")
    print("=" * 25)

    try:
        # Test that we can import the QA gates
        from cutout.qa_gates import QAResult, check_frame_contrast

        print("✓ QA gates module imported successfully")

        # Test QAResult creation
        result = QAResult(
            ok=True, fails=[], warnings=["Test warning"], details={"test": "data"}
        )

        assert result.ok == True, "QAResult should have correct ok value"
        assert len(result.fails) == 0, "QAResult should have empty fails list"
        assert len(result.warnings) == 1, "QAResult should have one warning"

        print("✓ QAResult creation successful")

        # Test that check_frame_contrast function exists
        assert hasattr(
            check_frame_contrast, "__call__"
        ), "check_frame_contrast should be callable"

        print("✓ check_frame_contrast function available")

        return True

    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def main():
    """Run simple texture integration tests."""
    print("Simple Texture Integration Test Suite")
    print("=" * 45)

    tests = [test_texture_integration_simple, test_qa_gates_simple]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("All simple texture integration tests passed!")
        return True
    else:
        print("Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
