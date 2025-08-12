#!/usr/bin/env python3
"""
QA Gates for Procedural Animatics Toolkit

Pre-render quality checks that catch bad scenes before CPU-intensive rendering.
All functions are side-effect free and return structured results.
"""

import colorsys
import json
import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

from .sdk import VIDEO_W, VIDEO_H, SAFE_MARGINS_PX


@dataclass
class QAResult:
    """Structured result from QA checks"""
    ok: bool
    fails: List[str]
    warnings: List[str]
    details: Dict[str, Any]


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c + c for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def calculate_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance using WCAG 2.1 formula."""
    # Convert sRGB to linear RGB
    def to_linear(c):
        c = c / 255.0
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4
    
    r_lin = to_linear(r)
    g_lin = to_linear(g)
    b_lin = to_linear(b)
    
    # Calculate relative luminance
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(lum1: float, lum2: float) -> float:
    """Calculate contrast ratio between two luminances."""
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def check_contrast(scene: Dict[str, Any]) -> QAResult:
    """
    Check text contrast ratios against WCAG 2.1 AA standards.
    
    Args:
        scene: Scene dictionary with elements
        
    Returns:
        QAResult with contrast validation results
    """
    fails = []
    warnings = []
    details = {"contrast_checks": []}
    
    # Extract background color
    bg_color = None
    if "background" in scene and "color" in scene["background"]:
        bg_color = scene["background"]["color"]
    elif "composition_rules" in scene and "background_color" in scene["composition_rules"]:
        bg_color = scene["composition_rules"]["background_color"]
    
    if not bg_color:
        fails.append("No background color specified for contrast checking")
        return QAResult(ok=False, fails=fails, warnings=warnings, details=details)
    
    try:
        bg_rgb = hex_to_rgb(bg_color)
        bg_luminance = calculate_luminance(*bg_rgb)
    except (ValueError, TypeError):
        fails.append(f"Invalid background color format: {bg_color}")
        return QAResult(ok=False, fails=fails, warnings=warnings, details=details)
    
    # Check text elements
    elements = scene.get("elements", [])
    text_elements = [e for e in elements if e.get("type") == "text" and "color" in e]
    
    if not text_elements:
        warnings.append("No text elements found for contrast checking")
        return QAResult(ok=True, fails=fails, warnings=warnings, details=details)
    
    for element in text_elements:
        text_color = element["color"]
        if not text_color:
            continue
            
        try:
            text_rgb = hex_to_rgb(text_color)
            text_luminance = calculate_luminance(*text_rgb)
            contrast_ratio = calculate_contrast_ratio(bg_luminance, text_luminance)
            
            check_result = {
                "element_id": element.get("id", "unknown"),
                "text_color": text_color,
                "background_color": bg_color,
                "contrast_ratio": round(contrast_ratio, 2),
                "wcag_aa_pass": contrast_ratio >= 4.5
            }
            
            details["contrast_checks"].append(check_result)
            
            if contrast_ratio < 4.5:
                fails.append(
                    f"Element '{element.get('id', 'unknown')}' has insufficient contrast: "
                    f"{contrast_ratio:.2f}:1 (need ≥4.5:1)"
                )
                
        except (ValueError, TypeError):
            fails.append(f"Invalid text color format in element '{element.get('id', 'unknown')}': {text_color}")
    
    return QAResult(
        ok=len(fails) == 0,
        fails=fails,
        warnings=warnings,
        details=details
    )


def check_collisions(bboxes: List[Tuple[int, int, int, int]]) -> QAResult:
    """
    Check for overlapping bounding boxes and calculate distances.
    
    Args:
        bboxes: List of (x1, y1, x2, y2) bounding boxes
        
    Returns:
        QAResult with collision detection results
    """
    fails = []
    warnings = []
    details = {"collisions": [], "distances": []}
    
    if len(bboxes) < 2:
        return QAResult(ok=True, fails=fails, warnings=warnings, details=details)
    
    # Check for overlaps
    for i, (x1, y1, x2, y2) in enumerate(bboxes):
        for j, (x3, y3, x4, y4) in enumerate(bboxes[i+1:], i+1):
            # Check for overlap
            if not (x2 < x3 or x4 < x1 or y2 < y3 or y4 < y1):
                collision = {
                    "box1_index": i,
                    "box2_index": j,
                    "box1": (x1, y1, x2, y2),
                    "box2": (x3, y3, x4, y4),
                    "overlap_area": (min(x2, x4) - max(x1, x3)) * (min(y2, y4) - max(y1, y3))
                }
                details["collisions"].append(collision)
                fails.append(
                    f"Bounding boxes {i} and {j} overlap with area {collision['overlap_area']} pixels"
                )
    
    # Calculate distances between non-overlapping boxes
    for i, (x1, y1, x2, y2) in enumerate(bboxes):
        for j, (x3, y3, x4, y4) in enumerate(bboxes[i+1:], i+1):
            # Skip if boxes overlap
            if any(c["box1_index"] == i and c["box2_index"] == j for c in details["collisions"]):
                continue
                
            # Calculate center points
            center1 = ((x1 + x2) / 2, (y1 + y2) / 2)
            center2 = ((x3 + x4) / 2, (y3 + y4) / 2)
            
            # Calculate distance
            distance = ((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2) ** 0.5
            
            details["distances"].append({
                "box1_index": i,
                "box2_index": j,
                "distance": round(distance, 2)
            })
            
            # Warn if boxes are very close
            if distance < 20:
                warnings.append(f"Bounding boxes {i} and {j} are very close: {distance:.1f} pixels")
    
    return QAResult(
        ok=len(fails) == 0,
        fails=fails,
        warnings=warnings,
        details=details
    )


def check_palette(used_hexes: List[str], max_k: int) -> QAResult:
    """
    Check palette usage against maximum color limit.
    
    Args:
        used_hexes: List of hex color codes
        max_k: Maximum number of colors allowed
        
    Returns:
        QAResult with palette validation results
    """
    fails = []
    warnings = []
    details = {"palette_analysis": {}}
    
    # Validate hex colors
    valid_hexes = []
    invalid_colors = []
    
    for color in used_hexes:
        if re.match(r'^#[0-9A-Fa-f]{6}$', color) or re.match(r'^#[0-9A-Fa-f]{3}$', color):
            valid_hexes.append(color)
        else:
            invalid_colors.append(color)
    
    if invalid_colors:
        fails.append(f"Invalid hex color formats: {', '.join(invalid_colors)}")
    
    # Count unique colors
    unique_colors = list(set(valid_hexes))
    color_count = len(unique_colors)
    
    details["palette_analysis"] = {
        "total_colors": len(used_hexes),
        "unique_colors": color_count,
        "max_allowed": max_k,
        "colors_used": unique_colors,
        "invalid_colors": invalid_colors
    }
    
    if color_count > max_k:
        fails.append(f"Too many colors: {color_count} used, maximum {max_k} allowed")
    
    if color_count == 1:
        warnings.append("Only one color used - consider adding variety")
    
    if color_count == max_k:
        warnings.append(f"Using maximum allowed colors ({max_k}) - consider reducing for consistency")
    
    return QAResult(
        ok=len(fails) == 0,
        fails=fails,
        warnings=warnings,
        details=details
    )


def check_rhythm(scenes_meta: List[Dict[str, Any]]) -> QAResult:
    """Check scene rhythm and timing consistency."""
    fails = []
    warnings = []
    details = {}
    
    if not scenes_meta:
        return QAResult(ok=True, fails=fails, warnings=warnings, details=details)
    
    # Load timing configuration for duration limits
    try:
        from bin.core import load_modules_cfg
        timing_config = load_modules_cfg().get('timing', {})
        min_scene_sec = timing_config.get('min_scene_ms', 2500) / 1000
        max_scene_sec = timing_config.get('max_scene_ms', 30000) / 1000
        # Use configurable thresholds for warnings
        avg_duration_warning_threshold = timing_config.get('avg_duration_warning_threshold', max_scene_sec * 0.6)
        max_duration_warning_threshold = timing_config.get('max_duration_warning_threshold', max_scene_sec * 0.8)
    except Exception:
        # Fallback to reasonable defaults
        min_scene_sec = 2.5
        max_scene_sec = 30.0
        avg_duration_warning_threshold = 18.0
        max_duration_warning_threshold = 24.0
    
    # Extract durations and transitions
    durations = []
    transitions = []
    
    for scene in scenes_meta:
        duration = scene.get("duration_ms", 0) / 1000
        durations.append(duration)
        
        # Check for transitions (simplified - could be enhanced)
        if duration > 0:
            transitions.append(duration)
    
    if not durations:
        return QAResult(ok=True, fails=fails, warnings=warnings, details=details)
    
    avg_duration = sum(durations) / len(durations)
    min_duration = min(durations)
    max_duration = max(durations)
    total_duration = sum(durations)
    
    # Check duration constraints using configurable limits
    if avg_duration < min_scene_sec:
        fails.append(f"Average scene duration too short: {avg_duration:.1f}s (need ≥{min_scene_sec:.1f}s)")
    elif avg_duration > avg_duration_warning_threshold:
        warnings.append(f"Average scene duration long: {avg_duration:.1f}s (consider ≤{avg_duration_warning_threshold:.1f}s)")
    
    if min_duration < min_scene_sec:
        fails.append(f"Scene duration too short: {min_duration:.1f}s (need ≥{min_scene_sec:.1f}s)")
    
    if max_duration > max_duration_warning_threshold:
        warnings.append(f"Scene duration very long: {max_duration:.1f}s (consider ≤{max_duration_warning_threshold:.1f}s)")
    
    # Check transition density
    transition_density = len(transitions) / total_duration if total_duration > 0 else 0
    max_transition_rate = 1.0 / 6.0  # 1 transition per 6 seconds
    
    if transition_density > max_transition_rate:
        fails.append(
            f"Transition density too high: {transition_density:.2f}/s "
            f"(need ≤{max_transition_rate:.2f}/s)"
        )
    
    details["rhythm_analysis"] = {
        "total_scenes": len(scenes_meta),
        "total_duration_sec": round(total_duration, 2),
        "average_duration_sec": round(avg_duration, 2),
        "min_duration_sec": round(min_duration, 2),
        "max_duration_sec": round(max_duration, 2),
        "transitions_count": len(transitions),
        "transition_density_per_sec": round(transition_density, 3),
        "max_transition_rate": max_transition_rate,
        "timing_config": {
            "min_scene_sec": min_scene_sec,
            "max_scene_sec": max_scene_sec,
            "avg_warning_threshold": avg_duration_warning_threshold,
            "max_warning_threshold": max_duration_warning_threshold
        }
    }
    
    return QAResult(
        ok=len(fails) == 0,
        fails=fails,
        warnings=warnings,
        details=details
    )


def run_all(scene: Dict[str, Any], scenes_meta: List[Dict[str, Any]], palette: List[str]) -> QAResult:
    """
    Run all QA checks on a scene.
    
    Args:
        scene: Scene dictionary to validate
        scenes_meta: List of scene metadata for rhythm analysis
        palette: List of hex colors for palette validation
        
    Returns:
        QAResult with comprehensive validation results
    """
    all_fails = []
    all_warnings = []
    all_details = {}
    
    # Run contrast check
    contrast_result = check_contrast(scene)
    all_fails.extend(contrast_result.fails)
    all_warnings.extend(contrast_result.warnings)
    all_details["contrast"] = contrast_result.details
    
    # Run collision check (extract bounding boxes from scene)
    bboxes = extract_bounding_boxes(scene)
    collision_result = check_collisions(bboxes)
    all_fails.extend(collision_result.fails)
    all_warnings.extend(collision_result.warnings)
    all_details["collisions"] = collision_result.details
    
    # Run palette check
    max_colors = scene.get("composition_rules", {}).get("max_colors", 3)
    palette_result = check_palette(palette, max_colors)
    all_fails.extend(palette_result.fails)
    all_warnings.extend(palette_result.warnings)
    all_details["palette"] = palette_result.details
    
    # Run rhythm check
    rhythm_result = check_rhythm(scenes_meta)
    all_fails.extend(rhythm_result.fails)
    all_warnings.extend(rhythm_result.warnings)
    all_details["rhythm"] = rhythm_result.details
    
    # Overall result
    overall_ok = len(all_fails) == 0
    
    return QAResult(
        ok=overall_ok,
        fails=all_fails,
        warnings=all_warnings,
        details=all_details
    )


def extract_bounding_boxes(scene: Dict[str, Any]) -> List[Tuple[int, int, int, int]]:
    """Extract bounding boxes from scene elements for collision detection."""
    bboxes = []
    
    for element in scene.get("elements", []):
        if "position" in element:
            x = element["position"]["x"]
            y = element["position"]["y"]
            
            # Estimate width and height based on element type
            width = 100  # Default width
            height = 100  # Default height
            
            if element.get("type") == "text":
                # Estimate text dimensions
                content = element.get("content", "")
                font_size = element.get("font_size", 24)
                width = len(content) * font_size * 0.6  # Rough estimate
                height = font_size * 1.2
            
            elif "scale" in element:
                # Scale the default dimensions
                scale = element["scale"]
                width *= scale
                height *= scale
            
            # Create bounding box (x1, y1, x2, y2)
            bbox = (int(x), int(y), int(x + width), int(y + height))
            bboxes.append(bbox)
    
    return bboxes


def qa_result_to_dict(result: QAResult) -> Dict[str, Any]:
    """Convert QAResult to JSON-serializable dictionary."""
    return {
        "ok": result.ok,
        "fails": result.fails,
        "warnings": result.warnings,
        "details": result.details
    }


# Convenience function for JSON serialization
def qa_result_to_json(result: QAResult) -> str:
    """Convert QAResult to JSON string."""
    return json.dumps(qa_result_to_dict(result), indent=2)
