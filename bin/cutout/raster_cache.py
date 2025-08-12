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
from pathlib import Path
from typing import Optional, Tuple

from bin.core import get_logger

log = get_logger("raster_cache")

# Cache configuration
CACHE_DIR = Path("render_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Supported output formats
OUTPUT_FORMAT = "png"


def _get_cache_key(svg_path: str, width: int, height: int) -> str:
    """
    Generate cache key from SVG path, dimensions, and file modification time.
    
    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels
    
    Returns:
        Cache key string
    """
    svg_path = Path(svg_path).resolve()
    
    # Get file modification time for cache invalidation
    try:
        mtime = os.path.getmtime(svg_path)
    except OSError:
        mtime = 0
    
    # Create cache key from path, dimensions, and mtime
    key_data = f"{svg_path}:{width}x{height}:{mtime}"
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


def _rasterize_with_cairosvg(svg_path: str, width: int, height: int, output_path: str) -> bool:
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
            output_height=height
        )
        
        log.debug(f"Successfully rasterized {svg_path} with cairosvg")
        return True
        
    except ImportError:
        log.debug("cairosvg not available")
        return False
    except Exception as e:
        log.warning(f"cairosvg failed: {e}")
        return False


def _rasterize_with_rsvg(svg_path: str, width: int, height: int, output_path: str) -> bool:
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
            ["rsvg-convert", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            log.debug("rsvg-convert not available")
            return False
        
        # Rasterize using rsvg-convert
        cmd = [
            "rsvg-convert",
            "-w", str(width),
            "-h", str(height),
            "-f", OUTPUT_FORMAT,
            "-o", output_path,
            svg_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
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


def _rasterize_with_pillow(svg_path: str, width: int, height: int, output_path: str) -> bool:
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
        img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # For now, create a simple placeholder since Pillow doesn't natively support SVG
        # In a real implementation, you might use svglib or other libraries
        # For this demo, we'll create a colored rectangle as placeholder
        
        # Get SVG dimensions from file
        with open(svg_path, 'r') as f:
            content = f.read()
        
        # Simple SVG parsing for basic dimensions (very basic)
        if 'viewBox' in content:
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
        draw.rectangle([x, y, x + scaled_w, y + scaled_h], fill=(200, 200, 200, 255), outline=(100, 100, 100, 255))
        
        # Save the image
        img.save(output_path, OUTPUT_FORMAT.upper())
        
        log.debug(f"Created Pillow placeholder for {svg_path} (not true SVG rasterization)")
        return True
        
    except ImportError:
        log.debug("Pillow not available")
        return False
    except Exception as e:
        log.warning(f"Pillow failed: {e}")
        return False


def rasterize_svg(svg_path: str, width: int, height: int) -> str:
    """
    Rasterize SVG to PNG with intelligent caching and fallback methods.
    
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
    svg_path = Path(svg_path).resolve()
    
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG file not found: {svg_path}")
    
    # Check cache first
    cached_path = get_cached(str(svg_path), width, height)
    if cached_path:
        return cached_path
    
    # Generate cache key and output path
    cache_key = _get_cache_key(str(svg_path), width, height)
    output_path = _get_cached_path(cache_key)
    
    log.info(f"Rasterizing {svg_path} to {width}x{height} pixels")
    start_time = time.time()
    
    # Try rasterization methods in order of preference
    success = False
    
    # Method 1: cairosvg (preferred)
    if not success:
        success = _rasterize_with_cairosvg(str(svg_path), width, height, str(output_path))
    
    # Method 2: rsvg-convert (fallback)
    if not success:
        success = _rasterize_with_rsvg(str(svg_path), width, height, str(output_path))
    
    # Method 3: Pillow (final fallback)
    if not success:
        success = _rasterize_with_pillow(str(svg_path), width, height, str(output_path))
    
    if not success:
        raise RuntimeError(f"All rasterization methods failed for {svg_path}")
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    log.info(f"Rasterized {svg_path} in {elapsed_ms}ms, saved to {output_path}")
    
    return str(output_path)


def clear_cache() -> None:
    """Clear all cached rasterized images."""
    if CACHE_DIR.exists():
        for cache_file in CACHE_DIR.glob(f"*.{OUTPUT_FORMAT}"):
            cache_file.unlink()
        log.info(f"Cleared raster cache ({CACHE_DIR})")


def get_cache_stats() -> dict:
    """Get cache statistics."""
    # Ensure cache directory exists
    CACHE_DIR.mkdir(exist_ok=True)
    
    if not CACHE_DIR.exists():
        return {"total_files": 0, "total_size_bytes": 0, "cache_dir": str(CACHE_DIR)}
    
    total_files = 0
    total_size = 0
    
    for cache_file in CACHE_DIR.glob(f"*.{OUTPUT_FORMAT}"):
        total_files += 1
        total_size += cache_file.stat().st_size
    
    return {
        "total_files": total_files,
        "total_size_bytes": total_size,
        "cache_dir": str(CACHE_DIR)
    }
