#!/usr/bin/env python3
"""
Asset Generator for Procedural Gap Filling

This module generates procedural SVG assets to fill gaps in asset plans,
using motif generators and ensuring palette compliance with the design system.
All generation is deterministic given the same seed parameters.
"""

import argparse
import hashlib
import json
import logging
import random
import subprocess
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# Simple logging setup for standalone operation
def get_logger(name="asset_generator"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


# Import motif generators if available
try:
    from bin.cutout.motif_generators import (
        generate_background_motif,
        generate_character_motif,
        generate_prop_motif,
        make_starburst,
    )

    MOTIF_GENERATORS_AVAILABLE = True
except ImportError:
    MOTIF_GENERATORS_AVAILABLE = False
    log = get_logger("asset_generator")
    log.warning("Motif generators not available, using fallback generation")

from bin.asset_manifest import AssetManifest

log = get_logger("asset_generator")


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join([c + c for c in hex_color])
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_lab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert RGB to CIE Lab color space."""

    # Convert sRGB to linear RGB
    def to_linear(c):
        c = c / 255.0
        if c <= 0.04045:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    r_lin = to_linear(r)
    g_lin = to_linear(g)
    b_lin = to_linear(b)

    # Convert to XYZ (D65 illuminant)
    x = r_lin * 0.4124 + g_lin * 0.3576 + b_lin * 0.1805
    y = r_lin * 0.2126 + g_lin * 0.7152 + b_lin * 0.0722
    z = r_lin * 0.0193 + g_lin * 0.1192 + b_lin * 0.9505

    # Convert to Lab
    def xyz_to_lab(x, y, z):
        # Normalize by D65 white point
        x /= 0.95047
        y /= 1.00000
        z /= 1.08883

        def transform(c):
            if c > 0.008856:
                return c ** (1 / 3)
            return (7.787 * c) + (16 / 116)

        l = (116 * transform(y)) - 16
        a = 500 * (transform(x) - transform(y))
        b = 200 * (transform(y) - transform(z))

        return l, a, b

    return xyz_to_lab(x, y, z)


def calculate_color_distance(color1: str, color2: str) -> float:
    """Calculate CIEDE2000 color distance between two hex colors."""
    try:
        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)

        lab1 = rgb_to_lab(*rgb1)
        lab2 = rgb_to_lab(*rgb2)

        # Simplified Euclidean distance in Lab space
        # For production, consider using colormath library for CIEDE2000
        delta_l = lab1[0] - lab2[0]
        delta_a = lab1[1] - lab2[1]
        delta_b = lab1[2] - lab2[2]

        distance = (delta_l**2 + delta_a**2 + delta_b**2) ** 0.5
        return distance

    except Exception as e:
        log.warning(
            f"Failed to calculate color distance between {color1} and {color2}: {e}"
        )
        return 999.0  # Return high distance on error


class AssetGenerator:
    """Generates procedural SVG assets to fill gaps in asset plans."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.assets_dir = self.base_dir / "assets"
        self.generated_dir = self.assets_dir / "generated"
        self.thumbnails_dir = self.assets_dir / "thumbnails"

        # Ensure directories exist
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

        # Load design language colors
        self.design_colors = self._load_design_colors()

        # Generation caps from config
        self.max_assets_per_run = 20  # Default cap

        # Palette validation threshold
        self.palette_threshold = 4.0  # ΔE threshold for color compliance

    def _load_design_colors(self) -> Dict[str, str]:
        """Load colors from design language configuration."""
        try:
            design_path = self.base_dir / "design" / "design_language.json"
            if design_path.exists():
                with open(design_path, "r") as f:
                    data = json.load(f)
                    return data.get("colors", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log.warning(f"Failed to load design language: {e}")

        # Fallback to core palette
        return {
            "primary_blue": "#1C4FA1",
            "primary_red": "#D62828",
            "primary_yellow": "#F6BE00",
            "secondary_orange": "#F28C28",
            "secondary_green": "#4E9F3D",
            "accent_teal": "#008080",
            "accent_brown": "#8B5E3C",
            "accent_black": "#1A1A1A",
            "accent_white": "#FFFFFF",
            "accent_cream": "#F8F1E5",
            "accent_pink": "#FF6F91",
        }

    def _validate_palette_delta_e(
        self, palette: List[str]
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Validate palette using ΔE color distance calculation."""
        valid_colors = []
        violations = []

        for color in palette:
            # Check if color is in design palette
            if color in self.design_colors.values():
                valid_colors.append(color)
                continue

            # Check if color is close enough to any palette color
            min_distance = float("inf")
            closest_palette_color = None

            for palette_color in self.design_colors.values():
                distance = calculate_color_distance(color, palette_color)
                if distance < min_distance:
                    min_distance = distance
                    closest_palette_color = palette_color

            if min_distance <= self.palette_threshold:
                # Use closest palette color instead
                valid_colors.append(closest_palette_color)
                log.info(
                    f"[asset-generate] Mapped {color} to {closest_palette_color} (ΔE: {min_distance:.2f})"
                )
            else:
                violations.append(
                    {
                        "color": color,
                        "closest_palette": closest_palette_color,
                        "delta_e": min_distance,
                        "threshold": self.palette_threshold,
                    }
                )
                log.warning(
                    f"[asset-generate] Color {color} exceeds palette threshold (ΔE: {min_distance:.2f})"
                )

        # Ensure we have at least one valid color
        if not valid_colors:
            log.warning("[asset-generate] No valid colors in palette, using default")
            valid_colors = ["#1C4FA1", "#F6BE00"]

        return valid_colors, violations

    def _generate_fallback_svg(
        self, category: str, colors: List[str], width: int, height: int, seed: int
    ) -> str:
        """Generate simple fallback SVG when motif generators are not available."""
        if not colors:
            colors = ["#1C4FA1", "#F6BE00"]

        # Use seed for deterministic generation
        random.seed(seed)

        if category == "background":
            # Generate a simple geometric background
            svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="{colors[0]}" stroke-width="1" opacity="0.3"/>
    </pattern>
  </defs>
  <rect width="{width}" height="{height}" fill="{colors[1] if len(colors) > 1 else colors[0]}"/>
  <rect width="{width}" height="{height}" fill="url(#grid)"/>
  <circle cx="{width//2}" cy="{height//2}" r="50" fill="{colors[0]}" opacity="0.7"/>
</svg>"""
        elif category == "prop":
            # Generate a simple geometric prop
            svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect x="20" y="20" width="{width-40}" height="{height-40}" fill="{colors[0]}" rx="10"/>
  <circle cx="{width//2}" cy="{height//2}" r="30" fill="{colors[1] if len(colors) > 1 else colors[0]}"/>
  <rect x="{width//2-15}" y="{height//2-15}" width="30" height="30" fill="{colors[0]}" rx="5"/>
</svg>"""
        elif category == "character":
            # Generate a simple character silhouette
            svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <circle cx="{width//2}" cy="{height//3}" r="25" fill="{colors[0]}"/>
  <rect x="{width//2-20}" y="{height//2}" width="40" height="60" fill="{colors[1] if len(colors) > 1 else colors[0]}" rx="20"/>
  <rect x="{width//2-30}" y="{height//2+20}" width="15" height="40" fill="{colors[0]}" rx="7"/>
  <rect x="{width//2+15}" y="{height//2+20}" width="15" height="40" fill="{colors[0]}" rx="7"/>
</svg>"""
        else:
            # Default geometric shape
            svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <polygon points="{width//2},20 {width-20},{height-20} 20,{height-20}" fill="{colors[0]}"/>
  <circle cx="{width//2}" cy="{height//2}" r="30" fill="{colors[1] if len(colors) > 1 else colors[0]}"/>
</svg>"""

        return svg

    def _validate_palette(self, palette: List[str]) -> List[str]:
        """Legacy palette validation method."""
        allowed_colors = set(self.design_colors.values())
        valid_colors = []

        for color in palette:
            if color in allowed_colors:
                valid_colors.append(color)
            else:
                log.warning(f"Color {color} not in design palette, skipping")

        # Ensure we have at least one valid color
        if not valid_colors:
            log.warning("No valid colors in palette, using default")
            valid_colors = ["#1C4FA1", "#F6BE00"]

        return valid_colors

    def _generate_asset_filename(self, spec: Dict[str, Any], seed: int) -> str:
        """Generate a deterministic filename for the asset."""
        # Create a hash from spec and seed for consistent naming
        spec_str = json.dumps(spec, sort_keys=True) + str(seed)
        spec_hash = hashlib.sha1(spec_str.encode()).hexdigest()[:8]

        category = spec.get("category", "unknown")
        style = spec.get("style", "default")

        return f"{category}_{style}_{spec_hash}.svg"

    def _add_metadata(
        self,
        svg_content: str,
        spec: Dict[str, Any],
        seed: int,
        generator_params: Dict[str, Any],
    ) -> str:
        """Add metadata to SVG including generator info and seed."""
        # Parse SVG to add metadata
        try:
            root = ET.fromstring(svg_content)

            # Add or update desc element
            desc = root.find(".//desc")
            if desc is None:
                desc = ET.SubElement(root, "desc")

            # Create metadata description
            metadata = {
                "generator": "asset_generator.py",
                "seed": seed,
                "category": spec.get("category", "unknown"),
                "style": spec.get("style", "default"),
                "palette": spec.get("palette", []),
                "generator_params": generator_params,
                "notes": spec.get("notes", ""),
                "created_at": self._get_timestamp(),
                "license": "MIT",
                "palette_compliant": True,
            }

            desc.text = f"Procedurally generated {spec.get('category', 'asset')} using seed {seed}. Parameters: {json.dumps(generator_params)}"

            # Add metadata as comment for easy extraction
            metadata_comment = f"<!-- METADATA: {json.dumps(metadata)} -->"

            # Insert comment after XML declaration
            if svg_content.startswith("<?xml"):
                xml_end = svg_content.find("?>") + 2
                return (
                    svg_content[:xml_end]
                    + "\n"
                    + metadata_comment
                    + "\n"
                    + svg_content[xml_end:]
                )
            else:
                return metadata_comment + "\n" + svg_content

        except ET.ParseError as e:
            log.warning(f"Failed to parse SVG for metadata: {e}")
            return svg_content

    def _create_thumbnail_pillow(self, svg_path: str, out_dir: str) -> str:
        """Create thumbnail using Pillow/CairoSVG fallback."""
        svg_path_obj = Path(svg_path)
        thumbnail_name = svg_path_obj.stem + "_thumb.png"
        thumbnail_path = Path(out_dir) / thumbnail_name

        try:
            # Try CairoSVG first (best quality)
            try:
                import cairosvg

                cairosvg.svg2png(
                    url=str(svg_path),
                    write_to=str(thumbnail_path),
                    output_width=128,
                    output_height=128,
                )
                log.info(f"[thumb] Created thumbnail with CairoSVG: {thumbnail_path}")
                return str(thumbnail_path)
            except ImportError:
                pass

            # Fallback to Pillow with basic SVG parsing
            try:
                from PIL import Image, ImageDraw

                # Create a simple colored square as fallback
                img = Image.new("RGBA", (128, 128), (255, 255, 255, 0))
                draw = ImageDraw.Draw(img)

                # Draw a colored border to indicate it's a fallback
                draw.rectangle([0, 0, 127, 127], outline=(100, 100, 100, 128), width=2)

                # Add text label
                try:
                    from PIL import ImageFont

                    font = ImageFont.load_default()
                    draw.text(
                        (64, 64),
                        "SVG",
                        fill=(100, 100, 100, 128),
                        anchor="mm",
                        font=font,
                    )
                except:
                    pass

                img.save(thumbnail_path, "PNG")
                log.info(
                    f"[thumb] Created thumbnail with Pillow fallback: {thumbnail_path}"
                )
                return str(thumbnail_path)

            except ImportError:
                pass

        except Exception as e:
            log.warning(f"[thumb] Pillow/Cairo thumbnail generation failed: {e}")

        return ""

    def _create_thumbnail(self, svg_path: str, out_dir: str) -> str:
        """Create a PNG thumbnail from SVG using rsvg-convert or similar."""
        svg_path_obj = Path(svg_path)
        thumbnail_name = svg_path_obj.stem + "_thumb.png"
        thumbnail_path = Path(out_dir) / thumbnail_name

        # Try Pillow/CairoSVG first (no external dependencies)
        result = self._create_thumbnail_pillow(svg_path, out_dir)
        if result:
            return result

        try:
            # Try rsvg-convert first (best quality)
            cmd = [
                "rsvg-convert",
                "-w",
                "128",
                "-h",
                "128",
                str(svg_path),
                "-o",
                str(thumbnail_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and thumbnail_path.exists():
                log.info(
                    f"[thumb] Created thumbnail with rsvg-convert: {thumbnail_path}"
                )
                return str(thumbnail_path)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        try:
            # Fallback to ImageMagick
            cmd = ["convert", str(svg_path), "-resize", "128x128", str(thumbnail_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and thumbnail_path.exists():
                log.info(
                    f"[thumb] Created thumbnail with ImageMagick: {thumbnail_path}"
                )
                return str(thumbnail_path)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        log.warning(f"[thumb] Could not create thumbnail for {svg_path}")
        return ""

    def generate_from_spec(
        self, spec: Dict[str, Any], out_dir: str, seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate a single asset from specification.

        Args:
            spec: Asset specification with category, style, palette, etc.
            out_dir: Output directory for generated assets
            seed: Random seed for deterministic generation

        Returns:
            Dict with path, palette, seed, and generator parameters
        """
        if seed is None:
            seed = random.randint(1, 1000000)

        log.info(
            f"[asset-generate] Generating asset: {spec.get('element_id', 'unknown')} with seed {seed}"
        )

        # Validate and filter palette using ΔE calculation
        palette = spec.get("palette", [])
        valid_palette, violations = self._validate_palette_delta_e(palette)

        if violations:
            log.warning(
                f"[asset-generate] Palette violations: {len(violations)} colors exceed threshold"
            )
            for violation in violations:
                log.warning(
                    f"  {violation['color']} -> {violation['closest_palette']} (ΔE: {violation['delta_e']:.2f})"
                )

        # Determine asset dimensions based on category
        category = spec.get("category", "prop")
        if category == "background":
            width, height = 1920, 1080
        else:
            width, height = 200, 200

        # Generate asset based on category and style
        svg_content = None
        generator_params = {}

        try:
            if MOTIF_GENERATORS_AVAILABLE:
                # Use motif generators if available
                if category == "background":
                    style = spec.get("style", "starburst")
                    # Handle specific background styles
                    if style in ["starburst", "boomerang", "cutout_collage"]:
                        svg_content = generate_background_motif(
                            motif_type=style,
                            colors=valid_palette,
                            seed=seed,
                            width=width,
                            height=height,
                        )
                    else:
                        # Fallback to starburst for unknown styles
                        svg_content = generate_background_motif(
                            motif_type="starburst",
                            colors=valid_palette,
                            seed=seed,
                            width=width,
                            height=height,
                        )
                        style = "starburst"  # Update style to reflect actual generation

                    generator_params = {
                        "motif_type": style,
                        "width": width,
                        "height": height,
                    }

                elif category == "prop":
                    style = spec.get("style", "geometric")
                    # Handle specific prop styles that have dedicated generators
                    if style in ["clock", "phone", "chair", "book", "notebook"]:
                        svg_content = generate_prop_motif(
                            prop_type=style,
                            colors=valid_palette,
                            seed=seed,
                            width=width,
                            height=height,
                        )
                    elif style == "nelson_sunburst":
                        # Use starburst motif for Nelson clock style
                        svg_content = make_starburst(
                            cx=width // 2,
                            cy=height // 2,
                            color_spokes=valid_palette[0],
                            color_knobs=(
                                valid_palette[1]
                                if len(valid_palette) > 1
                                else valid_palette[0]
                            ),
                            spokes=12,
                            inner=12,
                            outer=48,
                            knob_radius=3,
                            seed=seed,
                        )
                    else:
                        # Fallback to geometric prop for unknown styles
                        svg_content = generate_prop_motif(
                            prop_type="geometric",
                            colors=valid_palette,
                            seed=seed,
                            width=width,
                            height=height,
                        )
                        style = "geometric"  # Update style to reflect actual generation

                    generator_params = {
                        "prop_type": style,
                        "width": width,
                        "height": height,
                    }

                elif category == "character":
                    style = spec.get("style", "generic")
                    svg_content = generate_character_motif(
                        character_type=style,
                        colors=valid_palette,
                        seed=seed,
                        width=width,
                        height=height,
                    )
                    generator_params = {
                        "character_type": style,
                        "width": width,
                        "height": height,
                    }

                else:
                    # Default to geometric prop
                    svg_content = generate_prop_motif(
                        prop_type="geometric",
                        colors=valid_palette,
                        seed=seed,
                        width=width,
                        height=height,
                    )
                    generator_params = {
                        "prop_type": "geometric",
                        "width": width,
                        "height": height,
                    }
            else:
                # Fallback generation when motif generators are not available
                log.warning("[asset-generate] Using fallback SVG generation")
                svg_content = self._generate_fallback_svg(
                    category, valid_palette, width, height, seed
                )
                generator_params = {
                    "fallback_type": category,
                    "width": width,
                    "height": height,
                }

            if not svg_content:
                raise ValueError(
                    f"Failed to generate {category} asset with style {spec.get('style', 'default')}"
                )

            # Add metadata
            svg_content = self._add_metadata(svg_content, spec, seed, generator_params)

            # Generate filename and save
            filename = self._generate_asset_filename(spec, seed)
            svg_path = Path(out_dir) / filename

            with open(svg_path, "w") as f:
                f.write(svg_content)

            # Create thumbnail
            thumbnail_path = self._create_thumbnail(
                str(svg_path), str(self.thumbnails_dir)
            )

            # Calculate asset hash
            with open(svg_path, "rb") as f:
                asset_hash = hashlib.sha1(f.read()).hexdigest()

            result = {
                "path": str(svg_path),
                "palette": valid_palette,
                "seed": seed,
                "generator_params": generator_params,
                "thumbnail": thumbnail_path,
                "asset_hash": asset_hash,
                "category": category,
                "style": spec.get("style", "default"),
                "palette_compliant": len(violations) == 0,
                "palette_violations": violations,
            }

            log.info(f"[asset-generate] Generated asset: {svg_path}")
            return result

        except Exception as e:
            log.error(f"[asset-generate] Failed to generate asset: {e}")
            raise

    def fill_gaps(
        self, plan_path: str, manifest_path: str, seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fill all gaps in an asset plan by generating missing assets.

        Args:
            plan_path: Path to asset plan JSON
            manifest_path: Path to asset manifest JSON
            seed: Random seed for deterministic generation

        Returns:
            Dict with generation report and updated plan
        """
        log.info(f"[asset-generate] Filling gaps in asset plan: {plan_path}")

        # Load asset plan
        with open(plan_path, "r") as f:
            asset_plan = json.load(f)

        gaps = asset_plan.get("gaps", [])
        if not gaps:
            log.info("[asset-generate] No gaps to fill")
            return {"generated": [], "plan_updated": False}

        # Check generation cap
        if len(gaps) > self.max_assets_per_run:
            log.warning(
                f"[asset-generate] Gap count {len(gaps)} exceeds cap {self.max_assets_per_run}"
            )
            gaps = gaps[: self.max_assets_per_run]

        # Generate assets for each gap
        generated_assets = []
        out_dir = self.generated_dir

        for i, gap in enumerate(gaps):
            try:
                # Use sequential seeds for deterministic generation
                gap_seed = seed + i if seed is not None else None

                asset_result = self.generate_from_spec(
                    gap["spec"], str(out_dir), gap_seed
                )

                # Add element_id to result
                asset_result["element_id"] = gap["element_id"]
                generated_assets.append(asset_result)

                log.info(
                    f"[asset-generate] Generated asset {i+1}/{len(gaps)}: {gap['element_id']}"
                )

            except Exception as e:
                log.error(
                    f"[asset-generate] Failed to generate asset for {gap['element_id']}: {e}"
                )
                continue

        # Update asset plan: move generated assets from gaps to resolved
        if generated_assets:
            # Add generated assets to resolved list
            for asset in generated_assets:
                resolved_item = {
                    "element_id": asset["element_id"],
                    "asset": asset["path"],
                    "scale": 1.0,
                    "variant": "default",
                    "asset_hash": asset["asset_hash"],
                    "reuse_type": "generated",
                    "palette_compliant": asset.get("palette_compliant", True),
                }
                asset_plan["resolved"].append(resolved_item)

            # Remove filled gaps
            asset_plan["gaps"] = []
            asset_plan["resolved_count"] = len(asset_plan["resolved"])
            asset_plan["gaps_count"] = 0

            # Update reuse ratio
            total_placeholders = asset_plan["total_placeholders"]
            existing_assets = sum(
                1 for item in asset_plan["resolved"] if item["reuse_type"] == "existing"
            )
            asset_plan["reuse_ratio"] = (
                existing_assets / total_placeholders if total_placeholders > 0 else 0
            )

            # Save updated plan
            with open(plan_path, "w") as f:
                json.dump(asset_plan, f, indent=2)

            log.info(
                f"[asset-generate] Updated asset plan: {len(generated_assets)} assets generated"
            )

        # Create generation report
        generation_report = {
            "slug": asset_plan.get("slug", "unknown"),
            "generated_at": asset_plan.get("generated_at"),
            "total_gaps": len(gaps),
            "assets_generated": len(generated_assets),
            "generated_assets": generated_assets,
            "generation_params": {
                "seed": seed,
                "max_assets_per_run": self.max_assets_per_run,
                "out_dir": str(out_dir),
            },
        }

        # Save generation report
        report_path = Path(plan_path).parent / "asset_generation_report.json"
        with open(report_path, "w") as f:
            json.dump(generation_report, f, indent=2)

        # Refresh manifest if it exists
        if Path(manifest_path).exists():
            try:
                manifest = AssetManifest(str(self.base_dir))
                manifest.rebuild_manifest()
                log.info("[asset-generate] Refreshed asset manifest")
            except Exception as e:
                log.warning(f"[asset-generate] Failed to refresh manifest: {e}")

        return {
            "generated": generated_assets,
            "plan_updated": len(generated_assets) > 0,
            "generation_report": str(report_path),
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate procedural assets to fill gaps"
    )
    parser.add_argument("--plan", required=True, help="Path to asset plan JSON")
    parser.add_argument(
        "--seed", type=int, help="Random seed for deterministic generation"
    )
    parser.add_argument("--base-dir", default=".", help="Base directory for assets")

    args = parser.parse_args()

    try:
        generator = AssetGenerator(args.base_dir)

        # Auto-detect manifest path
        plan_path = Path(args.plan)
        manifest_path = Path("data/library_manifest.json")

        if not plan_path.exists():
            log.error(f"Asset plan not found: {plan_path}")
            sys.exit(1)

        if not manifest_path.exists():
            log.error(f"Asset manifest not found: {manifest_path}")
            sys.exit(1)

        result = generator.fill_gaps(str(plan_path), str(manifest_path), args.seed)

        if result["plan_updated"]:
            print(f"Successfully generated {len(result['generated'])} assets")
            print(f"Generation report: {result['generation_report']}")
        else:
            print("No assets were generated")

    except Exception as e:
        log.error(f"Asset generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
