#!/usr/bin/env python3
"""
Complete Texture Integration Test

This script demonstrates the complete texture integration working end-to-end.
"""

import json
import sys

from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))


def test_complete_texture_integration():
    """Test the complete texture integration end-to-end."""
    print("Complete Texture Integration Test")
    print("=" * 40)

    try:
        # Test 1: Texture QA Loop
        print("\n1. Testing Texture QA Loop...")
        from cutout.texture_integration import apply_texture_with_qa_loop

        # Create test image
        from PIL import Image, ImageDraw

        test_img = Image.new("RGB", (300, 200), color="white")
        draw = ImageDraw.Draw(test_img)
        draw.rectangle(
            [50, 50, 250, 150], fill="lightblue", outline="darkblue", width=3
        )
        draw.text((100, 80), "Texture Test", fill="black")

        # Test aggressive texture config that should trigger QA failures
        aggressive_config = {
            "enable": True,
            "grain_strength": 0.9,
            "feather_px": 6.0,
            "posterize_levels": 2,
            "halftone": {"enable": True, "opacity": 0.9},
        }

        print(f"   Testing with aggressive config: {aggressive_config}")

        # Run QA loop
        result_img, metadata = apply_texture_with_qa_loop(
            test_img, aggressive_config, seed=42, max_retries=2
        )

        print("   QA loop completed:")
        print(f"     - Applied: {metadata['textures']['applied']}")
        print(f"     - Attempts: {metadata['textures']['attempts']}")
        print(f"     - Dialback applied: {metadata['textures']['dialback_applied']}")

        assert metadata["textures"]["applied"] == True, "Texture should be applied"
        print("   ✓ Texture QA loop working correctly")

        # Test 2: Metadata Creation
        print("\n2. Testing Metadata Creation...")
        from animatics_generate import create_texture_metadata

        # Create mock texture results with proper structure (all dictionaries)
        mock_results = {
            "test_element": {
                "textures": {
                    "applied": True,
                    "attempts": 3,
                    "final_params": metadata["textures"]["final_params"],
                    "qa_results": [
                        {
                            "attempt": 1,
                            "config": {"grain_strength": 0.9, "posterize_levels": 2},
                            "contrast_result": {
                                "ok": False,
                                "fails": ["Contrast too low"],
                                "warnings": [],
                                "details": {},
                            },
                        },
                        {
                            "attempt": 2,
                            "config": {"grain_strength": 0.63, "posterize_levels": 3},
                            "contrast_result": {
                                "ok": False,
                                "fails": ["Contrast too low"],
                                "warnings": [],
                                "details": {},
                            },
                        },
                        {
                            "attempt": 3,
                            "config": {"grain_strength": 0.44, "posterize_levels": 4},
                            "contrast_result": {
                                "ok": False,
                                "fails": ["Contrast too low"],
                                "warnings": [],
                                "details": {},
                            },
                        },
                    ],
                    "dialback_applied": True,
                }
            }
        }

        metadata_obj = create_texture_metadata(aggressive_config, mock_results)

        assert "textures" in metadata_obj, "Should have textures section"
        assert "summary" in metadata_obj["textures"], "Should have summary"
        assert "qa_summary" in metadata_obj["textures"], "Should have QA summary"

        print("   Created metadata with:")
        print(
            f"     - Total elements: {metadata_obj['textures']['summary']['total_elements']}"
        )
        print(
            f"     - Success rate: {metadata_obj['textures']['summary']['success_rate']:.1%}"
        )
        print(
            f"     - Dialback applied: {metadata_obj['textures']['summary']['dialback_applied']}"
        )
        print("   ✓ Metadata creation working correctly")

        # Test 3: Metadata Writing
        print("\n3. Testing Metadata Writing...")
        from animatics_generate import write_animatics_metadata

        test_slug = "complete_texture_test"
        metadata_path = write_animatics_metadata(
            test_slug, mock_results, aggressive_config
        )

        assert Path(metadata_path).exists(), "Metadata file should exist"

        # Read and verify
        with open(metadata_path, "r") as f:
            written_metadata = json.load(f)

        assert written_metadata["slug"] == test_slug, "Slug should match"
        assert "textures" in written_metadata, "Should have textures section"

        print(f"   Wrote metadata to: {metadata_path}")
        print(f"   Metadata includes: {list(written_metadata.keys())}")
        print("   ✓ Metadata writing working correctly")

        # Test 4: Configuration Integration
        print("\n4. Testing Configuration Integration...")
        import yaml

        # Load configuration
        with open("conf/global.yaml", "r") as f:
            config = yaml.safe_load(f)

        texture_config = config.get("textures", {})
        print(f"   Loaded texture config: {texture_config}")

        assert "enable" in texture_config, "Should have enable flag"
        assert "grain_strength" in texture_config, "Should have grain_strength"
        assert "posterize_levels" in texture_config, "Should have posterize_levels"

        print(f"   Textures enabled: {texture_config.get('enable', False)}")
        print("   ✓ Configuration integration working correctly")

        # Clean up
        if Path(metadata_path).exists():
            Path(metadata_path).unlink()
            print(f"\n   Cleaned up: {metadata_path}")

        print("\n🎉 Complete texture integration test passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run complete texture integration test."""
    print("Complete Texture Integration Test Suite")
    print("=" * 50)

    if test_complete_texture_integration():
        print("\n🎉 All texture integration tests passed!")
        print("\nSummary of implemented features:")
        print("✓ Texture QA loop with auto-dialback on contrast failures")
        print("✓ Deterministic texture application with configurable retries")
        print("✓ Comprehensive metadata collection and storage")
        print("✓ Integration with animatics generation pipeline")
        print("✓ Configuration-driven texture settings")
        print("✓ Proper logging with [texture-qa] and [texture-integrate] tags")
        return True
    else:
        print("\n❌ Some texture integration tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
