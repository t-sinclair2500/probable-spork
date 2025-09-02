#!/usr/bin/env python3
"""
Test Texture Metadata Integration

This script tests the full texture metadata integration including metadata writing.
"""

import json
import sys

from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))


def test_texture_metadata_integration():
    """Test texture metadata integration including metadata writing."""
    print("Testing Texture Metadata Integration")
    print("=" * 40)

    try:
        # Import the metadata creation function
        from animatics_generate import create_texture_metadata, write_animatics_metadata

        print("✓ Metadata functions imported successfully")

        # Create mock texture results
        mock_texture_results = {
            "element_1": {
                "textures": {
                    "applied": True,
                    "attempts": 2,
                    "final_params": {
                        "grain_strength": 0.3,
                        "posterize_levels": 5,
                        "feather_px": 2.0,
                        "halftone": {"enable": False},
                    },
                    "qa_results": [
                        {
                            "attempt": 1,
                            "config": {"grain_strength": 0.5, "posterize_levels": 4},
                            "contrast_result": {
                                "ok": False,
                                "fails": ["Contrast too low"],
                            },
                        },
                        {
                            "attempt": 2,
                            "config": {"grain_strength": 0.3, "posterize_levels": 5},
                            "contrast_result": {"ok": True, "fails": []},
                        },
                    ],
                    "dialback_applied": True,
                }
            },
            "element_2": {
                "textures": {
                    "applied": True,
                    "attempts": 1,
                    "final_params": {
                        "grain_strength": 0.2,
                        "posterize_levels": 6,
                        "feather_px": 1.5,
                        "halftone": {"enable": False},
                    },
                    "qa_results": [
                        {
                            "attempt": 1,
                            "config": {"grain_strength": 0.2, "posterize_levels": 6},
                            "contrast_result": {"ok": True, "fails": []},
                        }
                    ],
                    "dialback_applied": False,
                }
            },
        }

        # Test texture configuration
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

        print(f"Mock texture results: {len(mock_texture_results)} elements")
        print(f"Texture config: {texture_config}")

        # Test metadata creation
        metadata = create_texture_metadata(texture_config, mock_texture_results)

        print(f"Created metadata: {json.dumps(metadata, indent=2)}")

        # Verify metadata structure
        assert "textures" in metadata, "Metadata should have textures section"
        assert metadata["textures"]["enabled"] == True, "Textures should be enabled"
        assert "summary" in metadata["textures"], "Should have summary section"
        assert "qa_summary" in metadata["textures"], "Should have QA summary section"

        # Verify summary statistics
        summary = metadata["textures"]["summary"]
        assert summary["total_elements"] == 2, "Should have 2 elements"
        assert summary["successful_applications"] == 2, "Both should be successful"
        assert summary["dialback_applied"] == 1, "One should have dialback applied"
        assert summary["success_rate"] == 1.0, "Success rate should be 100%"

        # Verify QA summary
        qa_summary = metadata["textures"]["qa_summary"]
        assert qa_summary["total_attempts"] == 3, "Should have 3 total attempts"
        assert (
            qa_summary["average_attempts_per_element"] == 2.0
        ), "Average should be 2.0 (3 attempts / 2 elements)"
        assert qa_summary["max_attempts"] == 2, "Max attempts should be 2"

        print("✓ Metadata creation successful")

        # Test metadata writing
        test_slug = "test_texture_metadata"
        metadata_path = write_animatics_metadata(
            test_slug, mock_texture_results, texture_config
        )

        print(f"Wrote metadata to: {metadata_path}")

        # Verify file was created
        assert Path(metadata_path).exists(), "Metadata file should exist"

        # Read and verify the written metadata
        with open(metadata_path, "r") as f:
            written_metadata = json.load(f)

        print(f"Written metadata: {json.dumps(written_metadata, indent=2)}")

        # Verify written metadata structure
        assert written_metadata["slug"] == test_slug, "Slug should match"
        assert "timestamp" in written_metadata, "Should have timestamp"
        assert "textures" in written_metadata, "Should have textures section"

        # Clean up test file
        if Path(metadata_path).exists():
            Path(metadata_path).unlink()
            print(f"Cleaned up: {metadata_path}")

        print("✓ Metadata writing successful")
        print("✓ Texture metadata integration test passed!")
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
    """Run texture metadata integration test."""
    print("Texture Metadata Integration Test Suite")
    print("=" * 50)

    if test_texture_metadata_integration():
        print("\n🎉 Texture metadata integration test passed!")
        return True
    else:
        print("\n❌ Texture metadata integration test failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
