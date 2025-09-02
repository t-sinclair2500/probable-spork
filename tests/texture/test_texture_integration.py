#!/usr/bin/env python3
"""
Test Texture Engine Integration

This script tests the texture engine integration with real images
to verify the P3-1 implementation works correctly.
"""

import sys

from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))

try:
    from cutout.texture_engine import apply_textures_to_frame, texture_signature
    from cutout.texture_integration import apply_texture_to_image
    from PIL import Image, ImageDraw

    def test_texture_integration():
        """Test texture integration with a real image."""
        print("Testing Texture Engine Integration")
        print("=" * 40)

        # Create a test image
        test_img = Image.new("RGB", (300, 200), color="white")
        draw = ImageDraw.Draw(test_img)

        # Draw some test content
        draw.rectangle(
            [50, 50, 250, 150], fill="lightblue", outline="darkblue", width=3
        )
        draw.text((100, 80), "Texture Test", fill="black")
        draw.text((100, 100), "Integration", fill="black")

        # Save test image
        test_path = "test_integration_image.png"
        test_img.save(test_path)
        print(f"Created test image: {test_path}")

        # Test texture configuration
        texture_config = {
            "enable": True,
            "grain_strength": 0.15,
            "feather_px": 1.0,
            "posterize_levels": 4,
            "halftone": {"enable": True, "cell_px": 8, "angle_deg": 30, "opacity": 0.1},
        }

        print(f"Texture config: {texture_config}")
        print(f"Texture signature: {texture_signature(texture_config)}")

        # Test direct texture application
        print("\nTesting direct texture application...")
        seed = 42
        textured_img = apply_textures_to_frame(test_img, texture_config, seed)

        # Save textured image
        textured_path = "test_integration_textured.png"
        textured_img.save(textured_path)
        print(f"Saved textured image: {textured_path}")

        # Test integration function
        print("\nTesting texture integration function...")
        integrated_path = apply_texture_to_image(test_path, texture_config)
        print(f"Integration result: {integrated_path}")

        # Verify files exist
        assert Path(test_path).exists(), "Test image should exist"
        assert Path(textured_path).exists(), "Textured image should exist"
        assert Path(integrated_path).exists(), "Integrated image should exist"

        print("\n✓ All texture integration tests passed!")

        # Clean up test files
        for path in [test_path, textured_path, integrated_path]:
            if Path(path).exists():
                Path(path).unlink()
                print(f"Cleaned up: {path}")

        return True

    def test_cache_behavior():
        """Test that texture caching works correctly."""
        print("\nTesting Texture Cache Behavior")
        print("=" * 35)

        # Create test image
        test_img = Image.new("RGB", (100, 100), color="red")
        test_path = "test_cache_image.png"
        test_img.save(test_path)

        texture_config = {
            "enable": True,
            "grain_strength": 0.2,
            "feather_px": 0.5,
            "posterize_levels": 3,
        }

        # Apply textures twice with same config
        print("Applying textures first time...")
        result1 = apply_texture_to_image(test_path, texture_config)

        print("Applying textures second time...")
        result2 = apply_texture_to_image(test_path, texture_config)

        # Results should be the same (deterministic)
        assert result1 == result2, "Cache should return same result for same config"
        print("✓ Cache behavior test passed")

        # Clean up
        for path in [test_path, result1]:
            if Path(path).exists():
                Path(path).unlink()

        return True

    def main():
        """Run all tests."""
        print("Texture Engine Integration Test Suite (P3-1)")
        print("=" * 50)

        try:
            test_texture_integration()
            test_cache_behavior()

            print("\n🎉 All tests passed successfully!")
            print("\nTexture Engine Core (P3-1) is working correctly!")

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

        return True

    if __name__ == "__main__":
        success = main()
        sys.exit(0 if success else 1)

except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you have the required dependencies installed:")
    print("pip install Pillow numpy")
    sys.exit(1)
except Exception as e:
    print(f"Test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
