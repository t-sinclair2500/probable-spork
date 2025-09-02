#!/usr/bin/env python3
"""
Procedural Motif Generators for Mid-Century Design System

This module generates SVG motifs programmatically for backgrounds and props,
respecting brand palette and safe margins. All functions are deterministic
given the same seed parameters.
"""

import hashlib
import json
import math
import random
from typing import List, Optional, Tuple

from pathlib import Path

from .sdk import SAFE_MARGINS_PX

# ============================================================================
# DESIGN LANGUAGE CONSTRAINTS
# ============================================================================


# Load design language colors
def _load_design_colors() -> dict:
    """Load colors from design language configuration."""
    try:
        with open("design/design_language.json", "r") as f:
            data = json.load(f)
            return data.get("colors", {})
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback to core palette if design file unavailable
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


# ============================================================================
# COLOR ENGINE
# ============================================================================


def pick_scene_colors(
    palette: List[str], n: int = 3, seed: Optional[int] = None
) -> List[str]:
    """Select n colors from palette for a scene, respecting max_colors_per_scene rule."""
    if seed is not None:
        random.seed(seed)

    # Ensure we don't exceed palette size
    n = min(n, len(palette))

    # Random selection without replacement
    selected = random.sample(palette, n)

    # Reset seed to avoid affecting other functions
    if seed is not None:
        random.seed()

    return selected


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def _add_jitter(
    value: float, max_jitter: float = 2.0, seed: Optional[int] = None
) -> float:
    """Add slight jitter for hand-cut aesthetic."""
    if seed is not None:
        random.seed(seed)

    jitter = random.uniform(-max_jitter, max_jitter)
    result = value + jitter

    if seed is not None:
        random.seed()

    return result


def _validate_color(color: str, allowed_colors: dict) -> bool:
    """Validate that color is in the allowed palette."""
    # Accept any valid hex color or named color
    import re

    hex_pattern = r"^#[0-9a-fA-F]{6}$"
    if re.match(hex_pattern, color):
        return True
    # Also accept colors from the allowed palette
    return color in allowed_colors.values()


def _generate_cache_key(params: dict) -> str:
    """Generate deterministic cache key from function parameters."""
    # Sort parameters for consistent hashing
    sorted_params = json.dumps(params, sort_keys=True)
    return hashlib.sha1(sorted_params.encode()).hexdigest()


# ============================================================================
# SVG GENERATION FUNCTIONS
# ============================================================================


def make_starburst(
    cx: int,
    cy: int,
    color_spokes: str,
    color_knobs: str,
    spokes: int = 12,
    inner: int = 12,
    outer: int = 48,
    knob_radius: int = 3,
    seed: Optional[int] = None,
) -> str:
    """
    Generate atomic starburst pattern SVG.

    Args:
        cx, cy: Center coordinates
        color_spokes: Color for spoke lines
        color_knobs: Color for end knobs
        spokes: Number of radiating spokes
        inner: Inner radius of spokes
        outer: Outer radius of spokes
        knob_radius: Radius of end knobs
        seed: Random seed for deterministic output

    Returns:
        SVG string with starburst pattern
    """
    if seed is not None:
        random.seed(seed)

    # Validate colors against design palette
    allowed_colors = _load_design_colors()
    if not _validate_color(color_spokes, allowed_colors):
        raise ValueError(f"Invalid spoke color: {color_spokes}")
    if not _validate_color(color_knobs, allowed_colors):
        raise ValueError(f"Invalid knob color: {color_knobs}")

    # Calculate dimensions for viewBox
    margin = max(outer + knob_radius, SAFE_MARGINS_PX)
    viewbox_w = (cx + margin) * 2
    viewbox_h = (cy + margin) * 2

    # Start building SVG
    svg_elements = []

    # Add spokes
    for i in range(spokes):
        angle = (i * 360 / spokes) + _add_jitter(0, 1.0, seed + i if seed else None)
        angle_rad = math.radians(angle)

        # Inner point
        x1 = cx + inner * math.cos(angle_rad)
        y1 = cy + inner * math.sin(angle_rad)

        # Outer point
        x2 = cx + outer * math.cos(angle_rad)
        y2 = cy + outer * math.sin(angle_rad)

        # Add slight jitter to end points
        x2 = _add_jitter(x2, 1.5, seed + i * 100 if seed else None)
        y2 = _add_jitter(y2, 1.5, seed + i * 100 if seed else None)

        svg_elements.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color_spokes}" stroke-width="2" stroke-linecap="round"/>'
        )

        # Add end knob
        svg_elements.append(
            f'<circle cx="{x2:.1f}" cy="{y2:.1f}" r="{knob_radius}" fill="{color_knobs}"/>'
        )

    # Add center circle
    svg_elements.append(
        f'<circle cx="{cx}" cy="{cy}" r="{inner//2}" fill="{color_knobs}"/>'
    )

    # Reset seed
    if seed is not None:
        random.seed()

    # Assemble SVG
    svg_content = "\n  ".join(svg_elements)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {viewbox_w} {viewbox_h}">
  <desc>Atomic starburst pattern with {spokes} spokes, mid-century geometric design</desc>
  {svg_content}
</svg>"""


def make_boomerang(
    center: Tuple[int, int],
    w: int,
    h: int,
    rotation_deg: float,
    color: str,
    seed: Optional[int] = None,
) -> str:
    """
    Generate boomerang shape SVG.

    Args:
        center: Center coordinates (x, y)
        w: Width of boomerang
        h: Height of boomerang
        rotation_deg: Rotation in degrees
        color: Fill color
        seed: Random seed for deterministic output

    Returns:
        SVG string with boomerang shape
    """
    if seed is not None:
        random.seed(seed)

    # Validate color
    allowed_colors = _load_design_colors()
    if not _validate_color(color, allowed_colors):
        raise ValueError(f"Invalid color: {color}")

    cx, cy = center

    # Calculate boomerang path points
    # Create a curved boomerang shape using quadratic bezier curves
    half_w = w // 2
    half_h = h // 2

    # Add slight jitter for organic feel
    jitter_w = _add_jitter(half_w, 3.0, seed)
    jitter_h = _add_jitter(half_h, 3.0, seed)

    # Define boomerang path
    path_data = [
        f"M {cx - jitter_w} {cy - jitter_h}",  # Start at top-left
        f"Q {cx} {cy - jitter_h - 20} {cx + jitter_w} {cy - jitter_h}",  # Top curve
        f"L {cx + jitter_w + 10} {cy + jitter_h//2}",  # Right edge
        f"Q {cx + jitter_w} {cy + jitter_h} {cx} {cy + jitter_h}",  # Bottom curve
        f"L {cx - jitter_w - 10} {cy + jitter_h//2}",  # Left edge
        "Z",  # Close path
    ]

    # Calculate viewBox with rotation margin
    margin = max(w, h) + SAFE_MARGINS_PX
    viewbox_w = margin * 2
    viewbox_h = margin * 2

    # Reset seed
    if seed is not None:
        random.seed()

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {viewbox_w} {viewbox_h}">
  <desc>Boomerang shape with mid-century organic curves</desc>
  <g transform="translate({margin} {margin}) rotate({rotation_deg} {cx} {cy})">
    <path d="{' '.join(path_data)}" fill="{color}" stroke="none"/>
  </g>
</svg>"""


def make_cutout_collage(
    w: int,
    h: int,
    n: int,
    palette: List[str],
    min_spacing: int = 48,
    seed: Optional[int] = None,
) -> str:
    """
    Generate organic cutout collage using Poisson placement.

    Args:
        w: Width of collage area
        h: Height of collage area
        n: Number of cutouts to place
        palette: List of colors to use
        min_spacing: Minimum distance between cutouts
        seed: Random seed for deterministic output

    Returns:
        SVG string with organic cutout collage
    """
    if seed is not None:
        random.seed(seed)

    # Validate colors
    allowed_colors = _load_design_colors()
    for color in palette:
        if not _validate_color(color, allowed_colors):
            raise ValueError(f"Invalid color in palette: {color}")

    # Limit to max 3 colors per scene
    if len(palette) > 3:
        palette = palette[:3]

    # Generate cutout positions using simple grid with jitter
    cutouts = []
    grid_size = int(math.sqrt(n)) + 1

    for i in range(min(n, grid_size * grid_size)):
        row = i // grid_size
        col = i % grid_size

        # Calculate base position
        base_x = (col + 0.5) * (w / grid_size)
        base_y = (row + 0.5) * (h / grid_size)

        # Add jitter
        x = _add_jitter(base_x, w // (grid_size * 4), seed + i * 10)
        y = _add_jitter(base_y, h // (grid_size * 4), seed + i * 10)

        # Ensure within bounds
        x = max(SAFE_MARGINS_PX, min(w - SAFE_MARGINS_PX, x))
        y = max(SAFE_MARGINS_PX, min(h - SAFE_MARGINS_PX, y))

        # Random size and color
        size = random.uniform(20, 60)
        color = random.choice(palette)

        cutouts.append(
            {
                "x": x,
                "y": y,
                "size": size,
                "color": color,
                "rotation": random.uniform(0, 360),
                "shape_type": random.choice(["leaf", "coral", "blob"]),
            }
        )

    # Build SVG elements
    svg_elements = []

    for i, cutout in enumerate(cutouts):
        x, y = cutout["x"], cutout["y"]
        size = cutout["size"]
        color = cutout["color"]
        rotation = cutout["rotation"]
        shape_type = cutout["shape_type"]

        # Generate organic shape path
        if shape_type == "leaf":
            path = _generate_leaf_path(x, y, size, seed + i * 100)
        elif shape_type == "coral":
            path = _generate_coral_path(x, y, size, seed + i * 100)
        else:  # blob
            path = _generate_blob_path(x, y, size, seed + i * 100)

        svg_elements.append(
            f'<g transform="translate({x} {y}) rotate({rotation})">'
            f'<path d="{path}" fill="{color}" stroke="none"/>'
            f"</g>"
        )

    # Reset seed
    if seed is not None:
        random.seed()

    # Assemble SVG
    svg_content = "\n  ".join(svg_elements)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">
  <desc>Organic cutout collage with {n} shapes in mid-century style</desc>
  {svg_content}
</svg>"""


def _generate_leaf_path(x: float, y: float, size: float, seed: int) -> str:
    """Generate leaf-shaped path."""
    random.seed(seed)

    # Leaf parameters
    length = size
    width = size * 0.6

    # Control points for leaf curve
    cp1x = x + length * 0.3
    cp1y = y - width * 0.5
    cp2x = x + length * 0.7
    cp2y = y + width * 0.3

    # Leaf path
    path = [
        f"M {x} {y}",  # Start at stem
        f"Q {cp1x} {cp1y} {x + length} {y}",  # Top curve
        f"Q {cp2x} {cp2y} {x} {y + width}",  # Bottom curve
        f"Q {x - width * 0.3} {y + width * 0.5} {x} {y}",  # Back to stem
    ]

    random.seed()
    return " ".join(path)


def _generate_coral_path(x: float, y: float, size: float, seed: int) -> str:
    """Generate coral-shaped path."""
    random.seed(seed)

    # Coral parameters
    height = size
    width = size * 0.8

    # Generate branching structure
    branches = random.randint(3, 6)
    path = [f"M {x} {y + height}"]  # Start at base

    for i in range(branches):
        angle = (i * 360 / branches) + random.uniform(-15, 15)
        angle_rad = math.radians(angle)
        branch_length = random.uniform(height * 0.3, height * 0.7)

        end_x = x + math.cos(angle_rad) * branch_length
        end_y = y + height - math.sin(angle_rad) * branch_length

        # Add slight curve
        mid_x = x + math.cos(angle_rad) * branch_length * 0.5
        mid_y = y + height - math.sin(angle_rad) * branch_length * 0.5

        path.append(f"Q {mid_x} {mid_y} {end_x} {end_y}")

    path.append(f"L {x} {y + height} Z")  # Close back to base

    random.seed()
    return " ".join(path)


def _generate_blob_path(x: float, y: float, size: float, seed: int) -> str:
    """Generate organic blob path."""
    random.seed(seed)

    # Blob parameters
    radius = size * 0.5

    # Generate irregular circle with multiple control points
    points = random.randint(6, 10)
    path = []

    for i in range(points):
        angle = i * 360 / points
        angle_rad = math.radians(angle)

        # Vary radius for organic feel
        r = radius + random.uniform(-radius * 0.3, radius * 0.3)

        px = x + r * math.cos(angle_rad)
        py = y + r * math.sin(angle_rad)

        if i == 0:
            path.append(f"M {px} {py}")
        else:
            # Add control point for smooth curves
            prev_angle = (i - 1) * 360 / points
            prev_angle_rad = math.radians(prev_angle)
            prev_r = radius + random.uniform(-radius * 0.3, radius * 0.3)

            cp_x = x + (prev_r + r) * 0.5 * math.cos((prev_angle + angle) * 0.5)
            cp_y = y + (prev_r + r) * 0.5 * math.sin((prev_angle + angle) * 0.5)

            path.append(f"Q {cp_x} {cp_y} {px} {py}")

    path.append("Z")  # Close path

    random.seed()
    return " ".join(path)


# ============================================================================
# FILE OPERATIONS
# ============================================================================


def save_svg(svg_str: str, path: str) -> None:
    """
    Save SVG string to file.

    Args:
        svg_str: SVG content string
        path: File path to save to
    """
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(path_obj, "w") as f:
        f.write(svg_str)


def save_to_cache(svg_str: str, params: dict, cache_dir: str = "render_cache") -> str:
    """
    Save SVG to cache directory with parameter-based filename.

    Args:
        svg_str: SVG content string
        params: Function parameters for cache key generation
        cache_dir: Cache directory path

    Returns:
        Path to cached file
    """
    cache_key = _generate_cache_key(params)
    cache_path = Path(cache_dir) / f"{cache_key}.svg"

    save_svg(svg_str, str(cache_path))
    return str(cache_path)


def generate_background_motif(
    motif_type: str,
    colors: List[str],
    seed: Optional[int] = None,
    width: int = 1920,
    height: int = 1080,
) -> Optional[str]:
    """
    Generate a background motif based on type and colors.

    Args:
        motif_type: Type of motif to generate
        colors: List of colors to use
        seed: Random seed for deterministic output
        width: SVG width
        height: SVG height

    Returns:
        SVG string or None if generation fails
    """
    if seed is not None:
        random.seed(seed)

    try:
        if motif_type == "starburst":
            # Use first two colors for spokes and knobs
            color_spokes = colors[0] if colors else "#1C4FA1"
            color_knobs = colors[1] if len(colors) > 1 else "#F6BE00"
            return make_starburst(
                cx=width // 2,
                cy=height // 2,
                color_spokes=color_spokes,
                color_knobs=color_knobs,
                seed=seed,
            )
        elif motif_type == "boomerang":
            # Use first color for boomerang
            color = colors[0] if colors else "#1C4FA1"
            return make_boomerang(
                center=(width // 2, height // 2),
                w=400,
                h=200,
                rotation_deg=45,
                color=color,
                seed=seed,
            )
        elif motif_type == "cutout_collage":
            # Use first color for cutouts
            color = colors[0] if colors else "#1C4FA1"
            return make_cutout_collage(
                width=width, height=height, color=color, seed=seed
            )
        else:
            # Default to starburst
            color_spokes = colors[0] if colors else "#1C4FA1"
            color_knobs = colors[1] if len(colors) > 1 else "#F6BE00"
            return make_starburst(
                cx=width // 2,
                cy=height // 2,
                color_spokes=color_spokes,
                color_knobs=color_knobs,
                seed=seed,
            )
    except Exception as e:
        print(f"Failed to generate background motif: {e}")
        return None
    finally:
        if seed is not None:
            random.seed()


def generate_prop_motif(
    prop_type: str,
    colors: List[str],
    seed: Optional[int] = None,
    width: int = 200,
    height: int = 200,
) -> Optional[str]:
    """
    Generate a procedural prop asset following mid-century design principles.

    Args:
        prop_type: Type of prop to generate
        colors: List of colors to use
        seed: Random seed for deterministic output
        width: SVG width
        height: SVG height

    Returns:
        SVG string or None if generation fails
    """
    if seed is not None:
        random.seed(seed)

    try:
        # Pick primary color for the prop
        primary_color = colors[0] if colors else "#1C4FA1"
        secondary_color = colors[1] if len(colors) > 1 else "#F6BE00"

        # Generate different prop types
        if "phone" in prop_type.lower() or "device" in prop_type.lower():
            return _make_phone_prop(primary_color, secondary_color, width, height, seed)
        elif "chair" in prop_type.lower() or "furniture" in prop_type.lower():
            return _make_chair_prop(primary_color, secondary_color, width, height, seed)
        elif "clock" in prop_type.lower() or "time" in prop_type.lower():
            return _make_clock_prop(primary_color, secondary_color, width, height, seed)
        elif "book" in prop_type.lower() or "notebook" in prop_type.lower():
            return _make_book_prop(primary_color, secondary_color, width, height, seed)
        else:
            # Default to geometric shape
            return _make_geometric_prop(
                primary_color, secondary_color, width, height, seed
            )
    except Exception as e:
        print(f"Failed to generate prop motif: {e}")
        return None
    finally:
        if seed is not None:
            random.seed()


def generate_character_motif(
    character_type: str,
    colors: List[str],
    seed: Optional[int] = None,
    width: int = 200,
    height: int = 200,
) -> Optional[str]:
    """
    Generate a procedural character asset following mid-century design principles.

    Args:
        character_type: Type of character to generate
        colors: List of colors to use
        seed: Random seed for deterministic output
        width: SVG width
        height: SVG height

    Returns:
        SVG string or None if generation fails
    """
    if seed is not None:
        random.seed(seed)

    try:
        # Pick primary color for the character
        primary_color = colors[0] if colors else "#1C4FA1"
        secondary_color = colors[1] if len(colors) > 1 else "#F6BE00"

        # Generate different character types
        if "narrator" in character_type.lower() or "speaker" in character_type.lower():
            return _make_narrator_character(
                primary_color, secondary_color, width, height, seed
            )
        elif "parent" in character_type.lower() or "adult" in character_type.lower():
            return _make_parent_character(
                primary_color, secondary_color, width, height, seed
            )
        elif "child" in character_type.lower() or "kid" in character_type.lower():
            return _make_child_character(
                primary_color, secondary_color, width, height, seed
            )
        else:
            # Default to generic character
            return _make_generic_character(
                primary_color, secondary_color, width, height, seed
            )
    except Exception as e:
        print(f"Failed to generate character motif: {e}")
        return None
    finally:
        if seed is not None:
            random.seed()


def _make_phone_prop(
    primary_color: str, secondary_color: str, width: int, height: int, seed: int
) -> str:
    """Generate a phone/device prop."""
    # Simple phone shape with mid-century styling
    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <rect x="{width//4}" y="{height//4}" width="{width//2}" height="{height//2}" 
              fill="{primary_color}" rx="8" ry="8"/>
        <rect x="{width//4 + 4}" y="{height//4 + 4}" width="{width//2 - 8}" height="{height//2 - 8}" 
              fill="{secondary_color}" rx="4" ry="4"/>
        <circle cx="{width//2}" cy="{height//2 + 20}" r="4" fill="{primary_color}"/>
    </svg>"""
    return svg


def _make_chair_prop(
    primary_color: str, secondary_color: str, width: int, height: int, seed: int
) -> str:
    """Generate a chair prop."""
    # Simple chair shape with mid-century styling
    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <rect x="{width//4}" y="{height//2}" width="{width//2}" height="{height//4}" 
              fill="{primary_color}" rx="4" ry="4"/>
        <rect x="{width//4}" y="{height//4}" width="{width//2}" height="{height//4}" 
              fill="{secondary_color}" rx="4" ry="4"/>
        <rect x="{width//4 - 8}" y="{height//2}" width="8" height="{height//4}" 
              fill="{primary_color}" rx="2" ry="2"/>
        <rect x="{width*3//4}" y="{height//2}" width="8" height="{height//4}" 
              fill="{primary_color}" rx="2" ry="2"/>
    </svg>"""
    return svg


def _make_clock_prop(
    primary_color: str, secondary_color: str, width: int, height: int, seed: int
) -> str:
    """Generate a clock prop."""
    # Simple clock shape with mid-century styling
    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <circle cx="{width//2}" cy="{height//2}" r="{min(width, height)//3}" 
                fill="{primary_color}" stroke="{secondary_color}" stroke-width="2"/>
        <line x1="{width//2}" y1="{height//2}" x2="{width//2}" y2="{height//4}" 
              stroke="{secondary_color}" stroke-width="3" stroke-linecap="round"/>
        <line x1="{width//2}" y1="{height//2}" x2="{width*3//4}" y2="{height//2}" 
              stroke="{secondary_color}" stroke-width="2" stroke-linecap="round"/>
    </svg>"""
    return svg


def _make_book_prop(
    primary_color: str, secondary_color: str, width: int, height: int, seed: int
) -> str:
    """Generate a book/notebook prop."""
    # Simple book shape with mid-century styling
    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <rect x="{width//4}" y="{height//4}" width="{width//2}" height="{height//2}" 
              fill="{primary_color}" rx="2" ry="2"/>
        <rect x="{width//4 + 2}" y="{height//4 + 2}" width="{width//2 - 4}" height="{height//2 - 4}" 
              fill="{secondary_color}" rx="1" ry="1"/>
        <line x1="{width//4 + 8}" y1="{height//2}" x2="{width*3//4 - 8}" y2="{height//2}" 
              stroke="{primary_color}" stroke-width="1"/>
        <line x1="{width//4 + 8}" y1="{height//2 + 8}" x2="{width*3//4 - 8}" y2="{height//2 + 8}" 
              stroke="{primary_color}" stroke-width="1"/>
    </svg>"""
    return svg


def _make_geometric_prop(
    primary_color: str, secondary_color: str, width: int, height: int, seed: int
) -> str:
    """Generate a generic geometric prop."""
    # Simple geometric shape with mid-century styling
    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <polygon points="{width//4},{height//4} {width*3//4},{height//4} {width//2},{height*3//4}" 
                 fill="{primary_color}"/>
        <circle cx="{width//2}" cy="{height//2}" r="{min(width, height)//8}" fill="{secondary_color}"/>
    </svg>"""
    return svg


def _make_narrator_character(
    primary_color: str, secondary_color: str, width: int, height: int, seed: int
) -> str:
    """Generate a narrator character."""
    # Simple narrator character with mid-century styling
    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <circle cx="{width//2}" cy="{height//3}" r="{min(width, height)//6}" fill="{primary_color}"/>
        <rect x="{width//4}" y="{height//2}" width="{width//2}" height="{height//3}" 
              fill="{primary_color}" rx="8" ry="8"/>
        <rect x="{width//4 + 4}" y="{height//2 + 4}" width="{width//2 - 8}" height="{height//3 - 8}" 
              fill="{secondary_color}" rx="4" ry="4"/>
    </svg>"""
    return svg


def _make_parent_character(
    primary_color: str, secondary_color: str, width: int, height: int, seed: int
) -> str:
    """Generate a parent character."""
    # Simple parent character with mid-century styling
    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <circle cx="{width//2}" cy="{height//3}" r="{min(width, height)//6}" fill="{primary_color}"/>
        <rect x="{width//4}" y="{height//2}" width="{width//2}" height="{height//3}" 
              fill="{primary_color}" rx="8" ry="8"/>
        <circle cx="{width//2 - 20}" cy="{height//2 + 20}" r="8" fill="{secondary_color}"/>
        <circle cx="{width//2 + 20}" cy="{height//2 + 20}" r="8" fill="{secondary_color}"/>
    </svg>"""
    return svg


def _make_child_character(
    primary_color: str, secondary_color: str, width: int, height: int, seed: int
) -> str:
    """Generate a child character."""
    # Simple child character with mid-century styling
    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <circle cx="{width//2}" cy="{height//3}" r="{min(width, height)//8}" fill="{primary_color}"/>
        <rect x="{width//4}" y="{height//2}" width="{width//2}" height="{height//3}" 
              fill="{primary_color}" rx="6" ry="6"/>
        <rect x="{width//4 + 2}" y="{height//2 + 2}" width="{width//2 - 4}" height="{height//3 - 4}" 
              fill="{secondary_color}" rx="4" ry="4"/>
    </svg>"""
    return svg


def _make_generic_character(
    primary_color: str, secondary_color: str, width: int, height: int, seed: int
) -> str:
    """Generate a generic character."""
    # Simple generic character with mid-century styling
    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <circle cx="{width//2}" cy="{height//3}" r="{min(width, height)//6}" fill="{primary_color}"/>
        <rect x="{width//4}" y="{height//2}" width="{width//2}" height="{height//3}" 
              fill="{primary_color}" rx="8" ry="8"/>
    </svg>"""
    return svg


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "make_starburst",
    "make_boomerang",
    "make_cutout_collage",
    "save_svg",
    "save_to_cache",
    "pick_scene_colors",
    "generate_background_motif",
    "generate_prop_motif",
    "generate_character_motif",
]
