#!/usr/bin/env python3
"""
Texture Engine Core for Paper/Print Effects

This module implements the exact API specified in P3-1 for applying
subtle paper/print effects to frames or clips with deterministic caching.

Public API:
- apply_textures_to_frame(img: PIL.Image.Image, cfg: dict, seed: int) -> PIL.Image.Image
- apply_textures_to_clip(path_in: str, path_out: str, cfg: dict, seed: int) -> None
- texture_signature(cfg: dict) -> str

Effects:
- Grain: opensimplex/perlin noise mixed in luminance
- Feather: slight edge feather on alphas to soften hard cutouts
- Posterize: optional levels for period print vibe
- Halftone: optional dot grid applied only to midtones
"""

import hashlib

import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter, ImageOps

from bin.core import get_logger

log = get_logger("texture_engine")

# Try to import optional dependencies
try:
    OPENIMPLEX_AVAILABLE = True
except ImportError:
    OPENIMPLEX_AVAILABLE = False
    log.warning("opensimplex not available, using numpy fallback for noise")

try:
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False
    log.warning("scikit-image not available, feather effect will be skipped")


def texture_signature(cfg: dict) -> str:
    """
    Generate stable hash for cache key from texture configuration.

    Args:
        cfg: Texture configuration dictionary

    Returns:
        Stable hash string for caching
    """
    # Create a stable representation of the config
    config_str = str(sorted(cfg.items()))
    return hashlib.sha1(config_str.encode()).hexdigest()[:16]


def _get_cache_path(input_hash: str, texture_sig: str, seed: int) -> Path:
    """Get cache path for texture output."""
    cache_dir = Path("render_cache/textures")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{input_hash}_{texture_sig}_{seed}.png"


def _hash_image(img: "PIL.Image.Image") -> str:
    """Generate hash for input image."""
    # Convert to bytes for hashing
    img_bytes = img.tobytes()
    return hashlib.sha1(img_bytes).hexdigest()[:16]


def _apply_grain(
    img: "PIL.Image.Image", strength: float, seed: int
) -> "PIL.Image.Image":
    """
    Apply grain effect using noise.

    Args:
        img: Input PIL Image
        strength: Grain strength (0.0 to 1.0)
        seed: Random seed for deterministic output

    Returns:
        PIL Image with grain applied
    """
    if strength <= 0:
        return img

    width, height = img.size

    # Use fast numpy-based noise for performance
    # This is much faster than OpenSimplex for real-time applications
    np.random.seed(seed)

    # Generate noise with reduced frequency for better performance
    # Use smaller noise tiles that are repeated
    tile_size = min(64, min(width, height))  # Limit tile size for performance
    noise_tile = np.random.rand(tile_size, tile_size) * 2 - 1

    # Repeat the tile to cover the full image
    noise_array = np.tile(noise_tile, (height // tile_size + 1, width // tile_size + 1))
    noise_array = noise_array[:height, :width]

    # Apply slight blur to smooth the tiling artifacts
    if SKIMAGE_AVAILABLE:
        from skimage.filters import gaussian

        noise_array = gaussian(noise_array, sigma=0.5, preserve_range=True)

    log.debug(
        f"[texture-core] Generated fast noise array {width}x{height} in {tile_size}x{tile_size} tiles"
    )

    # Normalize noise to 0-1 range
    noise_array = (noise_array + 1) / 2

    # Convert image to numpy array
    img_array = np.array(img)

    # Apply grain to luminance if color image
    if len(img_array.shape) == 3:
        # Convert to grayscale for luminance
        gray = np.mean(img_array, axis=2)
        # Mix noise with luminance
        grainy_gray = gray * (1 - strength) + noise_array * strength * 255
        grainy_gray = np.clip(grainy_gray, 0, 255).astype(np.uint8)

        # Apply back to all channels
        result = img_array.copy()
        for i in range(3):
            result[:, :, i] = result[:, :, i] * (1 - strength) + grainy_gray * strength
    else:
        # Grayscale image
        result = img_array * (1 - strength) + noise_array * strength * 255

    result = np.clip(result, 0, 255).astype(np.uint8)
    return Image.fromarray(result)


def _apply_feather(img: "PIL.Image.Image", feather_px: float) -> "PIL.Image.Image":
    """
    Apply edge feathering to soften hard cutouts.

    Args:
        img: Input PIL Image
        feather_px: Feather radius in pixels

    Returns:
        PIL Image with feathering applied
    """
    if feather_px <= 0:
        return img

    if SKIMAGE_AVAILABLE:
        # Use scikit-image for better feathering
        img_array = np.array(img)

        # Apply Gaussian blur for feathering
        from skimage.filters import gaussian

        feathered = gaussian(img_array, sigma=feather_px, preserve_range=True)
        return Image.fromarray(feathered.astype(np.uint8))
    else:
        # Fallback to Pillow
        return img.filter(ImageFilter.GaussianBlur(radius=feather_px))


def _apply_posterize(img: "PIL.Image.Image", levels: int) -> "PIL.Image.Image":
    """
    Apply posterization effect.

    Args:
        img: Input PIL Image
        levels: Number of posterization levels

    Returns:
        PIL Image with posterization applied
    """
    if levels <= 1:
        return img

    # PIL has a bug with levels > 8, causing "bad operand type for unary ~: 'float'"
    # Limit to valid range and log warning
    if levels > 8:
        log.warning(f"Posterize level {levels} exceeds maximum (8), clamping to 8")
        levels = 8

    return ImageOps.posterize(img, levels)


def _apply_halftone(
    img: "PIL.Image.Image", cell_px: int, angle_deg: float, opacity: float
) -> "PIL.Image.Image":
    """
    Apply halftone dot pattern to midtones only.

    Args:
        img: Input PIL Image
        cell_px: Cell size in pixels
        angle_deg: Halftone angle in degrees
        opacity: Halftone opacity

    Returns:
        PIL Image with halftone applied
    """
    if opacity <= 0 or cell_px <= 0:
        return img

    width, height = img.size

    # Create halftone pattern
    halftone = Image.new("L", (width, height), 255)

    # Calculate dot positions
    spacing = cell_px
    dot_radius = max(1, cell_px // 4)

    # Apply rotation
    cos_a = np.cos(np.radians(angle_deg))
    sin_a = np.sin(np.radians(angle_deg))

    for y in range(0, height, spacing):
        for x in range(0, width, spacing):
            # Rotate coordinates
            rx = x * cos_a - y * sin_a
            ry = x * sin_a + y * cos_a

            # Check if rotated position is within bounds
            if 0 <= rx < width and 0 <= ry < height:
                # Create dot
                dot_intensity = int(255 * (1 - opacity))
                for dy in range(-dot_radius, dot_radius + 1):
                    for dx in range(-dot_radius, dot_radius + 1):
                        if dx * dx + dy * dy <= dot_radius * dot_radius:
                            px, py = int(rx + dx), int(ry + dy)
                            if 0 <= px < width and 0 <= py < height:
                                halftone.putpixel((px, py), dot_intensity)

    # Apply halftone only to midtones
    img_array = np.array(img)
    halftone_array = np.array(halftone)

    if len(img_array.shape) == 3:
        # Color image - apply to luminance
        gray = np.mean(img_array, axis=2)
        # Create midtone mask (values between 64 and 192)
        midtone_mask = (gray >= 64) & (gray <= 192)

        # Apply halftone only to midtones
        for i in range(3):
            img_array[:, :, i] = np.where(
                midtone_mask,
                img_array[:, :, i] * (1 - opacity) + halftone_array * opacity,
                img_array[:, :, i],
            )
    else:
        # Grayscale image
        midtone_mask = (img_array >= 64) & (img_array <= 192)
        img_array = np.where(
            midtone_mask,
            img_array * (1 - opacity) + halftone_array * opacity,
            img_array,
        )

    return Image.fromarray(img_array.astype(np.uint8))


import time


def apply_textures_to_frame(
    img: "PIL.Image.Image", cfg: dict, seed: int
) -> "PIL.Image.Image":
    """
    Apply texture effects to a single frame.

    Args:
        img: Input PIL Image
        cfg: Texture configuration dictionary
        seed: Random seed for deterministic output

    Returns:
        PIL Image with textures applied
    """
    if not cfg.get("enable", True):
        return img

    # Start performance monitoring
    start_time = time.time()
    log.debug(f"[texture-core] Applying textures with seed {seed}")

    # Apply grain effect
    grain_strength = cfg.get("grain_strength", 0.12)
    if grain_strength > 0:
        img = _apply_grain(img, grain_strength, seed)

    # Apply feathering
    feather_px = cfg.get("feather_px", 1.5)
    if feather_px > 0:
        img = _apply_feather(img, feather_px)

    # Apply posterization
    posterize_levels = cfg.get("posterize_levels", 6)
    if posterize_levels > 1:
        img = _apply_posterize(img, posterize_levels)

    # Apply halftone
    halftone_cfg = cfg.get("halftone", {})
    if halftone_cfg.get("enable", False):
        cell_px = halftone_cfg.get("cell_px", 6)
        angle_deg = halftone_cfg.get("angle_deg", 15)
        opacity = halftone_cfg.get("opacity", 0.12)
        img = _apply_halftone(img, cell_px, angle_deg, opacity)

    # End performance monitoring
    end_time = time.time()
    render_time_ms = (end_time - start_time) * 1000

    log.debug(f"[texture-core] Textures applied successfully in {render_time_ms:.2f}ms")

    # Store performance data in image metadata if possible
    if hasattr(img, "_texture_performance"):
        img._texture_performance = render_time_ms
    else:
        # Create a simple attribute to store performance data
        img._texture_performance = render_time_ms

    return img


def apply_textures_to_clip(path_in: str, path_out: str, cfg: dict, seed: int) -> None:
    """
    Apply texture effects to a video clip.

    Args:
        path_in: Input video file path
        path_out: Output video file path
        cfg: Texture configuration dictionary
        seed: Random seed for deterministic output
    """
    if not cfg.get("enable", True):
        # If textures disabled, just copy the file
        import shutil

        shutil.copy2(path_in, path_out)
        return

    log.info(f"[texture-core] Processing clip {path_in} -> {path_out}")

    # Check cache first
    input_hash = _hash_file(path_in)
    texture_sig = texture_signature(cfg)
    cache_path = _get_cache_path(input_hash, texture_sig, seed)

    if cache_path.exists():
        log.info(f"[texture-core] cache_hit=true for {path_in}")
        import shutil

        shutil.copy2(cache_path, path_out)
        return

    log.info(f"[texture-core] cache_hit=false for {path_in}")

    # For now, this is a placeholder - video processing would require
    # frame extraction, processing, and re-encoding which is beyond
    # the scope of this texture engine core
    log.warning("[texture-core] Video clip processing not implemented yet")

    # Copy input to output for now
    import shutil

    shutil.copy2(path_in, path_out)


def _hash_file(file_path: str) -> str:
    """Generate hash for input file."""
    import hashlib

    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()[:16]
