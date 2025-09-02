#!/usr/bin/env python3
"""
Texture Integration for Rasterization Pipeline

This module provides functions to integrate texture overlays with the existing
rasterization system, maintaining backward compatibility while adding texture support.
"""

import os
from typing import Dict, Optional

from pathlib import Path

from bin.core import get_logger

log = get_logger("texture_integration")

# Try to import texture engine
try:
    from .texture_engine import apply_textures_to_frame, texture_signature

    TEXTURE_ENGINE_AVAILABLE = True
except ImportError:
    TEXTURE_ENGINE_AVAILABLE = False
    log.debug("Texture engine not available")


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

    if not texture_config.get("enable", False):
        log.debug("Textures disabled, returning original image")
        return image_path

    try:
        from PIL import Image

        # Load image
        img = Image.open(image_path)

        # Apply textures using new API
        seed = 42  # Fixed seed for consistency
        textured_img = apply_textures_to_frame(img, texture_config, seed)

        # Save textured image
        base_path = Path(image_path)
        textured_path = str(
            base_path.parent / f"{base_path.stem}_textured{base_path.suffix}"
        )
        textured_img.save(textured_path)

        log.info(f"Applied texture overlay to {image_path} -> {textured_path}")
        return textured_path

    except Exception as e:
        log.error(f"Failed to apply texture to {image_path}: {e}")
        # Return original image on failure
        return image_path


def get_texture_cache_key(
    svg_path: str, width: int, height: int, texture_config: Optional[Dict] = None
) -> str:
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

    svg_path = Path(svg_path).resolve()

    # Get file modification time for cache invalidation
    try:
        mtime = os.path.getmtime(svg_path)
    except OSError:
        mtime = 0

    # Create cache key from path, dimensions, mtime, and texture config
    key_data = f"{svg_path}:{width}x{height}:{mtime}"

    # Include texture configuration in cache key if available
    if texture_config and texture_config.get("enable", False):
        texture_hash = texture_signature(texture_config)
        key_data += f":texture_{texture_hash}"

    return hashlib.sha1(key_data.encode()).hexdigest()


def check_texture_cache(
    svg_path: str, width: int, height: int, texture_config: Optional[Dict] = None
) -> Optional[str]:
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


def apply_texture_with_qa_loop(
    img: "PIL.Image.Image",
    texture_config: Dict,
    seed: int,
    max_retries: int = 2,
    min_contrast_ratio: float = 4.5,
) -> tuple["PIL.Image.Image", Dict]:
    """
    Apply texture with QA loop that auto-dials back on contrast/legibility failures.

    Args:
        img: Input PIL Image
        texture_config: Texture configuration dictionary
        seed: Random seed for deterministic output
        max_retries: Maximum number of retry attempts
        min_contrast_ratio: Minimum acceptable contrast ratio

    Returns:
        Tuple of (processed_image, metadata_dict)
    """
    from .qa_gates import check_frame_contrast

    original_config = texture_config.copy()
    current_config = texture_config.copy()
    attempts = 0
    qa_results = []

    log.info(
        f"[texture-qa] Starting texture application with QA loop (max retries: {max_retries})"
    )

    while attempts <= max_retries:
        attempts += 1
        log.info(
            f"[texture-qa] Attempt {attempts}: applying textures with config {current_config}"
        )

        try:
            # Apply textures using current configuration
            processed_img = apply_textures_to_frame(img, current_config, seed)

            # Run contrast/legibility check
            contrast_result = check_frame_contrast(processed_img, min_contrast_ratio)
            qa_results.append(
                {
                    "attempt": attempts,
                    "config": current_config.copy(),
                    "contrast_result": contrast_result,
                }
            )

            if contrast_result.ok:
                log.info(f"[texture-qa] QA passed on attempt {attempts}")
                break
            else:
                log.warning(
                    f"[texture-qa] QA failed on attempt {attempts}: {contrast_result.fails}"
                )

                if attempts <= max_retries:
                    # Auto-dial back texture strength
                    current_config = _dial_back_texture_strength(current_config)
                    log.info(
                        f"[texture-qa] Dialing back texture strength for retry: {current_config}"
                    )
                else:
                    log.warning(
                        "[texture-qa] Max retries reached, using last processed image"
                    )

        except Exception as e:
            log.error(
                f"[texture-qa] Texture application failed on attempt {attempts}: {e}"
            )
            qa_results.append(
                {"attempt": attempts, "config": current_config.copy(), "error": str(e)}
            )

            if attempts <= max_retries:
                # Dial back on error too
                current_config = _dial_back_texture_strength(current_config)
            else:
                # Return original image on final failure
                log.error("[texture-qa] All attempts failed, returning original image")
                return img, {
                    "textures": {
                        "applied": False,
                        "attempts": attempts,
                        "final_params": current_config,
                        "qa_results": qa_results,
                        "fallback_reason": "all_attempts_failed",
                    }
                }

    # Prepare metadata
    metadata = {
        "textures": {
            "applied": True,
            "attempts": attempts,
            "final_params": current_config,
            "qa_results": qa_results,
            "original_config": original_config,
            "dialback_applied": attempts > 1,
        }
    }

    log.info(
        f"[texture-qa] Texture application completed successfully after {attempts} attempts"
    )
    return processed_img, metadata


def _dial_back_texture_strength(config: Dict) -> Dict:
    """
    Automatically reduce texture strength for retry.

    Args:
        config: Current texture configuration

    Returns:
        Modified configuration with reduced strength
    """
    dialed_config = config.copy()

    # Reduce grain strength by 30%
    if "grain_strength" in dialed_config:
        current_strength = dialed_config["grain_strength"]
        dialed_config["grain_strength"] = max(0.0, current_strength * 0.7)
        log.info(
            f"[texture-qa] Reduced grain_strength from {current_strength:.3f} to {dialed_config['grain_strength']:.3f}"
        )

    # Increase posterize levels (softer effect)
    if "posterize_levels" in dialed_config:
        current_levels = dialed_config["posterize_levels"]
        dialed_config["posterize_levels"] = min(16, current_levels + 1)
        log.info(
            f"[texture-qa] Increased posterize_levels from {current_levels} to {dialed_config['posterize_levels']}"
        )

    # Disable halftone if enabled
    if "halftone" in dialed_config and dialed_config["halftone"].get("enable", False):
        dialed_config["halftone"]["enable"] = False
        log.info("[texture-qa] Disabled halftone effect")

    # Reduce feather effect
    if "feather_px" in dialed_config:
        current_feather = dialed_config["feather_px"]
        dialed_config["feather_px"] = max(0.5, current_feather * 0.8)
        log.info(
            f"[texture-qa] Reduced feather_px from {current_feather:.1f} to {dialed_config['feather_px']:.1f}"
        )

    return dialed_config


def process_rasterized_with_texture_qa(
    raster_path: str,
    texture_config: Dict,
    brand_palette: Optional[list] = None,
    seed: int = 42,
) -> tuple[str, Dict]:
    """
    Process a rasterized image with texture overlay and QA loop.

    Args:
        raster_path: Path to rasterized image
        texture_config: Texture configuration
        brand_palette: Optional brand color palette
        seed: Random seed for deterministic output

    Returns:
        Tuple of (processed_image_path, metadata_dict)
    """
    if not texture_config.get("enable", False):
        return raster_path, {"textures": {"applied": False, "reason": "disabled"}}

    try:
        from PIL import Image

        # Load image
        img = Image.open(raster_path)

        # Apply texture with QA loop
        processed_img, metadata = apply_texture_with_qa_loop(img, texture_config, seed)

        if metadata["textures"]["applied"]:
            # Save processed image
            base_path = Path(raster_path)
            processed_path = str(
                base_path.parent / f"{base_path.stem}_textured{base_path.suffix}"
            )
            processed_img.save(processed_path)

            log.info(
                f"[texture-integrate] Applied texture overlay to {raster_path} -> {processed_path}"
            )
            return processed_path, metadata
        else:
            log.warning(
                f"[texture-integrate] Texture application failed, using original: {raster_path}"
            )
            return raster_path, metadata

    except Exception as e:
        log.error(f"[texture-integrate] Failed to apply texture to {raster_path}: {e}")
        return raster_path, {
            "textures": {
                "applied": False,
                "error": str(e),
                "fallback_reason": "exception",
            }
        }
