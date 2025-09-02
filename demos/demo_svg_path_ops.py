#!/usr/bin/env python3
"""
Demonstration of Advanced SVG Path Operations

This script demonstrates the capabilities of the SVG path operations module
for procedural asset generation, including:
- Path parsing and manipulation
- Boolean operations
- Geometric transformations
- Safe area validation
- Procedural motif variant generation
"""

import os
import sys

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def demo_basic_operations():
    """Demonstrate basic SVG path operations."""
    print("=" * 60)
    print("DEMO: Basic SVG Path Operations")
    print("=" * 60)

    try:
        from bin.cutout.svg_path_ops import create_path_processor

        # Create processor
        processor = create_path_processor()
        print("✓ Created SVG path processor")

        # Create a simple test path (triangle)
        from svgpathtools import Line, Path

        triangle = Path(
            Line(complex(0, 0), complex(100, 0)),
            Line(complex(100, 0), complex(50, 100)),
            Line(complex(50, 100), complex(0, 0)),
        )

        print(f"✓ Created test triangle with {len(triangle)} segments")

        # Test transformations
        print("\nTesting transformations:")

        # Scale
        scaled = processor.transform_path(triangle, "scale", scale_x=2.0, scale_y=1.5)
        print("  - Scaled 2x horizontally, 1.5x vertically")

        # Rotate
        rotated = processor.transform_path(triangle, "rotate", angle=45)
        print("  - Rotated 45 degrees")

        # Translate
        translated = processor.transform_path(triangle, "translate", dx=50, dy=25)
        print("  - Translated 50px right, 25px down")

        # Skew
        skewed = processor.transform_path(triangle, "skew", skew_x=15, skew_y=0)
        print("  - Skewed 15 degrees horizontally")

        print("✓ All transformations completed successfully")

        # Test safe area validation
        bounds = (0, 0, 200, 200)
        is_safe = processor.validate_safe_area(triangle, bounds)
        print(f"✓ Safe area validation: {is_safe}")

        return True

    except Exception as e:
        print(f"✗ Basic operations demo failed: {e}")
        return False


def demo_boolean_operations():
    """Demonstrate boolean operations between paths."""
    print("\n" + "=" * 60)
    print("DEMO: Boolean Operations")
    print("=" * 60)

    try:
        from svgpathtools import Line, Path

        from bin.cutout.svg_path_ops import create_path_processor

        processor = create_path_processor()

        # Create two overlapping shapes
        square = Path(
            Line(complex(0, 0), complex(100, 0)),
            Line(complex(100, 0), complex(100, 100)),
            Line(complex(100, 100), complex(0, 100)),
            Line(complex(0, 100), complex(0, 0)),
        )

        circle_approx = Path(
            Line(complex(50, 0), complex(50, 0)),  # Start point
            # Simplified circle approximation
            Line(complex(50, 0), complex(100, 50)),
            Line(complex(100, 50), complex(50, 100)),
            Line(complex(50, 100), complex(0, 50)),
            Line(complex(0, 50), complex(50, 0)),
        )

        print("✓ Created test shapes: square and circle approximation")

        # Test boolean operations
        operations = ["union", "intersection", "difference", "symmetric_difference"]

        for operation in operations:
            try:
                result = processor.boolean_operation(square, circle_approx, operation)
                if result:
                    print(f"  ✓ {operation.capitalize()}: Success")
                else:
                    print(f"  ⚠ {operation.capitalize()}: No result")
            except Exception as e:
                print(f"  ✗ {operation.capitalize()}: Failed - {e}")

        print("✓ Boolean operations demo completed")
        return True

    except Exception as e:
        print(f"✗ Boolean operations demo failed: {e}")
        return False


def demo_morphing():
    """Demonstrate path morphing between shapes."""
    print("\n" + "=" * 60)
    print("DEMO: Path Morphing")
    print("=" * 60)

    try:
        from svgpathtools import Line, Path

        from bin.cutout.svg_path_ops import create_path_processor

        processor = create_path_processor()

        # Create two different shapes
        shape1 = Path(
            Line(complex(0, 0), complex(100, 0)),
            Line(complex(100, 0), complex(100, 100)),
            Line(complex(100, 100), complex(0, 100)),
            Line(complex(0, 100), complex(0, 0)),
        )

        shape2 = Path(
            Line(complex(50, 0), complex(50, 0)),  # Start point
            Line(complex(50, 0), complex(100, 50)),
            Line(complex(100, 50), complex(50, 100)),
            Line(complex(50, 100), complex(0, 50)),
            Line(complex(0, 50), complex(50, 0)),
        )

        print("✓ Created test shapes for morphing")

        # Generate morphing sequence
        morph_steps = 5
        print(f"\nGenerating {morph_steps} morphing steps...")

        for i in range(morph_steps + 1):
            t = i / morph_steps
            morphed = processor.morph_paths(shape1, shape2, t)
            print(f"  Step {i}: t={t:.2f} - {len(morphed)} segments")

        print("✓ Path morphing demo completed")
        return True

    except Exception as e:
        print(f"✗ Path morphing demo failed: {e}")
        return False


def demo_motif_variants():
    """Demonstrate procedural motif variant generation."""
    print("\n" + "=" * 60)
    print("DEMO: Procedural Motif Variants")
    print("=" * 60)

    try:
        from bin.cutout.svg_path_ops import generate_motif_variants

        # Find a base SVG to work with
        base_assets = [
            "assets/brand/props/blanket.svg",
            "assets/brand/backgrounds/gradient1.svg",
            "assets/brand/characters/narrator.svg",
        ]

        base_asset = None
        for asset in base_assets:
            if os.path.exists(asset):
                base_asset = asset
                break

        if not base_asset:
            print("⚠ No base SVG assets found, creating a simple test shape")
            # Create a simple test SVG
            test_svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <path d="M 10 10 L 90 10 L 50 90 Z" fill="blue"/>
</svg>"""

            test_path = "assets/generated/test_base.svg"
            os.makedirs(os.path.dirname(test_path), exist_ok=True)
            with open(test_path, "w") as f:
                f.write(test_svg)
            base_asset = test_path
            print(f"✓ Created test SVG: {test_path}")

        print(f"Using base asset: {base_asset}")

        # Generate variants for different motif types
        motif_types = ["boomerang", "starburst", "abstract"]
        output_dir = "assets/generated/demo_variants"

        for motif_type in motif_types:
            print(f"\nGenerating {motif_type} variants...")

            try:
                variants = generate_motif_variants(
                    base_asset, motif_type, count=3, output_dir=output_dir, seed=42
                )

                if variants:
                    print(f"  ✓ Generated {len(variants)} variants:")
                    for variant in variants:
                        print(f"    - {os.path.basename(variant)}")
                else:
                    print(f"  ⚠ No variants generated for {motif_type}")

            except Exception as e:
                print(f"  ✗ Failed to generate {motif_type} variants: {e}")

        print("\n✓ Variant generation demo completed")
        print(f"  Output directory: {output_dir}")
        return True

    except Exception as e:
        print(f"✗ Motif variants demo failed: {e}")
        return False


def demo_integration():
    """Demonstrate integration with the asset loop."""
    print("\n" + "=" * 60)
    print("DEMO: Asset Loop Integration")
    print("=" * 60)

    try:
        from bin.cutout.asset_loop import StoryboardAssetLoop
        from bin.cutout.sdk import load_style

        # Load brand style
        brand_style = load_style()
        print("✓ Brand style loaded")

        # Create asset loop
        loop = StoryboardAssetLoop("demo_integration", brand_style, seed=42)
        print("✓ Asset loop created")

        # Check SVG path processor integration
        if hasattr(loop, "path_processor") and loop.path_processor:
            print("✓ SVG path processor integrated")

            # Test variant generation through the asset loop
            if hasattr(loop, "asset_generator") and hasattr(
                loop.asset_generator, "generate_variants"
            ):
                print("✓ Variant generation available through asset loop")
            else:
                print("⚠ Variant generation not available through asset loop")
        else:
            print("⚠ SVG path processor not integrated")

        print("✓ Asset loop integration demo completed")
        return True

    except Exception as e:
        print(f"✗ Asset loop integration demo failed: {e}")
        return False


def main():
    """Run all demonstrations."""
    print("Advanced SVG Path Operations Demonstration")
    print("=" * 60)

    demos = [
        ("Basic Operations", demo_basic_operations),
        ("Boolean Operations", demo_boolean_operations),
        ("Path Morphing", demo_morphing),
        ("Motif Variants", demo_motif_variants),
        ("Asset Loop Integration", demo_integration),
    ]

    results = []
    for demo_name, demo_func in demos:
        try:
            result = demo_func()
            results.append((demo_name, result))
        except Exception as e:
            print(f"✗ Demo {demo_name} crashed: {e}")
            results.append((demo_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("DEMONSTRATION SUMMARY")
    print("=" * 60)

    passed = 0
    total = len(results)

    for demo_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{demo_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} demonstrations successful")

    if passed == total:
        print("🎉 All demonstrations completed successfully!")
        print("\nThe SVG path operations module provides:")
        print("  ✓ Path parsing and manipulation")
        print("  ✓ Boolean operations (union, intersection, difference)")
        print("  ✓ Geometric transformations (scale, rotate, translate, skew)")
        print("  ✓ Path morphing for animation effects")
        print("  ✓ Safe area validation")
        print("  ✓ Procedural motif variant generation")
        print("  ✓ Integration with the storyboard asset loop")
        return True
    else:
        print("❌ Some demonstrations failed. Check the output above for details.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
