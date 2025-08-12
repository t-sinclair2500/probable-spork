#!/usr/bin/env python3
"""
Texture Integration for Rasterization Pipeline

This module provides functions to integrate texture overlays with the existing
rasterization system, maintaining backward compatibility while adding texture support.
"""

import os
from pathlib import Path
from typing import Dict, Optional

from bin.core import get_logger

log = get_logger("texture_integration")

# Try to import texture engine
try:
    from .texture_engine import create_texture_engine
    TEXTURE_ENGINE_AVAILABLE = True
except ImportError:
    TEXTURE_ENGINE_AVAILABLE = False
    log.debug("Texture engine not available")


def apply_texture_to_image(image_path: str, texture_config: Dict, brand_palette: Optional[list] = None) -> str:
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


def get_texture_cache_key(svg_path: str, width: int, height: int, texture_config: Optional[Dict] = None) -> str:
    """
    Generate cache key that includes texture configuration.
    
    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels
        texture_config: Optional texture configuration
        
    Returns:
        Cache key string
    """
    import hashlib
    import os
    
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
        texture_hash = hashlib.md5(str(sorted(texture_config.items())).encode()).hexdigest()[:8]
        key_data += f":texture_{texture_hash}"
    
    return hashlib.sha1(key_data.encode()).hexdigest()


def check_texture_cache(svg_path: str, width: int, height: int, texture_config: Optional[Dict] = None) -> Optional[str]:
    """
    Check if a textured version exists in cache.
    
    Args:
        svg_path: Path to SVG file
        width: Target width in pixels
        height: Target height in pixels
        texture_config: Optional texture configuration
        
    Returns:
        Path to cached file if exists, None otherwise
    """
    from .raster_cache import CACHE_DIR, OUTPUT_FORMAT
    
    cache_key = get_texture_cache_key(svg_path, width, height, texture_config)
    cached_path = CACHE_DIR / f"{cache_key}.{OUTPUT_FORMAT}"
    
    if cached_path.exists():
        log.debug(f"Texture cache hit for {svg_path} at {width}x{height}")
        return str(cached_path)
    
    log.debug(f"Texture cache miss for {svg_path} at {width}x{height}")
    return None


def process_rasterized_with_texture(
    raster_path: str, 
    texture_config: Dict, 
    brand_palette: Optional[list] = None
) -> str:
    """
    Process a rasterized image with texture overlay.
    
    Args:
        raster_path: Path to rasterized image
        texture_config: Texture configuration
        brand_palette: Optional brand color palette
        
    Returns:
        Path to processed image
    """
    if not texture_config.get("enabled", False):
        return raster_path
    
    try:
        # Apply texture overlay
        textured_path = apply_texture_to_image(raster_path, texture_config, brand_palette)
        
        if textured_path != raster_path:
            log.info(f"Applied texture overlay to {raster_path}")
            return textured_path
        else:
            return raster_path
            
    except Exception as e:
        log.error(f"Failed to apply texture to {raster_path}: {e}")
        return raster_path
