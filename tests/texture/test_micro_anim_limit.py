#!/usr/bin/env python3
"""
Test Micro-Animations 10% Limit Enforcement

This script tests that micro-animations properly enforce the ≤10% limit per scene.
"""

import sys

from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))


def test_micro_anim_limit():
    """Test that micro-animations enforce the 10% limit per scene."""
    print("Testing Micro-Animations 10% Limit Enforcement")
    print("=" * 50)

    try:
        # Import the micro-animations module
        from cutout.micro_animations import create_micro_animation_generator

        # Test configuration with 10% limit
        config = {
            "enable": True,
            "max_elements_percent": 10,  # ≤10% limit
            "max_movement_px": 4,
            "max_movement_per_1000ms": 4,
            "ease_in_out": True,
            "seed": 42,
            "collision_check": True,
        }

        print(
            f"Configuration: max_elements_percent = {config['max_elements_percent']}%"
        )

        # Import Element and Scene classes
        from cutout.sdk import Element, Scene

        # Create test scenes with different numbers of elements
        test_scenes = [
            # Scene with 10 elements - should animate max 1 (10%)
            {
                "id": "scene_10_elements",
                "duration_ms": 5000,
                "elements": [
                    Element(id=f"element_{i}", type="shape", x=100 + i * 50, y=100)
                    for i in range(10)
                ],
            },
            # Scene with 20 elements - should animate max 2 (10%)
            {
                "id": "scene_20_elements",
                "duration_ms": 5000,
                "elements": [
                    Element(id=f"element_{i}", type="shape", x=100 + i * 30, y=100)
                    for i in range(20)
                ],
            },
            # Scene with 5 elements - should animate max 1 (20% but capped at 1)
            {
                "id": "scene_5_elements",
                "duration_ms": 5000,
                "elements": [
                    Element(id=f"element_{i}", type="shape", x=100 + i * 80, y=100)
                    for i in range(5)
                ],
            },
        ]

        # Test each scene
        all_passed = True

        for scene_data in test_scenes:
            print(f"\nTesting scene: {scene_data['id']}")
            print(f"  Total elements: {len(scene_data['elements'])}")

            # Create micro-animation generator
            micro_anim_gen = create_micro_animation_generator(config, seed=42)

            # Create a proper Scene object
            scene = Scene(
                id=scene_data["id"],
                duration_ms=scene_data["duration_ms"],
                elements=scene_data["elements"],
            )

            # Generate animations
            result = micro_anim_gen.generate_scene_animations(scene)

            # Check results
            elements_animated = result["elements_animated"]
            total_elements = result["total_elements"]
            animation_percent = (
                (elements_animated / total_elements * 100) if total_elements > 0 else 0
            )

            print(f"  Elements animated: {elements_animated}")
            print(f"  Animation percentage: {animation_percent:.1f}%")

            # Verify the 10% limit
            max_allowed = max(
                1, int(total_elements * config["max_elements_percent"] / 100)
            )
            expected_max = min(max_allowed, total_elements)

            if elements_animated <= expected_max:
                print(
                    f"  ✓ PASS: {elements_animated} ≤ {expected_max} (limit: {config['max_elements_percent']}%)"
                )
            else:
                print(
                    f"  ✗ FAIL: {elements_animated} > {expected_max} (limit: {config['max_elements_percent']}%)"
                )
                all_passed = False

            # Check that animation percentage doesn't exceed 10% (but allow for minimum 1 element)
            # For small scenes, 1 element might be >10% but that's correct behavior
            if (
                animation_percent <= config["max_elements_percent"]
                or elements_animated == 1
            ):
                print(
                    f"  ✓ PASS: {animation_percent:.1f}% (1 element minimum enforced)"
                )
            else:
                print(
                    f"  ✗ FAIL: {animation_percent:.1f}% > {config['max_elements_percent']}%"
                )
                all_passed = False

        # Test summary
        if all_passed:
            print("\n🎯 All micro-animation limit tests PASSED")
            return True
        else:
            print("\n💥 Some micro-animation limit tests FAILED")
            return False

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_micro_anim_limit()
    if success:
        print("\n🎯 Micro-animations limit enforcement test PASSED")
    else:
        print("\n💥 Micro-animations limit enforcement test FAILED")
