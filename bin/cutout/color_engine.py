#!/usr/bin/env python3
"""
Color Engine for Procedural Animatics Toolkit

Provides centralized palette operations, WCAG contrast validation, and scene color policy
enforcement to ensure every scene is legible and on-brand.
"""

import json
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bin.core import load_config

log = logging.getLogger(__name__)

# WCAG AA contrast ratio requirements
WCAG_AA_NORMAL = 4.5  # Normal text (18pt+ or 14pt+ bold)
WCAG_AA_LARGE = 3.0   # Large text (18pt+ or 14pt+ bold)

# Color conversion cache for performance
_color_cache: Dict[str, Tuple[float, float, float]] = {}


def load_palette() -> Dict[str, str]:
    """
    Load the brand color palette from design_language.json.
    
    Returns:
        Dictionary mapping color names to hex values
        
    Raises:
        FileNotFoundError: If design_language.json is missing
        KeyError: If colors section is missing
    """
    design_path = Path("design/design_language.json")
    if not design_path.exists():
        raise FileNotFoundError(f"Design language file not found: {design_path}")
    
    with open(design_path, 'r') as f:
        design_data = json.load(f)
    
    if 'colors' not in design_data:
        raise KeyError("No 'colors' section found in design_language.json")
    
    palette = design_data['colors']
    log.info(f"Loaded {len(palette)} colors from design palette")
    return palette


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB tuple to hex color."""
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_hsl(hex_color: str) -> Tuple[float, float, float]:
    """Convert hex color to HSL tuple (0-1 range)."""
    if hex_color in _color_cache:
        return _color_cache[hex_color]
    
    r, g, b = hex_to_rgb(hex_color)
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    delta = max_val - min_val
    
    # Lightness
    l = (max_val + min_val) / 2.0
    
    if delta == 0:
        h = s = 0
    else:
        # Saturation
        s = delta / (2.0 - max_val - min_val) if l > 0.5 else delta / (max_val + min_val)
        
        # Hue
        if max_val == r:
            h = (g - b) / delta + (6 if g < b else 0)
        elif max_val == g:
            h = (b - r) / delta + 2
        else:
            h = (r - g) / delta + 4
        h /= 6.0
    
    result = (h, s, l)
    _color_cache[hex_color] = result
    return result


def hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL tuple (0-1 range) to hex color."""
    def hue_to_rgb(m1: float, m2: float, h: float) -> float:
        h = h % 1.0
        if h < 1/6:
            return m1 + (m2 - m1) * 6 * h
        elif h < 1/2:
            return m2
        elif h < 2/3:
            return m1 + (m2 - m1) * 6 * (2/3 - h)
        else:
            return m1
    
    if s == 0:
        r = g = b = l
    else:
        m2 = l + s * (0.5 - l) if l <= 0.5 else l + s - l * s
        m1 = 2 * l - m2
        r = hue_to_rgb(m1, m2, h + 1/3)
        g = hue_to_rgb(m1, m2, h)
        b = hue_to_rgb(m1, m2, h - 1/3)
    
    # Clamp RGB values to valid range and convert to hex
    r_clamped = max(0, min(255, int(r * 255)))
    g_clamped = max(0, min(255, int(g * 255)))
    b_clamped = max(0, min(255, int(b * 255)))
    
    return rgb_to_hex(r_clamped, g_clamped, b_clamped)


def calculate_luminance(hex_color: str) -> float:
    """
    Calculate relative luminance for contrast ratio calculation.
    
    Uses the WCAG 2.1 formula for relative luminance.
    """
    r, g, b = hex_to_rgb(hex_color)
    
    def gamma_correct(c: int) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * gamma_correct(r) + 0.7152 * gamma_correct(g) + 0.0722 * gamma_correct(b)


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """
    Calculate contrast ratio between foreground and background colors.
    
    Args:
        fg_hex: Foreground color in hex format
        bg_hex: Background color in hex format
        
    Returns:
        Contrast ratio (1.0 to 21.0, higher is better)
    """
    l1 = calculate_luminance(fg_hex)
    l2 = calculate_luminance(bg_hex)
    
    lighter = max(l1, l2)
    darker = min(l1, l2)
    
    return (lighter + 0.05) / (darker + 0.05)


def assert_legible_text(text_color: str, bg_color: str, large_text: bool = False) -> None:
    """
    Assert that text color provides sufficient contrast against background.
    
    Args:
        text_color: Text color in hex format
        bg_color: Background color in hex format
        large_text: If True, uses WCAG AA large text standard (3.0:1)
        
    Raises:
        ValueError: If contrast ratio is insufficient for legibility
    """
    ratio = contrast_ratio(text_color, bg_color)
    required = WCAG_AA_LARGE if large_text else WCAG_AA_NORMAL
    
    if ratio < required:
        raise ValueError(
            f"Insufficient contrast: {ratio:.2f}:1 (need {required}:1) "
            f"for text {text_color} on background {bg_color}"
        )


def tint(hex_color: str, amount: float) -> str:
    """
    Create a tint (lighter version) of a color.
    
    Args:
        hex_color: Base color in hex format
        amount: Tint amount (-0.3 to +0.3, positive = lighter)
        
    Returns:
        Tinted color in hex format
    """
    if not -0.3 <= amount <= 0.3:
        raise ValueError("Tint amount must be between -0.3 and +0.3")
    
    h, s, l = hex_to_hsl(hex_color)
    new_l = min(1.0, max(0.0, l + amount))
    return hsl_to_hex(h, s, new_l)


def shade(hex_color: str, amount: float) -> str:
    """
    Create a shade (darker version) of a color.
    
    Args:
        hex_color: Base color in hex format
        amount: Shade amount (-0.3 to +0.3, positive = darker)
        
    Returns:
        Shaded color in hex format
    """
    return tint(hex_color, -amount)


def pick_scene_colors(seed: Optional[int] = None, k: int = 3) -> List[str]:
    """
    Pick k colors from the brand palette for a scene.
    
    Args:
        seed: Random seed for deterministic selection (None = random)
        k: Number of colors to select
        
    Returns:
        List of hex color values
        
    Raises:
        ValueError: If k exceeds available palette size
    """
    palette = load_palette()
    if k > len(palette):
        raise ValueError(f"Requested {k} colors but palette only has {len(palette)}")
    
    if seed is not None:
        random.seed(seed)
    
    # Convert to list and shuffle
    color_list = list(palette.values())
    random.shuffle(color_list)
    
    selected = color_list[:k]
    log.info(f"Selected {len(selected)} colors for scene (seed: {seed})")
    return selected


def enforce_scene_palette(used_hexes: List[str], max_k: int) -> List[str]:
    """
    Enforce scene palette limits by trimming to max_k colors.
    
    Priority order: background colors first, then text colors, then accents.
    
    Args:
        used_hexes: List of hex colors currently used in scene
        max_k: Maximum number of colors allowed
        
    Returns:
        Trimmed list of hex colors respecting the limit
    """
    if len(used_hexes) <= max_k:
        return used_hexes
    
    # Simple heuristic: assume first color is background, second is text
    # This could be enhanced with more sophisticated analysis
    if len(used_hexes) >= 2:
        # Keep background and text colors
        result = used_hexes[:2]
        # Add remaining colors up to limit
        result.extend(used_hexes[2:max_k])
    else:
        # Just trim to limit
        result = used_hexes[:max_k]
    
    log.info(f"Enforced palette limit: {len(used_hexes)} -> {len(result)} colors")
    return result


def get_scene_color_policy() -> Dict[str, int]:
    """
    Get the current scene color policy from configuration.
    
    Returns:
        Dictionary with color policy settings
    """
    try:
        config = load_config()
        return {
            'max_colors_per_scene': config.procedural.max_colors_per_scene
        }
    except Exception as e:
        log.warning(f"Could not load color policy config: {e}, using defaults")
        return {'max_colors_per_scene': 3}


def validate_scene_colors(scene_colors: List[str], scene_name: str = "unknown") -> bool:
    """
    Validate that a scene's color palette meets all requirements.
    
    Args:
        scene_colors: List of hex colors used in the scene
        scene_name: Name of the scene for logging
        
    Returns:
        True if scene colors are valid, False otherwise
    """
    policy = get_scene_color_policy()
    max_colors = policy['max_colors_per_scene']
    
    if len(scene_colors) > max_colors:
        log.error(f"Scene '{scene_name}' uses {len(scene_colors)} colors, max allowed: {max_colors}")
        return False
    
    # Check for duplicate colors
    if len(scene_colors) != len(set(scene_colors)):
        log.error(f"Scene '{scene_name}' has duplicate colors")
        return False
    
    # Validate hex format
    for color in scene_colors:
        if not color.startswith('#') or len(color) != 7:
            log.error(f"Scene '{scene_name}' has invalid hex color: {color}")
            return False
    
    log.info(f"Scene '{scene_name}' color palette validated successfully")
    return True
