#!/usr/bin/env python3
"""
Pacing Comparison Module

Compares pacing KPIs against intent-specific bands and returns flags for:
- Individual metric status (ok/fast/slow)
- Overall pacing status
- Acceptance criteria

Integrates with pacing_kpi.py to provide complete pacing analysis.
"""

import json
import logging
import os
import yaml
from typing import Dict, List, Optional, Tuple

try:
    from .core import get_logger, load_config, load_modules_cfg, load_brief
except ImportError:
    # Handle direct execution
    import sys
    sys.path.append(os.path.dirname(__file__))
    from core import get_logger, load_config, load_modules_cfg, load_brief

log = get_logger("pacing-compare")


def load_intent_profiles() -> Dict:
    """
    Load intent-specific pacing profiles from configuration.
    
    Returns:
        Dictionary of intent profiles with metric bands
    """
    config_dir = os.path.join(os.path.dirname(__file__), '..', 'conf')
    profiles_path = os.path.join(config_dir, 'intent_profiles.yaml')
    
    if not os.path.exists(profiles_path):
        log.error(f"Intent profiles not found: {profiles_path}")
        return {}
    
    try:
        with open(profiles_path, 'r') as f:
            profiles = yaml.safe_load(f)
        log.info(f"Loaded {len(profiles)} intent profiles")
        return profiles
    except Exception as e:
        log.error(f"Error loading intent profiles: {e}")
        return {}


def get_current_intent() -> str:
    """
    Get the current intent from brief configuration.
    
    Returns:
        Intent string (e.g., 'narrative_history')
    """
    try:
        # Try direct import first
        from bin.brief_loader import load_brief as _load_brief
        brief_cfg = _load_brief()
        intent = brief_cfg.get('intent', 'default')
        log.info(f"Current intent: {intent}")
        return intent
    except ImportError:
        # Fallback to core module
        try:
            brief_cfg = load_brief()
            intent = brief_cfg.get('intent', 'default')
            log.info(f"Current intent: {intent}")
            return intent
        except Exception as e:
            log.warning(f"Could not load brief config, using default intent: {e}")
            return 'default'


def compare_to_profile(kpi_data: Dict, profile: Dict) -> Dict:
    """
    Compare KPI metrics against intent profile bands.
    
    Args:
        kpi_data: Dictionary with pacing metrics
        profile: Intent profile with metric bands
        
    Returns:
        Dictionary with comparison results and flags
    """
    log.info("Comparing KPIs to intent profile")
    
    # Extract metrics from KPI data
    words_per_sec = kpi_data.get('words_per_sec', 0.0)
    cuts_per_min = kpi_data.get('cuts_per_min', 0.0)
    avg_scene_s = kpi_data.get('avg_scene_s', 0.0)
    speech_music_ratio = kpi_data.get('speech_music_ratio', 0.0)
    
    # Extract bands from profile
    wps_band = profile.get('words_per_sec', [2.0, 3.5])
    cpm_band = profile.get('cuts_per_min', [8, 25])
    scene_band = profile.get('avg_scene_s', [4.0, 8.0])
    
    # Compare each metric to its band
    wps_status = _compare_metric(words_per_sec, wps_band, 'words_per_sec')
    cpm_status = _compare_metric(cuts_per_min, cpm_band, 'cuts_per_min')
    scene_status = _compare_metric(avg_scene_s, scene_band, 'avg_scene_s')
    
    # Determine overall status
    statuses = [wps_status, cpm_status, scene_status]
    overall_status = _determine_overall_status(statuses)
    
    # Compile comparison result
    comparison = {
        "flags": {
            "words_per_sec": wps_status,
            "cuts_per_min": cpm_status,
            "avg_scene_s": scene_status,
            "speech_music_ratio": "ok"  # Not currently banded
        },
        "overall_status": overall_status,
        "profile_used": profile,
        "tolerance_applied": True,
        "compared_at": None  # Will be set by caller
    }
    
    log.info(f"Comparison complete: {overall_status} overall, "
             f"WPS: {wps_status}, CPM: {cpm_status}, Scene: {scene_status}")
    
    return comparison


def _compare_metric(value: float, band: List[float], metric_name: str) -> str:
    """
    Compare a single metric value against its band.
    
    Args:
        value: Metric value to compare
        band: [min, max] band for the metric
        metric_name: Name of the metric for logging
        
    Returns:
        Status: 'ok', 'fast', or 'slow'
    """
    if len(band) != 2:
        log.warning(f"Invalid band for {metric_name}: {band}")
        return 'ok'
    
    min_val, max_val = band[0], band[1]
    
    if value < min_val:
        log.debug(f"{metric_name}: {value:.2f} < {min_val:.2f} (slow)")
        return 'slow'
    elif value > max_val:
        log.debug(f"{metric_name}: {value:.2f} > {max_val:.2f} (fast)")
        return 'fast'
    else:
        log.debug(f"{metric_name}: {value:.2f} in range [{min_val:.2f}, {max_val:.2f}] (ok)")
        return 'ok'


def _determine_overall_status(statuses: List[str]) -> str:
    """
    Determine overall status based on individual metric statuses.
    
    Args:
        statuses: List of individual metric statuses
        
    Returns:
        Overall status: 'ok', 'fast', or 'slow'
    """
    if not statuses:
        return 'ok'
    
    # Count statuses
    status_counts = {}
    for status in statuses:
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Determine overall status based on majority
    if status_counts.get('slow', 0) > status_counts.get('fast', 0):
        return 'slow'
    elif status_counts.get('fast', 0) > status_counts.get('slow', 0):
        return 'fast'
    else:
        return 'ok'


def save_pacing_report(slug: str, kpi_data: Dict, comparison: Dict, 
                      report_dir: str = None) -> str:
    """
    Save complete pacing report with comparison results.
    
    Args:
        slug: Content slug identifier
        kpi_data: KPI computation results
        comparison: Comparison results and flags
        report_dir: Optional custom report directory
        
    Returns:
        Path to saved report file
    """
    if report_dir is None:
        report_dir = os.path.join(os.path.dirname(__file__), '..', 'runs', slug)
    
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, 'pacing_report.json')
    
    # Combine KPI data with comparison results
    complete_report = {
        "kpi_metrics": kpi_data,
        "comparison": comparison,
        "metadata": {
            "slug": slug,
            "intent": get_current_intent(),
            "compared_at": None  # Will be set by caller
        }
    }
    
    # Add timestamp
    import datetime
    timestamp = datetime.datetime.utcnow().isoformat() + 'Z'
    complete_report['metadata']['compared_at'] = timestamp
    
    # Also set the timestamp in the comparison for metadata update
    comparison['compared_at'] = timestamp
    
    with open(report_path, 'w') as f:
        json.dump(complete_report, f, indent=2)
    
    log.info(f"Complete pacing report saved to {report_path}")
    return report_path


def update_video_metadata(slug: str, kpi_data: Dict, comparison: Dict, 
                         metadata_dir: str = None) -> str:
    """
    Update video metadata with pacing KPIs and comparison flags.
    
    Args:
        slug: Content slug identifier
        kpi_data: KPI computation results
        comparison: Comparison results and flags
        metadata_dir: Optional custom metadata directory
        
    Returns:
        Path to updated metadata file
    """
    if metadata_dir is None:
        metadata_dir = os.path.join(os.path.dirname(__file__), '..', 'videos')
    
    metadata_path = os.path.join(metadata_dir, f'{slug}.metadata.json')
    
    # Load existing metadata
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {}
    
    # Add complete pacing section
    metadata['pacing'] = {
        "words_per_sec": kpi_data['words_per_sec'],
        "cuts_per_min": kpi_data['cuts_per_min'],
        "avg_scene_s": kpi_data['avg_scene_s'],
        "speech_music_ratio": kpi_data['speech_music_ratio'],
        "source": kpi_data['source'],
        "bands": comparison['profile_used'],
        "flags": comparison['flags'],
        "overall_status": comparison['overall_status'],
        "adjusted": False,  # Will be set by feedback module
        "computed_at": kpi_data['metadata']['computed_at'],
        "compared_at": comparison.get('metadata', {}).get('compared_at') or comparison.get('compared_at')
    }
    
    # Save updated metadata
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    log.info(f"Video metadata updated with pacing comparison: {metadata_path}")
    return metadata_path


def run_pacing_analysis(slug: str, kpi_data: Dict) -> Dict:
    """
    Run complete pacing analysis including comparison and feedback adjustment.
    
    Args:
        slug: Content slug identifier
        kpi_data: KPI computation results from pacing_kpi.py
        
    Returns:
        Complete analysis results
    """
    log.info(f"Running pacing analysis for {slug}")
    
    # Load intent profiles
    profiles = load_intent_profiles()
    if not profiles:
        log.error("No intent profiles available for comparison")
        return {}
    
    # Get current intent
    current_intent = get_current_intent()
    profile = profiles.get(current_intent, profiles.get('default', {}))
    
    if not profile:
        log.error(f"No profile found for intent: {current_intent}")
        return {}
    
    log.info(f"Using profile for intent: {current_intent}")
    
    # Compare KPIs to profile
    comparison = compare_to_profile(kpi_data, profile)
    
    # Save complete report
    report_path = save_pacing_report(slug, kpi_data, comparison)
    
    # Update video metadata
    metadata_path = update_video_metadata(slug, kpi_data, comparison)
    
    # Run feedback adjustment if enabled
    feedback_result = None
    log.info("[pacing-compare] Attempting to run feedback adjustment...")
    
    # Load scenescript for feedback adjustment
    scenescript_path = os.path.join(os.path.dirname(__file__), '..', 'scenescripts', f'{slug}.json')
    if os.path.exists(scenescript_path):
        with open(scenescript_path, 'r') as f:
            scenescript = json.load(f)
        
        scenes = scenescript.get('scenes', [])
        modules_cfg = load_modules_cfg()
        
        # Run feedback adjustment using integrated functions
        # Pass the KPI metrics and bands separately
        kpi_metrics = report_data.get('kpi_metrics', {})
        bands = report_data.get('comparison', {}).get('profile_used', {})
        
        # Create a combined data structure for the feedback function
        feedback_data = {
            'kpi_metrics': kpi_metrics,
            'comparison': {'profile_used': bands}
        }
        

        
        adjusted_scenes, feedback_summary = _run_integrated_feedback_adjustment(slug, feedback_data, scenes, modules_cfg)
        feedback_result = {
            "adjusted_scenes": adjusted_scenes,
            "summary": feedback_summary
        }
        
        if feedback_summary.get('adjusted'):
            log.info(f"[pacing-feedback] Applied adjustments to {feedback_summary['adjusted_scenes']} scenes")
            
            # Save adjusted scenescript
            adjusted_path = os.path.join(os.path.dirname(__file__), '..', 'scenescripts', f'{slug}_adjusted.json')
            
            # Save the adjusted scenes with new durations
            adjusted_scenescript = scenescript.copy()
            adjusted_scenescript['scenes'] = adjusted_scenes
            adjusted_scenescript['metadata']['pacing_adjusted'] = True
            adjusted_scenescript['metadata']['pacing_adjustment_ms'] = feedback_summary['total_adjustment_ms']
            
            with open(adjusted_path, 'w') as f:
                json.dump(adjusted_scenescript, f, indent=2)
            
            # Update metadata to mark as adjusted
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                if 'pacing' not in metadata:
                    metadata['pacing'] = {}
                metadata['pacing']['adjusted'] = True
                metadata['pacing']['adjustments_applied'] = feedback_summary['total_adjustment_ms']
                
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                log.info(f"[pacing-feedback] Updated metadata: adjusted=true, total_adjustment={feedback_summary['total_adjustment_ms']}ms")
        else:
            log.info("[pacing-feedback] No adjustments needed or feedback disabled")
    else:
        log.warning(f"[pacing-feedback] Scenescript not found: {scenescript_path}")
    
    # Compile results
    analysis_result = {
        "slug": slug,
        "intent": current_intent,
        "kpi_data": kpi_data,
        "comparison": comparison,
        "report_path": report_path,
        "metadata_path": metadata_path,
        "feedback_result": feedback_result
    }
    
    log.info(f"Pacing analysis complete for {slug}")
    return analysis_result


# Feedback adjustment functions (integrated to avoid import issues)
def _check_adjustment_need(kpi: Dict, bands: Dict, tolerance_pct: float) -> bool:
    """Check if any KPI is outside tolerance and needs adjustment."""
    metrics = ['words_per_sec', 'cuts_per_min', 'avg_scene_s']
    
    log.info(f"[pacing-feedback] Checking adjustment need with tolerance: {tolerance_pct}%")
    
    # Extract KPI metrics from nested structure if needed
    kpi_metrics = kpi.get('kpi_metrics', kpi)
    log.info(f"[pacing-feedback] KPI data structure: {list(kpi.keys())}")
    log.info(f"[pacing-feedback] KPI metrics structure: {list(kpi_metrics.keys())}")
    
    for metric in metrics:
        if metric not in kpi_metrics or metric not in bands:
            log.debug(f"[pacing-feedback] Skipping {metric}: not in KPI or bands")
            continue
            
        value = kpi_metrics[metric]
        band = bands[metric]
        
        log.debug(f"[pacing-feedback] Checking {metric}: value={value}, band={band}")
        
        if len(band) != 2:
            log.debug(f"[pacing-feedback] Skipping {metric}: band length != 2")
            continue
            
        min_val, max_val = band
        if min_val <= value <= max_val:
            log.debug(f"[pacing-feedback] {metric} {value} within band [{min_val}, {max_val}]")
            continue
            
        # Calculate deviation percentage
        if value < min_val:
            deviation = (min_val - value) / min_val * 100
            log.info(f"[pacing-feedback] {metric} {value} below band [{min_val}, {max_val}], "
                     f"deviation: {deviation:.1f}%")
        else:
            deviation = (value - max_val) / max_val * 100
            log.info(f"[pacing-feedback] {metric} {value} above band [{min_val}, {max_val}], "
                     f"deviation: {deviation:.1f}%")
            
        if deviation > tolerance_pct:
            log.info(f"[pacing-feedback] {metric} {value} outside band [{min_val}, {max_val}], "
                     f"deviation: {deviation:.1f}% > {tolerance_pct}% - ADJUSTMENT NEEDED")
            return True
        else:
            log.info(f"[pacing-feedback] {metric} {value} outside band but within tolerance: "
                     f"deviation: {deviation:.1f}% <= {tolerance_pct}%")
    
    log.info("[pacing-feedback] No adjustments needed - all metrics within tolerance")
    return False


def _calculate_metric_adjustments(kpi: Dict, bands: Dict, tolerance_pct: float) -> Dict[str, float]:
    """Calculate which metrics need adjustment and in what direction."""
    adjustments = {}
    
    # Extract KPI metrics from nested structure if needed
    kpi_metrics = kpi.get('kpi_metrics', kpi)
    
    log.info(f"[pacing-feedback] Calculating metric adjustments...")
    log.info(f"[pacing-feedback] Available metrics: {list(kpi_metrics.keys())}")
    log.info(f"[pacing-feedback] Available bands: {list(bands.keys())}")
    
    for metric in ['words_per_sec', 'cuts_per_min', 'avg_scene_s']:
        log.info(f"[pacing-feedback] Checking metric: {metric}")
        
        if metric not in kpi_metrics:
            log.info(f"[pacing-feedback] Metric {metric} not in KPI data")
            continue
            
        if metric not in bands:
            log.info(f"[pacing-feedback] Metric {metric} not in bands")
            continue
            
        value = kpi_metrics[metric]
        band = bands[metric]
        
        log.info(f"[pacing-feedback] {metric}: value={value}, band={band}")
        
        if len(band) != 2:
            log.info(f"[pacing-feedback] Band for {metric} is not length 2: {band}")
            continue
            
        min_val, max_val = band
        
        if value < min_val:
            # Value is too low, need to increase (longer scenes, slower pacing)
            adjustments[metric] = 1.0  # Positive adjustment
            log.info(f"[pacing-feedback] {metric} below band: {value} < {min_val} -> +1.0")
        elif value > max_val:
            # Value is too high, need to decrease (shorter scenes, faster pacing)
            adjustments[metric] = -1.0  # Negative adjustment
            log.info(f"[pacing-feedback] {metric} above band: {value} > {max_val} -> -1.0")
        else:
            adjustments[metric] = 0.0  # No adjustment needed
            log.info(f"[pacing-feedback] {metric} within band: {min_val} <= {value} <= {max_val} -> 0.0")
    
    log.info(f"[pacing-feedback] Final metric adjustments: {adjustments}")
    return adjustments


def _calculate_scene_slack(scenes: List[Dict], cfg: Dict) -> Dict[str, int]:
    """Calculate available slack for each scene based on current duration vs bounds."""
    timing_cfg = cfg.get('timing', {})
    min_scene_ms = timing_cfg.get('min_scene_ms', 2500)
    max_scene_ms = timing_cfg.get('max_scene_ms', 30000)
    
    scene_slack = {}
    
    for scene in scenes:
        scene_id = scene.get("id", "unknown")
        duration = scene.get("duration_ms", 0)
        
        # Calculate slack in both directions
        slack_down = duration - min_scene_ms  # How much we can decrease
        slack_up = max_scene_ms - duration    # How much we can increase
        
        # Total available slack (minimum of up/down)
        total_slack = min(slack_down, slack_up)
        
        scene_slack[scene_id] = total_slack
        
        log.debug(f"[pacing-feedback] Scene {scene_id}: duration={duration}ms, "
                  f"slack_down={slack_down}ms, slack_up={slack_up}ms, total={total_slack}ms")
    
    return scene_slack


def _generate_scene_adjustments(
    scenes: List[Dict], 
    scene_slack: Dict[str, int], 
    metric_adjustments: Dict[str, float],
    max_adjust_ms: int,
    max_total_ms: int,
    cfg: Dict
) -> List[Dict]:
    """Generate scene adjustments prioritizing scenes with most available slack."""
    
    # Determine overall adjustment direction based on primary metric
    primary_metric = 'words_per_sec'  # Primary pacing metric
    if primary_metric in metric_adjustments:
        overall_direction = metric_adjustments[primary_metric]
    else:
        # Fallback to average scene length
        overall_direction = metric_adjustments.get('avg_scene_s', 0.0)
    
    if overall_direction == 0:
        log.info("[pacing-feedback] No overall adjustment direction determined")
        return [{"id": scene.get("id", f"scene_{i:03d}"), "delta_ms": 0} for i, scene in enumerate(scenes)]
    
    # Sort scenes by available slack (descending)
    scenes_with_slack = []
    for scene in scenes:
        scene_id = scene.get("id", "unknown")
        slack = scene_slack.get(scene_id, 0)
        if slack > 0:
            scenes_with_slack.append((scene_id, slack, scene))
    
    scenes_with_slack.sort(key=lambda x: x[1], reverse=True)
    
    # Generate adjustments starting with scenes that have most slack
    adjustments = []
    remaining_budget = max_total_ms
    
    for scene_id, slack, scene in scenes_with_slack:
        if remaining_budget <= 0:
            # No more budget for adjustments
            adjustments.append({"id": scene_id, "delta_ms": 0})
            continue
        
        # Calculate adjustment amount
        # Use smaller of: available slack, max per scene, remaining budget
        max_possible = min(slack, max_adjust_ms, remaining_budget)
        
        if max_possible < 500:  # Minimum meaningful adjustment
            adjustments.append({"id": scene_id, "delta_ms": 0})
            continue
        
        # Apply adjustment in the determined direction
        delta_ms = int(max_possible * overall_direction)
        
        # Ensure we don't exceed remaining budget
        if abs(delta_ms) > remaining_budget:
            delta_ms = int(remaining_budget * overall_direction)
        
        adjustments.append({"id": scene_id, "delta_ms": delta_ms})
        remaining_budget -= abs(delta_ms)
        
        log.debug(f"[pacing-feedback] Scene {scene_id}: slack={slack}ms, "
                  f"adjustment={delta_ms:+d}ms, remaining_budget={remaining_budget}ms")
    
    # Add scenes with no slack
    for scene in scenes:
        scene_id = scene.get("id", "unknown")
        if not any(adj["id"] == scene_id for adj in adjustments):
            adjustments.append({"id": scene_id, "delta_ms": 0})
    
    return adjustments


def _apply_scene_adjustments(scenes: List[Dict], adjustments: List[Dict], cfg: Dict) -> List[Dict]:
    """Apply suggested adjustments to scene durations."""
    log.info("[pacing-feedback] Applying duration adjustments")
    
    # Load timing configuration
    timing_cfg = cfg.get('timing', {})
    min_scene_ms = timing_cfg.get('min_scene_ms', 2500)
    max_scene_ms = timing_cfg.get('max_scene_ms', 30000)
    
    adjusted_scenes = []
    total_adjustment = 0
    
    for i, scene in enumerate(scenes):
        scene_id = scene.get("id", f"scene_{i:03d}")
        
        # Find matching adjustment
        adjustment = next((adj for adj in adjustments if adj["id"] == scene_id), None)
        if not adjustment:
            log.warning(f"[pacing-feedback] No adjustment found for scene {scene_id}")
            adjusted_scenes.append(scene)
            continue
        
        delta_ms = adjustment["delta_ms"]
        original_duration = scene.get("duration_ms", 0)
        
        if delta_ms == 0:
            # No change needed
            adjusted_scenes.append(scene)
            continue
        
        # Apply duration adjustment
        new_duration = original_duration + delta_ms
        
        # Clamp to min/max bounds
        clamped_duration = max(min_scene_ms, min(max_scene_ms, new_duration))
        actual_delta = clamped_duration - original_duration
        
        if actual_delta != delta_ms:
            log.info(f"[pacing-feedback] Scene {scene_id} adjustment clamped: "
                     f"{delta_ms}ms → {actual_delta}ms")
        
        # Create adjusted scene
        adjusted_scene = scene.copy()
        adjusted_scene["duration_ms"] = clamped_duration
        
        # Add adjustment metadata
        if "metadata" not in adjusted_scene:
            adjusted_scene["metadata"] = {}
        adjusted_scene["metadata"]["pacing_adjustment"] = {
            "original_duration_ms": original_duration,
            "requested_delta_ms": delta_ms,
            "actual_delta_ms": actual_delta,
            "clamped": actual_delta != delta_ms,
            "reason": "pacing_feedback"
        }
        
        adjusted_scenes.append(adjusted_scene)
        total_adjustment += abs(actual_delta)
        
        log.info(f"[pacing-feedback] Scene {scene_id}: {original_duration}ms → {clamped_duration}ms "
                 f"(delta: {actual_delta:+d}ms)")
    
    log.info(f"[pacing-feedback] Applied adjustments to {len(adjusted_scenes)} scenes, "
             f"total adjustment: {total_adjustment}ms")
    
    return adjusted_scenes


def _run_integrated_feedback_adjustment(slug: str, kpi_data: Dict, scenes: List[Dict], cfg: Dict) -> Tuple[List[Dict], Dict]:
    """Run feedback adjustment using integrated functions."""
    log.info(f"[pacing-feedback] Starting integrated feedback adjustment for {slug}")
    
    # Check if pacing feedback is enabled
    pacing_cfg = cfg.get('pacing', {})
    if not pacing_cfg.get('enable', True):
        log.info("[pacing-feedback] Pacing feedback disabled in configuration")
        return scenes, {"enabled": False, "adjustments": []}
    
    # Extract bands from KPI data
    bands = kpi_data.get('comparison', {}).get('profile_used', {})
    if not bands:
        log.warning("[pacing-feedback] No bands found in KPI data")
        return scenes, {"enabled": True, "error": "No bands found"}
    
    # Load pacing configuration
    pacing_cfg = cfg.get('pacing', {})
    max_adjust_ms = pacing_cfg.get('max_adjust_ms_per_scene', 1000)
    max_total_ms = pacing_cfg.get('max_total_adjust_ms', 5000)
    tolerance_pct = pacing_cfg.get('tolerance_pct', 10.0)
    
    # Check if adjustments are needed (>10% out of band)
    adjustments_needed = _check_adjustment_need(kpi_data, bands, tolerance_pct)
    if not adjustments_needed:
        log.info("[pacing-feedback] KPIs within tolerance, no adjustments needed")
        return scenes, {"enabled": True, "adjustments": [], "adjusted": False}
    
    # Calculate which metrics need adjustment and direction
    metric_adjustments = _calculate_metric_adjustments(kpi_data, bands, tolerance_pct)
    
    # Determine scene adjustment priorities based on available slack
    scene_slack = _calculate_scene_slack(scenes, cfg)
    
    # Generate adjustments prioritizing scenes with most slack
    adjustments = _generate_scene_adjustments(
        scenes, scene_slack, metric_adjustments, 
        max_adjust_ms, max_total_ms, cfg
    )
    
    # Apply adjustments
    adjusted_scenes = _apply_scene_adjustments(scenes, adjustments, cfg)
    
    # Prepare summary
    summary = {
        "enabled": True,
        "adjusted": True,
        "adjustments": adjustments,
        "total_adjustment_ms": sum(abs(adj["delta_ms"]) for adj in adjustments),
        "adjusted_scenes": len([adj for adj in adjustments if adj["delta_ms"] != 0])
    }
    
    log.info(f"[pacing-feedback] Integrated feedback adjustment complete: {summary['adjusted_scenes']} scenes adjusted")
    
    return adjusted_scenes, summary


if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pacing_compare.py <slug> [--feedback]")
        print("  --feedback: Force feedback adjustment even if report exists")
        sys.exit(1)
    
    slug = sys.argv[1]
    force_feedback = '--feedback' in sys.argv
    
    # Load existing KPI data for testing
    report_path = os.path.join(os.path.dirname(__file__), '..', 'runs', slug, 'pacing_report.json')
    
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        # Handle both old and new report formats
        if 'kpi_metrics' in report_data:
            # New format with comparison already done
            kpi_data = report_data['kpi_metrics']
            comparison = report_data['comparison']
            print("Report already contains comparison data:")
            print(f"Intent: {report_data['metadata']['intent']}")
            print(f"Overall status: {comparison['overall_status']}")
            print(f"Flags: {comparison['flags']}")
            
            if force_feedback:
                print("Forcing feedback adjustment...")
                # Extract KPI data from the report for feedback adjustment
                kpi_data_for_feedback = report_data.get('kpi_metrics', report_data)
                print(f"KPI data structure: {list(kpi_data_for_feedback.keys())}")
                
                # If it's still nested, extract the actual metrics
                if 'kpi_metrics' in kpi_data_for_feedback:
                    kpi_data_for_feedback = kpi_data_for_feedback['kpi_metrics']
                    print(f"Extracted KPI metrics: {list(kpi_data_for_feedback.keys())}")
                
                result = run_pacing_analysis(slug, kpi_data_for_feedback)
                if result.get('feedback_result'):
                    feedback = result['feedback_result']
                    # Check if adjustments were applied (either directly or in summary)
                    feedback_adjusted = feedback.get('adjusted') or feedback.get('summary', {}).get('adjusted', False)
                    if feedback_adjusted:
                        adjusted_scenes = feedback.get('adjusted_scenes') or feedback.get('summary', {}).get('adjusted_scenes', 0)
                        total_adjustment = feedback.get('total_adjustment_ms') or feedback.get('summary', {}).get('total_adjustment_ms', 0)
                        print(f"Feedback adjustment applied: {adjusted_scenes} scenes adjusted")
                        print(f"Total adjustment: {total_adjustment}ms")
                    else:
                        print("No feedback adjustments were needed")
                else:
                    print("Feedback adjustment failed or not available")
        else:
            # Old format, just KPI data
            kpi_data = report_data
            print("Running comparison analysis on existing KPI data...")
            result = run_pacing_analysis(slug, kpi_data)
            print("Pacing analysis completed successfully!")
            print(f"Intent: {result['intent']}")
            print(f"Overall status: {result['comparison']['overall_status']}")
            print(f"Flags: {result['comparison']['flags']}")
    else:
        print(f"No KPI data found for {slug}. Run pacing_kpi.py first.")
        sys.exit(1)
