#!/usr/bin/env python3
"""
Test Texture QA Loop Fixing Contrast Issues

This script demonstrates how the texture QA loop automatically fixes contrast issues
by dialing back texture strength until legibility passes.
"""

import sys

from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))


def test_texture_qa_fix():
    """Test that texture QA loop fixes contrast issues."""
    print("Testing Texture QA Loop Fixing Contrast Issues")
    print("=" * 55)

    try:
        # Import the texture QA loop
        from cutout.texture_integration import apply_texture_with_qa_loop

        # Create a test image with poor contrast (black text on dark blue background)
        from PIL import Image, ImageDraw

        # Create test image with poor contrast
        test_img = Image.new("RGB", (400, 300), color="#1C4FA1")  # Dark blue background
        draw = ImageDraw.Draw(test_img)

        # Draw black text on dark blue (poor contrast)
        draw.text((50, 150), "Poor Contrast Text", fill="#000000")  # Black text

        # Save original image
        test_img.save("test_contrast_original.png")
        print("Created test image with poor contrast (black text on dark blue)")

        # Test aggressive texture config that should trigger QA failures
        aggressive_texture_config = {
            "enable": True,
            "grain_strength": 0.8,  # Very strong grain
            "feather_px": 5.0,  # Heavy feathering
            "posterize_levels": 2,  # Very aggressive posterization
            "halftone": {"enable": True, "cell_px": 4, "angle_deg": 15, "opacity": 0.8},
        }

        print("\nTesting with aggressive texture config:")
        print(f"  - Grain strength: {aggressive_texture_config['grain_strength']}")
        print(f"  - Feather: {aggressive_texture_config['feather_px']}px")
        print(f"  - Posterize levels: {aggressive_texture_config['posterize_levels']}")
        print("  - Halftone: enabled")

        # Run the QA loop
        print("\nRunning texture QA loop...")
        result_img, metadata = apply_texture_with_qa_loop(
            test_img, aggressive_texture_config, seed=42, max_retries=2
        )

        # Analyze results
        print("\nQA loop completed:")
        print(f"  - Applied: {metadata['textures']['applied']}")
        print(f"  - Attempts: {metadata['textures']['attempts']}")
        print(f"  - Dialback applied: {metadata['textures']['dialback_applied']}")

        if metadata["textures"]["dialback_applied"]:
            print(
                f"  - Final grain strength: {metadata['textures']['final_params']['grain_strength']:.3f}"
            )
            print(
                f"  - Final posterize levels: {metadata['textures']['final_params']['posterize_levels']}"
            )
            print(
                f"  - Final halftone enabled: {metadata['textures']['final_params']['halftone']['enable']}"
            )

        # Save result image
        result_img.save("test_contrast_fixed.png")
        print("\nSaved result image: test_contrast_fixed.png")

        # Check if QA loop worked
        if metadata["textures"]["applied"] and metadata["textures"]["dialback_applied"]:
            print(
                "✓ Texture QA loop successfully applied dialback to fix contrast issues"
            )
            return True
        else:
            print("✗ Texture QA loop did not work as expected")
            return False

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_texture_qa_fix()
    if success:
        print("\n🎯 Texture QA loop test PASSED")
    else:
        print("\n💥 Texture QA loop test FAILED")
