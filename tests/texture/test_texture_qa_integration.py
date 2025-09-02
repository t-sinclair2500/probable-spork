#!/usr/bin/env python3
"""
Test Texture QA Integration with Simple Image

This script tests the texture QA integration directly with a simple image.
"""

import sys

from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))


def test_texture_qa_integration():
    """Test texture QA integration with a simple image."""
    print("Testing Texture QA Integration")
    print("=" * 35)

    try:
        # Create a simple test image
        from PIL import Image, ImageDraw

        # Create a test image
        test_img = Image.new("RGB", (200, 200), color="white")
        draw = ImageDraw.Draw(test_img)

        # Draw some test content
        draw.rectangle(
            [50, 50, 150, 150], fill="lightblue", outline="darkblue", width=3
        )
        draw.text((70, 80), "Test", fill="black")

        # Save test image
        test_path = "test_texture_image.png"
        test_img.save(test_path)
        print(f"Created test image: {test_path}")

        # Test texture configuration that should trigger QA failures
        aggressive_texture_config = {
            "enable": True,
            "grain_strength": 0.8,  # Very strong grain
            "feather_px": 5.0,  # Heavy feathering
            "posterize_levels": 2,  # Very aggressive posterization
            "halftone": {"enable": True, "cell_px": 4, "angle_deg": 15, "opacity": 0.8},
        }

        print(f"Testing with aggressive texture config: {aggressive_texture_config}")

        # Import and test the texture QA loop
        from cutout.texture_integration import apply_texture_with_qa_loop

        # Run the QA loop
        result_img, metadata = apply_texture_with_qa_loop(
            test_img, aggressive_texture_config, seed=42, max_retries=2
        )

        print("Texture QA loop completed")
        print(f"  - Applied: {metadata['textures']['applied']}")
        print(f"  - Attempts: {metadata['textures']['attempts']}")
        print(f"  - Dialback applied: {metadata['textures']['dialback_applied']}")
        print(f"  - Final params: {metadata['textures']['final_params']}")

        # Save the result
        result_path = "test_texture_result.png"
        result_img.save(result_path)
        print(f"Saved result image: {result_path}")

        # Verify the results
        assert metadata["textures"]["applied"] == True, "Texture should be applied"
        assert metadata["textures"]["attempts"] >= 1, "Should have at least one attempt"

        # If dialback was applied, verify the parameters were reduced
        if metadata["textures"]["dialback_applied"]:
            final_config = metadata["textures"]["final_params"]
            original_config = aggressive_texture_config

            assert (
                final_config["grain_strength"] < original_config["grain_strength"]
            ), "Grain strength should be reduced"
            assert (
                final_config["posterize_levels"] > original_config["posterize_levels"]
            ), "Posterize levels should increase"
            assert (
                final_config["halftone"]["enable"] == False
            ), "Halftone should be disabled on aggressive config"

            print("✓ Dialback was applied correctly")

        # Clean up test files
        for path in [test_path, result_path]:
            if Path(path).exists():
                Path(path).unlink()
                print(f"Cleaned up: {path}")

        print("✓ Texture QA integration test passed!")
        return True

    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run texture QA integration test."""
    print("Texture QA Integration Test")
    print("=" * 35)

    if test_texture_qa_integration():
        print("\n🎉 Texture QA integration test passed!")
        return True
    else:
        print("\n❌ Texture QA integration test failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
