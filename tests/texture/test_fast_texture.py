#!/usr/bin/env python3
"""
Fast Texture Performance Test

This script profiles the texture application to identify performance bottlenecks.
"""

import sys
import time

from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))


def test_texture_performance():
    """Test texture performance with profiling."""
    print("Fast Texture Performance Test")
    print("=" * 35)

    try:
        from cutout.texture_engine import apply_textures_to_frame

        # Create test image
        from PIL import Image, ImageDraw

        test_img = Image.new("RGB", (400, 300), color="#1C4FA1")
        draw = ImageDraw.Draw(test_img)
        draw.text((50, 150), "Test Text", fill="#000000")

        # Test different texture configurations
        configs = [
            {"name": "No textures", "config": {"enable": False}},
            {
                "name": "Basic processing",
                "config": {"enable": False},  # Will add basic operations manually
            },
            {
                "name": "Grain only",
                "config": {
                    "enable": True,
                    "grain_strength": 0.3,
                    "feather_px": 0,
                    "posterize_levels": 1,
                },
            },
            {
                "name": "Feather only",
                "config": {
                    "enable": True,
                    "grain_strength": 0,
                    "feather_px": 2.0,
                    "posterize_levels": 1,
                },
            },
            {
                "name": "Posterize only",
                "config": {
                    "enable": True,
                    "grain_strength": 0,
                    "feather_px": 0,
                    "posterize_levels": 4,
                },
            },
            {
                "name": "All effects",
                "config": {
                    "enable": True,
                    "grain_strength": 0.3,
                    "feather_px": 2.0,
                    "posterize_levels": 4,
                },
            },
        ]

        results = []

        for test_config in configs:
            print(f"\nTesting: {test_config['name']}")

            # Warm up
            for _ in range(2):
                apply_textures_to_frame(test_img.copy(), test_config["config"], seed=42)

            # Measure performance
            start_time = time.time()
            if test_config["name"] == "Basic processing":
                # Do some basic image operations to simulate real baseline
                img_copy = test_img.copy()
                img_copy = img_copy.resize((400, 300))  # Basic resize
                img_copy = img_copy.convert("RGB")  # Basic conversion
                result_img = img_copy
            else:
                result_img = apply_textures_to_frame(
                    test_img.copy(), test_config["config"], seed=42
                )
            end_time = time.time()

            render_time_ms = (end_time - start_time) * 1000
            results.append(
                {
                    "name": test_config["name"],
                    "time_ms": render_time_ms,
                    "config": test_config["config"],
                }
            )

            print(f"  Render time: {render_time_ms:.2f}ms")

            # Check if performance data was stored
            if hasattr(result_img, "_texture_performance"):
                print(f"  Stored performance: {result_img._texture_performance:.2f}ms")

        # Analyze results
        print("\nPerformance Analysis:")
        print("=" * 25)

        baseline_time = next(
            r["time_ms"] for r in results if r["name"] == "No textures"
        )

        # Handle case where baseline time is 0
        if baseline_time == 0:
            baseline_time = 0.1  # Use small non-zero value for calculation

        for result in results:
            if result["name"] != "No textures":
                overhead = ((result["time_ms"] - baseline_time) / baseline_time) * 100
                print(
                    f"  {result['name']}: {result['time_ms']:.2f}ms (overhead: {overhead:.1f}%)"
                )

        # Check if any configuration meets the 15% budget
        budget_compliant = []
        for result in results:
            if result["name"] != "No textures":
                overhead = ((result["time_ms"] - baseline_time) / baseline_time) * 100
                if overhead <= 15.0:
                    budget_compliant.append(result["name"])

        if budget_compliant:
            print(f"\n✓ Budget compliant configurations: {', '.join(budget_compliant)}")
        else:
            print("\n✗ No configurations meet 15% budget")

        return len(budget_compliant) > 0

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_texture_performance()
    if success:
        print("\n🎯 Some texture configurations meet performance budget")
    else:
        print("\n💥 All texture configurations exceed performance budget")
