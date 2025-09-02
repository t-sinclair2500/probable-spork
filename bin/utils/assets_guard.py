#!/usr/bin/env python3
"""
Asset guard utilities for ensuring required brand assets exist.
Generates placeholders when assets are missing to prevent crashes.
"""

import logging
from typing import Callable, Optional

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("assets_guard")


def ensure_file(
    path: str, kind: str, placeholder_fn: Optional[Callable[[], str]] = None
) -> str:
    """
    Ensure a file exists, creating a placeholder if missing.

    Args:
        path: Path to the required file
        kind: Human-readable description of the asset type (e.g., "font", "logo", "overlay")
        placeholder_fn: Optional function to create a placeholder file

    Returns:
        Path to the existing or created file

    Raises:
        FileNotFoundError: If file missing and no placeholder_fn provided
    """
    file_path = Path(path)

    if file_path.exists():
        return str(file_path)

    # File doesn't exist
    log.warning(f"Missing {kind}: {path}")

    if placeholder_fn:
        try:
            placeholder_path = placeholder_fn()
            log.warning(f"Created placeholder {kind}: {placeholder_path}")
            return placeholder_path
        except Exception as e:
            log.error(f"Failed to create placeholder {kind}: {e}")
            raise FileNotFoundError(
                f"Missing {kind}: {path} (placeholder creation failed)"
            )
    else:
        log.error(f"No placeholder function provided for missing {kind}: {path}")
        raise FileNotFoundError(f"Missing {kind}: {path}")


def create_font_placeholder(font_path: str) -> str:
    """Create a placeholder font file."""
    # For fonts, we'll use PIL's default font and just log the warning
    # The actual font loading will be handled by the calling code
    log.warning(f"Using system default font instead of: {font_path}")
    return "/System/Library/Fonts/Helvetica.ttc"  # macOS fallback


def create_overlay_placeholder(overlay_path: str) -> str:
    """Create a placeholder overlay image."""
    placeholder_path = Path(overlay_path)
    placeholder_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a 640x640 transparent PNG with white "MISSING OVERLAY" text
    try:
        img = Image.new("RGBA", (640, 640), (0, 0, 0, 0))  # Transparent background
        draw = ImageDraw.Draw(img)

        # Try to use a system font
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        except:
            try:
                font = ImageFont.load_default()
            except:
                # Last resort: create a simple text overlay
                font = None

        # Add semi-transparent background for text
        text_bg = Image.new("RGBA", (400, 60), (255, 255, 255, 180))
        img.paste(text_bg, (120, 290), text_bg)

        # Add text
        text = "MISSING OVERLAY"
        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_x = (640 - text_w) // 2
            text_y = 300
            draw.text((text_x, text_y), text, font=font, fill=(255, 0, 0, 255))
        else:
            # Simple text without font
            draw.text((200, 300), text, fill=(255, 0, 0, 255))

        img.save(placeholder_path, "PNG")
        log.warning(f"Created placeholder overlay: {placeholder_path}")
        return str(placeholder_path)

    except Exception as e:
        log.error(f"Failed to create overlay placeholder: {e}")
        # Create a minimal 1x1 transparent PNG as last resort
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        img.save(placeholder_path, "PNG")
        return str(placeholder_path)


def ensure_font(font_path: str) -> str:
    """Ensure a font file exists, using system default if missing."""
    return ensure_file(font_path, "font", lambda: create_font_placeholder(font_path))


def ensure_overlay(overlay_path: str) -> str:
    """Ensure an overlay image exists, creating placeholder if missing."""
    return ensure_file(
        overlay_path, "overlay", lambda: create_overlay_placeholder(overlay_path)
    )


def ensure_palette(palette_path: str) -> dict:
    """Ensure a palette/style file exists, returning default if missing."""
    try:
        import yaml

        with open(palette_path, "r") as f:
            return yaml.safe_load(f)
    except Exception:
        log.warning(f"Missing or invalid palette: {palette_path}, using defaults")
        return {
            "colors": ["#1a1a1a", "#2d2d2d", "#ffffff", "#f0f0f0"],
            "background_colors": ["#1a1a1a", "#2d2d2d", "#3a3a3a"],
            "text_colors": ["#ffffff", "#f0f0f0", "#e0e0e0"],
        }
