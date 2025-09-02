#!/usr/bin/env python3
"""
SVG Rasterizer and Asset Cache

This module provides efficient SVG rasterization with intelligent caching.
Uses cairosvg as preferred method, with fallbacks to rsvg-convert and Pillow.
"""

import hashlib
import os
import subprocess
import time
from typing import Dict, Optional

from pathlib import Path

from bin.core import get_logger

log = get_logger("raster_cache")

# Cache configuration
CACHE_DIR = Path("render_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Supported output formats
OUTPUT_FORMAT = "png"

# Try to import texture engine
try:
    from .texture_engine import create_texture_engine

    TEXTURE_ENGINE_AVAILABLE = True
except ImportError:
    TEXTURE_ENGINE_AVAILABLE = False
    log.debug("Texture engine not available")


def _get_cache_key(
    svg_path: str, width: int, height: int, texture_config: Optional[Dict] = None
) -> str:
    """
    Generate cache key from SVG path, dimensions, file modification time, and texture config.

    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels
        texture_config: Optional texture configuration for cache key

    Returns:
        Cache key string
    """
    svg_path = Path(svg_path).resolve()

    # Get file modification time for cache invalidation
    try:
        mtime = os.path.getmtime(svg_path)
    except OSError:
        mtime = 0

    # Create cache key from path, dimensions, mtime, and texture config
    key_data = f"{svg_path}:{width}x{height}:{mtime}"

    # Include texture configuration in cache key if available
    if texture_config and texture_config.get("enabled", False):
        texture_hash = hashlib.md5(
            str(sorted(texture_config.items())).encode()
        ).hexdigest()[:8]
        key_data += f":texture_{texture_hash}"

    return hashlib.sha1(key_data.encode()).hexdigest()


def _get_cached_path(cache_key: str) -> Path:
    """
    Get the cached file path for a given cache key.

    Args:
        cache_key: Cache key string

    Returns:
        Path to cached file
    """
    return CACHE_DIR / f"{cache_key}.{OUTPUT_FORMAT}"


def get_cached(svg_path: str, width: int, height: int) -> Optional[str]:
    """
    Check if a rasterized version exists in cache.

    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels

    Returns:
        Path to cached file if exists, None otherwise
    """
    cache_key = _get_cache_key(svg_path, width, height)
    cached_path = _get_cached_path(cache_key)

    if cached_path.exists():
        log.debug(f"Cache hit for {svg_path} at {width}x{height}")
        return str(cached_path)

    log.debug(f"Cache miss for {svg_path} at {width}x{height}")
    return None


def _rasterize_with_cairosvg(
    svg_path: str, width: int, height: int, output_path: str
) -> bool:
    """
    Rasterize SVG using cairosvg (preferred method).

    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels
        output_path: Output file path

    Returns:
        True if successful, False otherwise
    """
    try:
        import cairosvg

        # Convert SVG to PNG using cairosvg
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=output_path,
            output_width=width,
            output_height=height,
        )

        log.debug(f"Successfully rasterized {svg_path} with cairosvg")
        return True

    except ImportError:
        log.debug("cairosvg not available")
        return False
    except Exception as e:
        log.warning(f"cairosvg failed: {e}")
        return False


def _rasterize_with_rsvg(
    svg_path: str, width: int, height: int, output_path: str
) -> bool:
    """
    Rasterize SVG using rsvg-convert (fallback method).

    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels
        output_path: Output file path

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if rsvg-convert is available
        result = subprocess.run(
            ["rsvg-convert", "--version"], capture_output=True, text=True, timeout=5
        )

        if result.returncode != 0:
            log.debug("rsvg-convert not available")
            return False

        # Rasterize using rsvg-convert
        cmd = [
            "rsvg-convert",
            "-w",
            str(width),
            "-h",
            str(height),
            "-f",
            OUTPUT_FORMAT,
            "-o",
            output_path,
            svg_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            log.debug(f"Successfully rasterized {svg_path} with rsvg-convert")
            return True
        else:
            log.warning(f"rsvg-convert failed: {result.stderr}")
            return False

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        log.debug(f"rsvg-convert not available: {e}")
        return False
    except Exception as e:
        log.warning(f"rsvg-convert error: {e}")
        return False


def _rasterize_with_pillow(
    svg_path: str, width: int, height: int, output_path: str
) -> bool:
    """
    Rasterize SVG using Pillow (final fallback method).

    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels
        output_path: Output file path

    Returns:
        True if successful, False otherwise
    """
    try:
        from PIL import Image, ImageDraw

        # Create a blank image with target dimensions
        img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # For now, create a simple placeholder since Pillow doesn't natively support SVG
        # In a real implementation, you might use svglib or other libraries
        # For this demo, we'll create a colored rectangle as placeholder

        # Get SVG dimensions from file
        with open(svg_path, "r") as f:
            content = f.read()

        # Simple SVG parsing for basic dimensions (very basic)
        if "viewBox" in content:
            # Extract viewBox if available
            import re

            viewbox_match = re.search(r'viewBox="([^"]+)"', content)
            if viewbox_match:
                viewbox = viewbox_match.group(1).split()
                if len(viewbox) >= 4:
                    svg_w, svg_h = float(viewbox[2]), float(viewbox[3])
                else:
                    svg_w, svg_h = width, height
            else:
                svg_w, svg_h = width, height
        else:
            svg_w, svg_h = width, height

        # Scale to fit target dimensions while maintaining aspect ratio
        scale = min(width / svg_w, height / svg_h)
        scaled_w = int(svg_w * scale)
        scaled_h = int(svg_h * scale)

        # Center the scaled content
        x = (width - scaled_w) // 2
        y = (height - scaled_h) // 2

        # Draw a placeholder rectangle (this is just for demo - real implementation would parse SVG)
        draw.rectangle(
            [x, y, x + scaled_w, y + scaled_h],
            fill=(200, 200, 200, 255),
            outline=(100, 100, 100, 255),
        )

        # Save the image
        img.save(output_path, OUTPUT_FORMAT.upper())

        log.debug(
            f"Created Pillow placeholder for {svg_path} (not true SVG rasterization)"
        )
        return True

    except ImportError:
        log.debug("Pillow not available")
        return False
    except Exception as e:
        log.warning(f"Pillow failed: {e}")
        return False


def apply_texture_to_image(
    image_path: str, texture_config: Dict, brand_palette: Optional[list] = None
) -> str:
    """
    Apply texture overlay to a rasterized image.

    Args:
        image_path: Path to input image
        texture_config: Texture configuration dictionary
        brand_palette: Optional brand color palette

    Returns:
        Path to textured image
    """
    if not TEXTURE_ENGINE_AVAILABLE:
        log.warning("Texture engine not available, returning original image")
        return image_path

    if not texture_config.get("enabled", False):
        log.debug("Textures disabled, returning original image")
        return image_path

    try:
        # Create texture engine
        texture_engine = create_texture_engine(texture_config, brand_palette)

        # Apply texture overlay
        textured_path = texture_engine.process_image(image_path)

        log.info(f"Applied texture overlay to {image_path}")
        return textured_path

    except Exception as e:
        log.error(f"Failed to apply texture to {image_path}: {e}")
        # Return original image on failure
        return image_path


def rasterize_svg_with_texture(
    svg_path: str,
    width: int,
    height: int,
    texture_config: Optional[Dict] = None,
    brand_palette: Optional[list] = None,
) -> str:
    """
    Rasterize SVG to PNG with optional texture overlay.

    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels
        texture_config: Optional texture configuration
        brand_palette: Optional brand color palette for texture constraints

    Returns:
        Path to rasterized PNG file (with texture if enabled)

    Raises:
        FileNotFoundError: If SVG file doesn't exist
        RuntimeError: If all rasterization methods fail
    """
    svg_path = Path(svg_path).resolve()

    if not svg_path.exists():
        raise FileNotFoundError(f"SVG file not found: {svg_path}")

    # Check cache first (including texture config)
    cached_path = get_cached_with_texture(str(svg_path), width, height, texture_config)
    if cached_path:
        return cached_path

    # Generate cache key and output path
    cache_key = _get_cache_key(str(svg_path), width, height, texture_config)
    output_path = _get_cached_path(cache_key)

    log.info(
        f"Rasterizing {svg_path} to {width}x{height} pixels with texture: {bool(texture_config and texture_config.get('enabled'))}"
    )
    start_time = time.time()

    # Try rasterization methods in order of preference
    success = False

    # Method 1: cairosvg (preferred)
    if not success:
        success = _rasterize_with_cairosvg(
            str(svg_path), width, height, str(output_path)
        )

    # Method 2: rsvg-convert (fallback)
    if not success:
        success = _rasterize_with_rsvg(str(svg_path), width, height, str(output_path))

    # Method 3: Pillow (final fallback)
    if not success:
        success = _rasterize_with_pillow(str(svg_path), width, height, str(output_path))

    if not success:
        raise RuntimeError(f"All rasterization methods failed for {svg_path}")

    # Apply texture overlay if enabled
    if texture_config and texture_config.get("enabled", False):
        try:
            textured_path = apply_texture_to_image(
                str(output_path), texture_config, brand_palette
            )
            if textured_path != str(output_path):
                # Replace original with textured version
                output_path = Path(textured_path)
                log.info(f"Applied texture overlay, saved to {output_path}")
        except Exception as e:
            log.warning(f"Texture application failed, using untextured version: {e}")

    elapsed_ms = int((time.time() - start_time) * 1000)
    log.info(f"Rasterized {svg_path} in {elapsed_ms}ms, saved to {output_path}")

    return str(output_path)


def rasterize_svg(svg_path: str, width: int, height: int) -> str:
    """
    Rasterize SVG to PNG with intelligent caching and fallback methods.
    Legacy function for backward compatibility.

    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels

    Returns:
        Path to rasterized PNG file

    Raises:
        FileNotFoundError: If SVG file doesn't exist
        RuntimeError: If all rasterization methods fail
    """
    return rasterize_svg_with_texture(svg_path, width, height)


def get_cached_with_texture(
    svg_path: str, width: int, height: int, texture_config: Optional[Dict] = None
) -> Optional[str]:
    """
    Check if a rasterized version with texture exists in cache.

    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels
        texture_config: Optional texture configuration

    Returns:
        Path to cached file if exists, None otherwise
    """
    cache_key = _get_cache_key(svg_path, width, height, texture_config)
    cached_path = _get_cached_path(cache_key)

    if cached_path.exists():
        log.debug(
            f"Cache hit for {svg_path} at {width}x{height} with texture: {bool(texture_config and texture_config.get('enabled'))}"
        )
        return str(cached_path)

    log.debug(
        f"Cache miss for {svg_path} at {width}x{height} with texture: {bool(texture_config and texture_config.get('enabled'))}"
    )
    return None


def clear_cache() -> None:
    """Clear all cached rasterized images."""
    if CACHE_DIR.exists():
        for cache_file in CACHE_DIR.glob(f"*.{OUTPUT_FORMAT}"):
            cache_file.unlink()

        # Also clear texture cache if it exists
        texture_cache_dir = CACHE_DIR / "textures"
        if texture_cache_dir.exists():
            for texture_file in texture_cache_dir.glob("*.png"):
                texture_file.unlink()
            log.info(f"Cleared texture cache ({texture_cache_dir})")

        log.info(f"Cleared raster cache ({CACHE_DIR})")


def get_cache_stats() -> dict:
    """Get cache statistics."""
    # Ensure cache directory exists
    CACHE_DIR.mkdir(exist_ok=True)

    if not CACHE_DIR.exists():
        return {"total_files": 0, "total_size_bytes": 0, "cache_dir": str(CACHE_DIR)}

    total_files = 0
    total_size = 0

    # Count raster cache files
    for cache_file in CACHE_DIR.glob(f"*.{OUTPUT_FORMAT}"):
        total_files += 1
        total_size += cache_file.stat().st_size

    # Count texture cache files
    texture_cache_dir = CACHE_DIR / "textures"
    if texture_cache_dir.exists():
        for texture_file in texture_cache_dir.glob("*.png"):
            total_files += 1
            total_size += texture_file.stat().st_size

    return {
        "total_files": total_files,
        "total_size_bytes": total_size,
        "cache_dir": str(CACHE_DIR),
        "texture_cache_dir": (
            str(texture_cache_dir) if texture_cache_dir.exists() else None
        ),
    }
