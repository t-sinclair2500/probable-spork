#!/usr/bin/env python3
"""
Texture Probe Grid Generator with Style Presets Support

Generates a grid of texture parameter combinations for visual comparison.
Supports style presets from conf/style_presets.yaml and CLI preset selection.

Usage:
    python bin/texture_probe.py --slug <slug> [--preset <preset_name>]
    python bin/texture_probe.py --slug <slug> --preset print-soft
    python bin/texture_probe.py --slug <slug> --preset halftone_classic
"""

import argparse
import sys
from typing import Dict, Optional

from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml
    from PIL import Image, ImageDraw, ImageFont

    from bin.core import get_logger, load_config
    from bin.cutout.texture_engine import apply_textures_to_frame

    log = get_logger("texture_probe")

    def normalize_preset_name(preset_name: str) -> str:
        """Normalize preset name to handle both hyphen and underscore formats."""
        return preset_name.replace("-", "_")

    def load_style_presets() -> Dict:
        """Load style presets from configuration file."""
        presets_path = Path("conf/style_presets.yaml")

        if not presets_path.exists():
            log.warning("Style presets file not found: conf/style_presets.yaml")
            return {}

        try:
            with open(presets_path, "r", encoding="utf-8") as f:
                presets = yaml.safe_load(f)
                return presets
        except Exception as e:
            log.error(f"Failed to load style presets: {e}")
            return {}

    def resolve_preset_config(preset_name: str, base_config: Dict) -> Dict:
        """Resolve preset configuration, merging with base config."""
        normalized_name = normalize_preset_name(preset_name)
        presets = load_style_presets()

        if normalized_name not in presets:
            log.warning(f"Preset '{preset_name}' not found, using base configuration")
            return base_config

        preset = presets[normalized_name]
        log.info(
            f"Using preset '{normalized_name}': {preset.get('description', 'No description')}"
        )

        # Merge preset with base config
        merged_config = base_config.copy()
        if "textures" in preset:
            # Deep merge textures section
            if "textures" not in merged_config:
                merged_config["textures"] = {}

            for key, value in preset["textures"].items():
                if key == "halftone" and isinstance(value, dict):
                    if "halftone" not in merged_config["textures"]:
                        merged_config["textures"]["halftone"] = {}
                    merged_config["textures"]["halftone"].update(value)
                else:
                    merged_config["textures"][key] = value

        return merged_config

    def create_test_image(size=(200, 200)):
        """Create a test image with various elements for texture testing."""
        img = Image.new("RGB", size, color="white")
        draw = ImageDraw.Draw(img)

        # Draw some test elements
        # Rectangle
        draw.rectangle([20, 20, 80, 80], fill="red", outline="black")

        # Circle
        draw.ellipse([120, 20, 180, 80], fill="blue", outline="black")

        # Text
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
        except:
            font = ImageFont.load_default()

        draw.text((20, 120), "Texture Test", fill="black", font=font)
        draw.text((20, 140), "ABCDEFGHIJK", fill="green", font=font)

        # Gradient
        for y in range(160, 200):
            alpha = int(255 * (y - 160) / 40)
            draw.line([(20, y), (180, y)], fill=(alpha, alpha, alpha))

        return img

    def generate_probe_grid(
        slug: str, preset_name: Optional[str] = None, output_path: Optional[str] = None
    ) -> str:
        """Generate texture probe grid with various parameter combinations."""

        # Load base configuration
        try:
            base_config = load_config()
            base_texture_config = {
                "enable": True,
                "grain_strength": 0.12,
                "feather_px": 1.5,
                "posterize_levels": 6,
                "halftone": {
                    "enable": False,
                    "cell_px": 6,
                    "angle_deg": 15,
                    "opacity": 0.12,
                },
            }
        except Exception as e:
            log.warning(f"Failed to load base config, using defaults: {e}")
            base_texture_config = {
                "enable": True,
                "grain_strength": 0.12,
                "feather_px": 1.5,
                "posterize_levels": 6,
                "halftone": {
                    "enable": False,
                    "cell_px": 6,
                    "angle_deg": 15,
                    "opacity": 0.12,
                },
            }

        # Resolve preset if specified
        if preset_name:
            texture_config = resolve_preset_config(preset_name, base_texture_config)
            log.info(f"Resolved preset '{preset_name}' configuration")
        else:
            texture_config = base_texture_config
            log.info("Using base texture configuration")

        # Set output path
        if not output_path:
            output_path = f"runs/{slug}/texture_probe_grid.png"

        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Test image
        test_img = create_test_image()

        # Parameter combinations to test
        grain_strengths = [0.0, 0.05, 0.12, 0.18, 0.25]
        posterize_levels = [1, 2, 4, 6, 8, 12]
        halftone_enabled = [False, True]

        # Grid layout
        cols = len(grain_strengths)
        rows = len(posterize_levels) * len(halftone_enabled)

        # Calculate grid size
        img_width, img_height = test_img.size
        grid_width = cols * img_width
        grid_height = rows * img_height

        # Create grid image
        grid_img = Image.new("RGB", (grid_width, grid_height), color="white")

        # Generate all combinations
        row_idx = 0
        for posterize in posterize_levels:
            for halftone in halftone_enabled:
                for col_idx, grain in enumerate(grain_strengths):
                    # Create texture config for this combination
                    test_config = texture_config.copy()
                    test_config["grain_strength"] = grain
                    test_config["posterize_levels"] = posterize
                    test_config["halftone"]["enable"] = halftone

                    # Apply textures
                    seed = 42  # Fixed seed for consistency
                    try:
                        textured = apply_textures_to_frame(test_img, test_config, seed)
                    except Exception as e:
                        log.warning(
                            f"Failed to apply textures for G:{grain} P:{posterize} H:{halftone}: {e}"
                        )
                        textured = test_img  # Fallback to original

                    # Calculate position in grid
                    x = col_idx * img_width
                    y = row_idx * img_height

                    # Paste into grid
                    grid_img.paste(textured, (x, y))

                    # Add label
                    draw = ImageDraw.Draw(grid_img)
                    try:
                        font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 12)
                    except:
                        font = ImageFont.load_default()

                    label = f"G:{grain:.2f} P:{posterize} H:{halftone}"
                    # Add black outline for visibility
                    draw.text((x + 4, y + 4), label, fill="black", font=font)
                    draw.text((x + 5, y + 5), label, fill="white", font=font)

                row_idx += 1

        # Save grid
        grid_img.save(output_path)
        log.info(f"Texture probe grid saved to: {output_path}")

        # Print parameter summary
        print("\nTexture Probe Grid Parameters:")
        print(f"Grid size: {cols}x{rows}")
        print(f"Grain strengths: {grain_strengths}")
        print(f"Posterize levels: {posterize_levels}")
        print(f"Halftone enabled: {halftone_enabled}")

        if preset_name:
            print(f"Preset: {preset_name}")
            presets = load_style_presets()
            if preset_name in presets:
                print(
                    f"Description: {presets[preset_name].get('description', 'No description')}"
                )

        return output_path

    def main():
        """Main function with CLI argument parsing."""
        parser = argparse.ArgumentParser(
            description="Generate texture probe grid for visual comparison",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python bin/texture_probe.py --slug design-history
  python bin/texture_probe.py --slug design-history --preset print_soft
  python bin/texture_probe.py --slug design-history --preset halftone_classic
  python bin/texture_probe.py --slug design-history --preset vintage_paper
            """,
        )

        parser.add_argument(
            "--slug",
            required=True,
            help="Topic slug for output directory (e.g., 'design-history')",
        )

        parser.add_argument(
            "--preset", help="Style preset name from conf/style_presets.yaml"
        )

        parser.add_argument(
            "--output",
            help="Custom output path (default: runs/<slug>/texture_probe_grid.png)",
        )

        args = parser.parse_args()

        print("Texture Probe Grid Generator (P3-6 Style Presets)")
        print("=" * 55)

        if args.preset:
            print(f"Using style preset: {args.preset}")
        else:
            print("Using base texture configuration")

        output_path = generate_probe_grid(
            slug=args.slug, preset_name=args.preset, output_path=args.output
        )

        print("\n✓ Texture probe grid generated successfully!")
        print(f"Output: {output_path}")

        # Log the resolved configuration
        if args.preset:
            presets = load_style_presets()
            normalized_name = normalize_preset_name(args.preset)
            if normalized_name in presets:
                preset_config = presets[normalized_name]
                print("\nResolved preset configuration:")
                print(
                    f"  Grain strength: {preset_config['textures']['grain_strength']}"
                )
                print(f"  Feather pixels: {preset_config['textures']['feather_px']}")
                print(
                    f"  Posterize levels: {preset_config['textures']['posterize_levels']}"
                )
                print(
                    f"  Halftone enabled: {preset_config['textures']['halftone']['enable']}"
                )

        # Also save to a default location for easy access
        default_path = "texture_probe_grid.png"
        Path(output_path).parent.parent.mkdir(exist_ok=True)
        import shutil

        shutil.copy2(output_path, default_path)
        print(f"Also saved to: {default_path}")

    if __name__ == "__main__":
        main()

except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you have the required dependencies installed:")
    print("pip install Pillow numpy pyyaml")
    sys.exit(1)
except Exception as e:
    print(f"Generation failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
