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
    
    # Extract background color - check multiple possible locations
    bg_color = None
    
    # First check for explicit background color
    if "background" in scene and "color" in scene["background"]:
        bg_color = scene["background"]["color"]
    elif "composition_rules" in scene and "background_color" in scene["composition_rules"]:
        bg_color = scene["composition_rules"]["background_color"]
    elif "bg" in scene and scene["bg"]:
        # Map background identifier to actual color
        bg_id = scene["bg"]
        bg_color = map_background_to_color(bg_id)
        if bg_color:
            warnings.append(f"Mapped background identifier '{bg_id}' to color {bg_color}")
    
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
    
    for element in elements:
        if element.get("type") == "text":
            text_color = element.get("color", "#000000")
            try:
                text_rgb = hex_to_rgb(text_color)
                text_luminance = calculate_luminance(*text_rgb)
                contrast_ratio = calculate_contrast_ratio(bg_luminance, text_luminance)
                
                # WCAG 2.1 AA requires 4.5:1 for normal text, 3:1 for large text
                min_contrast = 4.5
                if element.get("size", "normal") == "large":
                    min_contrast = 3.0
                
                if contrast_ratio < min_contrast:
                    fails.append(f"Text element '{element.get('id', 'unknown')}' has insufficient contrast: {contrast_ratio:.2f}:1 (required: {min_contrast}:1)")
                
                details["contrast_checks"].append({
                    "element_id": element.get("id", "unknown"),
                    "text_color": text_color,
                    "background_color": bg_color,
                    "contrast_ratio": contrast_ratio,
                    "min_required": min_contrast,
                    "passes": contrast_ratio >= min_contrast
                })
                
            except (ValueError, TypeError) as e:
                warnings.append(f"Could not validate contrast for text element '{element.get('id', 'unknown')}': {e}")
    
    return QAResult(
        ok=len(fails) == 0,
        fails=fails,
        warnings=warnings,
        details=details
    )


def check_palette_compliance(asset_plan: Dict[str, Any], manifest: Dict[str, Any]) -> QAResult:
    """
    Check if all assets in the plan are palette compliant.
    
    Args:
        asset_plan: Asset plan with resolved assets
        manifest: Asset library manifest
        
    Returns:
        QAResult with palette validation results
    """
    fails = []
    warnings = []
    details = {
        "palette_checks": [],
        "total_assets": 0,
        "compliant_assets": 0,
        "violations": 0
    }
    
    resolved_assets = asset_plan.get("resolved", [])
    details["total_assets"] = len(resolved_assets)
    
    for asset in resolved_assets:
        asset_hash = asset.get("asset_hash")
        if not asset_hash:
            warnings.append(f"Asset {asset.get('element_id', 'unknown')} missing hash")
            continue
        
        # Look up asset in manifest
        manifest_asset = manifest.get("assets", {}).get(asset_hash)
        if not manifest_asset:
            warnings.append(f"Asset {asset.get('element_id', 'unknown')} not found in manifest")
            continue
        
        # Check palette compliance
        palette_ok = manifest_asset.get("palette_ok", False)
        if palette_ok:
            details["compliant_assets"] += 1
        else:
            details["violations"] += 1
            delta_e_violations = manifest_asset.get("delta_e_violations", [])
            
            if delta_e_violations:
                violation_details = []
                for violation in delta_e_violations:
                    violation_details.append(f"{violation['color']} -> {violation['closest_palette']} (ΔE: {violation['delta_e']:.2f})")
                
                fails.append(f"Asset {asset.get('element_id', 'unknown')} has palette violations: {'; '.join(violation_details)}")
            else:
                fails.append(f"Asset {asset.get('element_id', 'unknown')} has palette violations (no ΔE details)")
        
        details["palette_checks"].append({
            "element_id": asset.get("element_id", "unknown"),
            "asset_path": asset.get("asset", "unknown"),
            "palette_ok": palette_ok,
            "delta_e_violations": manifest_asset.get("delta_e_violations", [])
        })
    
    # Check if generated assets are all compliant
    generated_assets = [a for a in resolved_assets if a.get("reuse_type") == "generated"]
    if generated_assets:
        generated_compliant = all(
            manifest.get("assets", {}).get(a.get("asset_hash", ""), {}).get("palette_ok", False)
            for a in generated_assets
        )
        
        if not generated_compliant:
            fails.append("Generated assets must be 100% palette compliant")
        else:
            details["generated_assets_compliant"] = True
    
    return QAResult(
        ok=len(fails) == 0,
        fails=fails,
        warnings=warnings,
        details=details
    )


def check_asset_coverage(asset_plan: Dict[str, Any]) -> QAResult:
    """
    Check if asset plan has sufficient coverage (no gaps).
    
    Args:
        asset_plan: Asset plan to validate
        
    Returns:
        QAResult with coverage validation results
    """
    fails = []
    warnings = []
    details = {
        "coverage_stats": {},
        "gap_details": []
    }
    
    total_placeholders = asset_plan.get("total_placeholders", 0)
    resolved_count = asset_plan.get("resolved_count", 0)
    gaps_count = asset_plan.get("gaps_count", 0)
    reuse_ratio = asset_plan.get("reuse_ratio", 0.0)
    
    details["coverage_stats"] = {
        "total_placeholders": total_placeholders,
        "resolved_count": resolved_count,
        "gaps_count": gaps_count,
        "reuse_ratio": reuse_ratio
    }
    
    # Check for gaps
    if gaps_count > 0:
        fails.append(f"Asset plan has {gaps_count} unresolved gaps")
        
        gaps = asset_plan.get("gaps", [])
        for gap in gaps:
            details["gap_details"].append({
                "element_id": gap.get("element_id", "unknown"),
                "category": gap.get("spec", {}).get("category", "unknown"),
                "style": gap.get("spec", {}).get("style", "unknown")
            })
    
    # Check reuse ratio
    if reuse_ratio < 0.7:  # Expect at least 70% reuse
        warnings.append(f"Low reuse ratio: {reuse_ratio:.2%} (expected: ≥70%)")
    
    # Check if all placeholders are resolved
    if resolved_count != total_placeholders:
        fails.append(f"Asset resolution incomplete: {resolved_count}/{total_placeholders} resolved")
    
    return QAResult(
        ok=len(fails) == 0,
        fails=fails,
        warnings=warnings,
        details=details
    )


def check_asset_quality(asset_plan: Dict[str, Any], manifest: Dict[str, Any]) -> QAResult:
    """
    Comprehensive asset quality check combining all asset-related validations.
    
    Args:
        asset_plan: Asset plan to validate
        manifest: Asset library manifest
        
    Returns:
        QAResult with comprehensive asset quality results
    """
    # Run individual checks
    palette_result = check_palette_compliance(asset_plan, manifest)
    coverage_result = check_asset_coverage(asset_plan)
    
    # Combine results
    all_fails = palette_result.fails + coverage_result.fails
    all_warnings = palette_result.warnings + coverage_result.warnings
    
    # Combine details
    combined_details = {
        "palette_validation": palette_result.details,
        "coverage_validation": coverage_result.details,
        "overall_summary": {
            "total_assets": coverage_result.details.get("coverage_stats", {}).get("total_placeholders", 0),
            "resolved_assets": coverage_result.details.get("coverage_stats", {}).get("resolved_count", 0),
            "palette_compliant": palette_result.details.get("compliant_assets", 0),
            "palette_violations": palette_result.details.get("violations", 0),
            "gaps": coverage_result.details.get("coverage_stats", {}).get("gaps_count", 0),
            "reuse_ratio": coverage_result.details.get("coverage_stats", {}).get("reuse_ratio", 0.0)
        }
    }
    
    return QAResult(
        ok=len(all_fails) == 0,
        fails=all_fails,
        warnings=all_warnings,
        details=combined_details
    )


def check_frame_contrast(img: "PIL.Image.Image", min_contrast_ratio: float = 4.5) -> QAResult:
    """
    Check contrast and legibility of a single image frame.
    
    Args:
        img: PIL Image to check
        min_contrast_ratio: Minimum acceptable contrast ratio (WCAG AA = 4.5)
        
    Returns:
        QAResult with contrast validation results
    """
    fails = []
    warnings = []
    details = {"contrast_checks": [], "overall_contrast": 0.0}
    
    try:
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Get image dimensions
        width, height = img.size
        
        # Sample points across the image for contrast analysis
        sample_points = []
        step = max(1, min(width, height) // 20)  # Sample every 20th pixel
        
        for y in range(0, height, step):
            for x in range(0, width, step):
                sample_points.append((x, y))
        
        # Limit samples to reasonable number
        if len(sample_points) > 100:
            sample_points = sample_points[::len(sample_points)//100]
        
        # Analyze contrast between adjacent samples
        contrast_ratios = []
        for i in range(len(sample_points) - 1):
            x1, y1 = sample_points[i]
            x2, y2 = sample_points[i + 1]
            
            # Get colors at sample points
            color1 = img.getpixel((x1, y1))
            color2 = img.getpixel((x2, y2))
            
            # Calculate luminance for each color
            lum1 = calculate_luminance(*color1)
            lum2 = calculate_luminance(*color2)
            
            # Calculate contrast ratio
            contrast = calculate_contrast_ratio(lum1, lum2)
            contrast_ratios.append(contrast)
        
        if contrast_ratios:
            # Calculate overall contrast metrics
            avg_contrast = sum(contrast_ratios) / len(contrast_ratios)
            min_contrast = min(contrast_ratios)
            max_contrast = max(contrast_ratios)
            
            details["overall_contrast"] = avg_contrast
            details["min_contrast"] = min_contrast
            details["max_contrast"] = max_contrast
            details["sample_count"] = len(contrast_ratios)
            
            # Check if minimum contrast is met
            if min_contrast < min_contrast_ratio:
                fails.append(f"Minimum contrast ratio {min_contrast:.2f} below threshold {min_contrast_ratio}")
            
            # Warn if average contrast is low
            if avg_contrast < min_contrast_ratio * 1.5:
                warnings.append(f"Average contrast ratio {avg_contrast:.2f} is close to threshold")
            
            # Log contrast distribution
            details["contrast_checks"].append({
                "avg_contrast": avg_contrast,
                "min_contrast": min_contrast,
                "max_contrast": max_contrast,
                "threshold": min_contrast_ratio
            })
        else:
            fails.append("Unable to sample image for contrast analysis")
            
    except Exception as e:
        fails.append(f"Contrast analysis failed: {e}")
    
    return QAResult(
        ok=len(fails) == 0,
        fails=fails,
        warnings=warnings,
        details=details
    )


def map_background_to_color(bg_id: str) -> Optional[str]:
    """Map background identifier to actual color value."""
    # This is a simplified mapping - in practice, you'd load from design system
    bg_color_map = {
        "gradient1": "#1C4FA1",
        "paper": "#F8F1E5",
        "starburst": "#F6BE00",
        "boomerang": "#F28C28",
        "atomic": "#1C4FA1"
    }
    return bg_color_map.get(bg_id)


def check_scene_composition(scene: Dict[str, Any]) -> QAResult:
    """
    Check scene composition rules and constraints.
    
    Args:
        scene: Scene dictionary to validate
        
    Returns:
        QAResult with composition validation results
    """
    fails = []
    warnings = []
    details = {"composition_checks": []}
    
    # Check safe margins
    elements = scene.get("elements", [])
    for element in elements:
        x = element.get("x", 0)
        y = element.get("y", 0)
        w = element.get("w", 0)
        h = element.get("h", 0)
        
        # Check if element is within safe margins
        if x < SAFE_MARGINS_PX or y < SAFE_MARGINS_PX:
            warnings.append(f"Element '{element.get('id', 'unknown')}' may be too close to edge")
        
        if x + w > VIDEO_W - SAFE_MARGINS_PX or y + h > VIDEO_H - SAFE_MARGINS_PX:
            warnings.append(f"Element '{element.get('id', 'unknown')}' may extend beyond safe area")
    
    # Check color limits
    colors_used = set()
    for element in elements:
        if "color" in element:
            colors_used.add(element["color"])
    
    if len(colors_used) > 3:
        warnings.append(f"Scene uses {len(colors_used)} colors (recommended: ≤3)")
    
    details["composition_checks"] = {
        "elements_count": len(elements),
        "colors_used": list(colors_used),
        "safe_margin_violations": len([w for w in warnings if "edge" in w or "safe area" in w])
    }
    
    return QAResult(
        ok=len(fails) == 0,
        fails=fails,
        warnings=warnings,
        details=details
    )


def run_qa_suite(scene: Dict[str, Any], asset_plan: Optional[Dict[str, Any]] = None, manifest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run complete QA suite on scene and optional asset plan.
    
    Args:
        scene: Scene to validate
        asset_plan: Optional asset plan for asset validation
        manifest: Optional asset manifest for palette validation
        
    Returns:
        Dict with all QA results
    """
    results = {
        "timestamp": None,
        "overall_status": "PENDING",
        "checks": {},
        "summary": {
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": 0,
            "warnings": 0
        }
    }
    
    # Run basic scene checks
    contrast_result = check_contrast(scene)
    composition_result = check_scene_composition(scene)
    
    results["checks"]["contrast"] = {
        "ok": contrast_result.ok,
        "fails": contrast_result.fails,
        "warnings": contrast_result.warnings,
        "details": contrast_result.details
    }
    
    results["checks"]["composition"] = {
        "ok": composition_result.ok,
        "fails": composition_result.fails,
        "warnings": composition_result.warnings,
        "details": composition_result.details
    }
    
    # Run asset checks if available
    if asset_plan and manifest:
        asset_result = check_asset_quality(asset_plan, manifest)
        results["checks"]["assets"] = {
            "ok": asset_result.ok,
            "fails": asset_result.fails,
            "warnings": asset_result.warnings,
            "details": asset_result.details
        }
    
    # Calculate summary
    total_checks = len(results["checks"])
    passed_checks = sum(1 for check in results["checks"].values() if check["ok"])
    failed_checks = total_checks - passed_checks
    total_warnings = sum(len(check["warnings"]) for check in results["checks"].values())
    
    results["summary"] = {
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "warnings": total_warnings
    }
    
    # Determine overall status
    if failed_checks == 0:
        results["overall_status"] = "PASS"
    else:
        results["overall_status"] = "FAIL"
    
    return results


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
