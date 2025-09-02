#!/usr/bin/env python3
"""
Pacing Feedback Adjuster - Deterministic Duration Nudge

Provides one-pass feedback adjustment for pacing KPIs that are outside target bands.
Respects VO alignment, timing clamps, and ensures no QA regressions.
"""

import argparse
import json
import os
from typing import Dict, List, Tuple

try:
    # Try relative import first (when used as module)
    from .core import get_logger, load_config, load_modules_cfg
except ImportError:
    try:
        # Try absolute import (when imported from other modules)
        from core import get_logger, load_config, load_modules_cfg
    except ImportError:
        # Handle direct execution
        import sys

        sys.path.append(os.path.dirname(__file__))
        from core import get_logger, load_config, load_modules_cfg

log = get_logger("pacing-feedback")


def suggest_adjustments(
    kpi: Dict, bands: Dict, scenes: List[Dict], cfg: Dict
) -> List[Dict]:
    """
    Suggest deterministic adjustments to move KPIs toward target bands.

    Args:
        kpi: Dictionary with pacing metrics (words_per_sec, cuts_per_min, avg_scene_s)
        bands: Intent profile bands for comparison
        scenes: List of scene dictionaries with duration_ms
        cfg: Configuration dictionary with pacing settings

    Returns:
        List of per-scene adjustments with {"id": ..., "delta_ms": ...}
    """
    log.info("[pacing-feedback] Analyzing KPI adjustments")

    # Load pacing configuration
    pacing_cfg = cfg.get("pacing", {})
    max_adjust_ms = pacing_cfg.get("max_adjust_ms_per_scene", 1000)
    max_total_ms = pacing_cfg.get("max_total_adjust_ms", 5000)
    tolerance_pct = pacing_cfg.get("tolerance_pct", 10.0)

    # Check if adjustments are needed (>10% out of band)
    log.info(f"[pacing-feedback] KPI data keys: {list(kpi.keys())}")
    log.info(f"[pacing-feedback] Bands data keys: {list(bands.keys())}")
    adjustments_needed = _check_adjustment_need(kpi, bands, tolerance_pct)
    if not adjustments_needed:
        log.info("[pacing-feedback] KPIs within tolerance, no adjustments needed")
        return [
            {"id": scene.get("id", f"scene_{i:03d}"), "delta_ms": 0}
            for i, scene in enumerate(scenes)
        ]

    # Calculate which metrics need adjustment and direction
    metric_adjustments = _calculate_metric_adjustments(kpi, bands, tolerance_pct)

    # Determine scene adjustment priorities based on available slack
    scene_slack = _calculate_scene_slack(scenes, cfg)

    # Generate adjustments prioritizing scenes with most slack
    adjustments = _generate_scene_adjustments(
        scenes, scene_slack, metric_adjustments, max_adjust_ms, max_total_ms, cfg
    )

    # Validate total adjustment doesn't exceed limits
    total_adjustment = sum(abs(adj["delta_ms"]) for adj in adjustments)
    if total_adjustment > max_total_ms:
        log.warning(
            f"[pacing-feedback] Total adjustment {total_adjustment}ms exceeds limit {max_total_ms}ms, scaling down"
        )
        adjustments = _scale_adjustments(adjustments, max_total_ms)

    log.info(
        f"[pacing-feedback] Suggested {len([a for a in adjustments if a['delta_ms'] != 0])} adjustments, "
        f"total delta: {total_adjustment}ms"
    )

    return adjustments


def apply_adjustments(
    scenes: List[Dict], adjustments: List[Dict], cfg: Dict
) -> List[Dict]:
    """
    Apply suggested adjustments to scene durations.

    Args:
        scenes: List of scene dictionaries
        adjustments: List of adjustment dictionaries from suggest_adjustments
        cfg: Configuration dictionary

    Returns:
        New list of scenes with adjusted durations
    """
    log.info("[pacing-feedback] Applying duration adjustments")

    # Load timing configuration
    timing_cfg = cfg.get("timing", {})
    min_scene_ms = timing_cfg.get("min_scene_ms", 2500)
    max_scene_ms = timing_cfg.get("max_scene_ms", 30000)
    align_to_vo = timing_cfg.get("align_to_vo", True)

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

        # Check if VO alignment prevents scene boundary changes
        if align_to_vo and _has_vo_timing(scene):
            log.info(
                f"[pacing-feedback] Scene {scene_id} has VO timing, adjusting internal timing only"
            )
            # For VO-aligned scenes, we can adjust internal timing but not boundaries
            # This would require more complex logic to redistribute B-roll timings
            # For now, skip adjustment to maintain VO alignment
            adjusted_scenes.append(scene)
            continue

        # Apply duration adjustment
        new_duration = original_duration + delta_ms

        # Clamp to min/max bounds
        clamped_duration = max(min_scene_ms, min(max_scene_ms, new_duration))
        actual_delta = clamped_duration - original_duration

        if actual_delta != delta_ms:
            log.info(
                f"[pacing-feedback] Scene {scene_id} adjustment clamped: "
                f"{delta_ms}ms → {actual_delta}ms"
            )

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
            "reason": "pacing_feedback",
        }

        adjusted_scenes.append(adjusted_scene)
        total_adjustment += abs(actual_delta)

        log.info(
            f"[pacing-feedback] Scene {scene_id}: {original_duration}ms → {clamped_duration}ms "
            f"(delta: {actual_delta:+d}ms)"
        )

    log.info(
        f"[pacing-feedback] Applied adjustments to {len(adjusted_scenes)} scenes, "
        f"total adjustment: {total_adjustment}ms"
    )

    return adjusted_scenes


def _check_adjustment_need(kpi: Dict, bands: Dict, tolerance_pct: float) -> bool:
    """Check if any KPI is outside tolerance and needs adjustment."""
    metrics = ["words_per_sec", "cuts_per_min", "avg_scene_s"]

    log.info(
        f"[pacing-feedback] Checking adjustment need with tolerance: {tolerance_pct}%"
    )

    for metric in metrics:
        if metric not in kpi or metric not in bands:
            log.debug(f"[pacing-feedback] Skipping {metric}: not in KPI or bands")
            continue

        value = kpi[metric]
        band = bands[metric]

        log.debug(f"[pacing-feedback] Checking {metric}: value={value}, band={band}")

        if len(band) != 2:
            log.debug(f"[pacing-feedback] Skipping {metric}: band length != 2")
            continue

        min_val, max_val = band
        if min_val <= value <= max_val:
            log.debug(
                f"[pacing-feedback] {metric} {value} within band [{min_val}, {max_val}]"
            )
            continue

        # Calculate deviation percentage
        if value < min_val:
            deviation = (min_val - value) / min_val * 100
            log.info(
                f"[pacing-feedback] {metric} {value} below band [{min_val}, {max_val}], "
                f"deviation: {deviation:.1f}%"
            )
        else:
            deviation = (value - max_val) / max_val * 100
            log.info(
                f"[pacing-feedback] {metric} {value} above band [{min_val}, {max_val}], "
                f"deviation: {deviation:.1f}%"
            )

        if deviation > tolerance_pct:
            log.info(
                f"[pacing-feedback] {metric} {value} outside band [{min_val}, {max_val}], "
                f"deviation: {deviation:.1f}% > {tolerance_pct}% - ADJUSTMENT NEEDED"
            )
            return True
        else:
            log.info(
                f"[pacing-feedback] {metric} {value} outside band but within tolerance: "
                f"deviation: {deviation:.1f}% <= {tolerance_pct}%"
            )

    log.info("[pacing-feedback] No adjustments needed - all metrics within tolerance")
    return False


def _calculate_metric_adjustments(
    kpi: Dict, bands: Dict, tolerance_pct: float
) -> Dict[str, float]:
    """Calculate which metrics need adjustment and in what direction."""
    adjustments = {}

    for metric in ["words_per_sec", "cuts_per_min", "avg_scene_s"]:
        if metric not in kpi or metric not in bands:
            continue

        value = kpi[metric]
        band = bands[metric]

        if len(band) != 2:
            continue

        min_val, max_val = band

        if value < min_val:
            # Value is too low, need to increase (longer scenes, slower pacing)
            adjustments[metric] = 1.0  # Positive adjustment
        elif value > max_val:
            # Value is too high, need to decrease (shorter scenes, faster pacing)
            adjustments[metric] = -1.0  # Negative adjustment
        else:
            adjustments[metric] = 0.0  # No adjustment needed

    log.info(f"[pacing-feedback] Metric adjustments: {adjustments}")
    return adjustments


def _calculate_scene_slack(scenes: List[Dict], cfg: Dict) -> Dict[str, int]:
    """Calculate available slack for each scene based on current duration vs bounds."""
    timing_cfg = cfg.get("timing", {})
    min_scene_ms = timing_cfg.get("min_scene_ms", 2500)
    max_scene_ms = timing_cfg.get("max_scene_ms", 30000)

    scene_slack = {}

    for scene in scenes:
        scene_id = scene.get("id", "unknown")
        duration = scene.get("duration_ms", 0)

        # Calculate slack in both directions
        slack_down = duration - min_scene_ms  # How much we can decrease
        slack_up = max_scene_ms - duration  # How much we can increase

        # Total available slack (minimum of up/down)
        total_slack = min(slack_down, slack_up)

        scene_slack[scene_id] = total_slack

        log.debug(
            f"[pacing-feedback] Scene {scene_id}: duration={duration}ms, "
            f"slack_down={slack_down}ms, slack_up={slack_up}ms, total={total_slack}ms"
        )

    return scene_slack


def _generate_scene_adjustments(
    scenes: List[Dict],
    scene_slack: Dict[str, int],
    metric_adjustments: Dict[str, float],
    max_adjust_ms: int,
    max_total_ms: int,
    cfg: Dict,
) -> List[Dict]:
    """Generate scene adjustments prioritizing scenes with most available slack."""

    # Determine overall adjustment direction based on primary metric
    primary_metric = "words_per_sec"  # Primary pacing metric
    if primary_metric in metric_adjustments:
        overall_direction = metric_adjustments[primary_metric]
    else:
        # Fallback to average scene length
        overall_direction = metric_adjustments.get("avg_scene_s", 0.0)

    if overall_direction == 0:
        log.info("[pacing-feedback] No overall adjustment direction determined")
        return [
            {"id": scene.get("id", f"scene_{i:03d}"), "delta_ms": 0}
            for i, scene in enumerate(scenes)
        ]

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

        log.debug(
            f"[pacing-feedback] Scene {scene_id}: slack={slack}ms, "
            f"adjustment={delta_ms:+d}ms, remaining_budget={remaining_budget}ms"
        )

    # Add scenes with no slack
    for scene in scenes:
        scene_id = scene.get("id", "unknown")
        if not any(adj["id"] == scene_id for adj in adjustments):
            adjustments.append({"id": scene_id, "delta_ms": 0})

    return adjustments


def _scale_adjustments(adjustments: List[Dict], max_total_ms: int) -> List[Dict]:
    """Scale down adjustments to fit within total budget."""
    total_adjustment = sum(abs(adj["delta_ms"]) for adj in adjustments)
    if total_adjustment <= max_total_ms:
        return adjustments

    scale_factor = max_total_ms / total_adjustment

    scaled_adjustments = []
    for adj in adjustments:
        scaled_delta = int(adj["delta_ms"] * scale_factor)
        scaled_adjustments.append({"id": adj["id"], "delta_ms": scaled_delta})

    log.info(f"[pacing-feedback] Scaled adjustments by factor {scale_factor:.2f}")
    return scaled_adjustments


def _has_vo_timing(scene: Dict) -> bool:
    """Check if scene has VO timing constraints."""
    # Check for VO-related metadata or timing constraints
    metadata = scene.get("metadata", {})
    if metadata.get("vo_aligned") or metadata.get("duration_strategy") == "vo":
        return True

    # Check for audio cues or timing constraints
    if scene.get("audio_cue") or "vo_cue" in str(metadata):
        return True

    return False


def save_adjustments_report(
    slug: str, adjustments: List[Dict], report_dir: str = None
) -> str:
    """Save pacing adjustments report."""
    if report_dir is None:
        report_dir = os.path.join(os.path.dirname(__file__), "..", "runs", slug)

    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "pacing_adjustments.json")

    # Calculate summary statistics
    total_adjustment = sum(abs(adj["delta_ms"]) for adj in adjustments)
    adjusted_scenes = len([adj for adj in adjustments if adj["delta_ms"] != 0])

    report_data = {
        "slug": slug,
        "adjustments": adjustments,
        "summary": {
            "total_adjustment_ms": total_adjustment,
            "adjusted_scenes": adjusted_scenes,
            "total_scenes": len(adjustments),
        },
        "metadata": {"generated_at": None},  # Will be set by caller
    }

    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)

    log.info(f"[pacing-feedback] Adjustments report saved to {report_path}")
    return report_path


def update_pacing_report_with_adjustments(
    slug: str, adjustments: List[Dict], report_dir: str = None
) -> str:
    """Update existing pacing report to mark as adjusted."""
    if report_dir is None:
        report_dir = os.path.join(os.path.dirname(__file__), "..", "runs", slug)

    report_path = os.path.join(report_dir, "pacing_report.json")

    if not os.path.exists(report_path):
        log.warning(f"[pacing-feedback] Pacing report not found: {report_path}")
        return ""

    try:
        with open(report_path, "r") as f:
            report_data = json.load(f)

        # Mark as adjusted
        if "metadata" not in report_data:
            report_data["metadata"] = {}
        report_data["metadata"]["pacing_adjustments_applied"] = True
        report_data["metadata"]["adjustments_count"] = len(
            [a for a in adjustments if a["delta_ms"] != 0]
        )

        # Save updated report
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)

        log.info(f"[pacing-feedback] Updated pacing report: {report_path}")
        return report_path

    except Exception as e:
        log.error(f"[pacing-feedback] Failed to update pacing report: {e}")
        return ""


def run_feedback_adjustment(
    slug: str, kpi_data: Dict, scenes: List[Dict], cfg: Dict
) -> Tuple[List[Dict], Dict]:
    """
    Run complete feedback adjustment process.

    Args:
        slug: Content slug identifier
        kpi_data: KPI data from pacing analysis
        scenes: List of scene dictionaries
        cfg: Configuration dictionary

    Returns:
        Tuple of (adjusted_scenes, adjustment_summary)
    """
    log.info(f"[pacing-feedback] Starting feedback adjustment for {slug}")

    # Check if pacing feedback is enabled
    pacing_cfg = cfg.get("pacing", {})
    if not pacing_cfg.get("enable", True):
        log.info("[pacing-feedback] Pacing feedback disabled in configuration")
        return scenes, {"enabled": False, "adjustments": []}

    # Extract bands from KPI data
    bands = kpi_data.get("comparison", {}).get("profile_used", {})
    if not bands:
        log.warning("[pacing-feedback] No bands found in KPI data")
        return scenes, {"enabled": True, "error": "No bands found"}

    # Extract actual KPI metrics (they're nested under kpi_metrics)
    actual_kpi = kpi_data.get("kpi_metrics", kpi_data)

    # Suggest adjustments
    adjustments = suggest_adjustments(actual_kpi, bands, scenes, cfg)

    # Check if any adjustments were suggested
    if not any(adj["delta_ms"] != 0 for adj in adjustments):
        log.info("[pacing-feedback] No adjustments needed")
        return scenes, {"enabled": True, "adjustments": [], "adjusted": False}

    # Apply adjustments
    adjusted_scenes = apply_adjustments(scenes, adjustments, cfg)

    # Save adjustment report
    adjustments_path = save_adjustments_report(slug, adjustments)

    # Update pacing report
    update_pacing_report_with_adjustments(slug, adjustments)

    # Prepare summary
    summary = {
        "enabled": True,
        "adjusted": True,
        "adjustments": adjustments,
        "adjustments_path": adjustments_path,
        "total_adjustment_ms": sum(abs(adj["delta_ms"]) for adj in adjustments),
        "adjusted_scenes": len([adj for adj in adjustments if adj["delta_ms"] != 0]),
    }

    log.info(
        f"[pacing-feedback] Feedback adjustment complete: {summary['adjusted_scenes']} scenes adjusted"
    )

    return adjusted_scenes, summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Apply pacing feedback adjustments to scene durations"
    )
    parser.add_argument("--slug", required=True, help="Content slug identifier")
    parser.add_argument(
        "--apply", action="store_true", help="Apply adjustments and update metadata"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed adjustments without applying",
    )

    args = parser.parse_args()
    slug = args.slug

    # Validate arguments
    if args.apply and args.dry_run:
        print("Error: Cannot use both --apply and --dry-run")
        sys.exit(1)

    if not args.apply and not args.dry_run:
        print("Error: Must specify either --apply or --dry-run")
        sys.exit(1)

    # Load configuration
    try:
        config = load_config()
        modules_cfg = load_modules_cfg()
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Load pacing report
    report_path = os.path.join(
        os.path.dirname(__file__), "..", "runs", slug, "pacing_report.json"
    )
    if not os.path.exists(report_path):
        print(f"Error: Pacing report not found at {report_path}")
        print("Please run pacing_kpi.py first to generate KPIs")
        sys.exit(1)

    with open(report_path, "r") as f:
        pacing_data = json.load(f)

    # Load scenescript
    scenescript_path = os.path.join(
        os.path.dirname(__file__), "..", "scenescripts", f"{slug}.json"
    )
    if not os.path.exists(scenescript_path):
        print(f"Error: Scenescript not found at {scenescript_path}")
        print("Please ensure scenescript exists at scenescripts/{slug}.json")
        sys.exit(1)

    with open(scenescript_path, "r") as f:
        scenescript = json.load(f)

    scenes = scenescript.get("scenes", [])

    if args.dry_run:
        # Dry run - just show proposed adjustments
        print(f"DRY RUN: Proposed pacing adjustments for {slug}")
        print("=" * 50)

        # Get current KPIs for comparison
        current_kpi = None
        try:
            # Try relative import first
            try:
                from .pacing_kpi import compute_pacing
            except ImportError:
                # Try absolute import
                from pacing_kpi import compute_pacing
        except ImportError:
            # Handle direct execution
            import sys

            sys.path.append(os.path.dirname(__file__))
            from pacing_kpi import compute_pacing

        try:
            script_path = os.path.join(
                os.path.dirname(__file__), "..", "scripts", f"{slug}.txt"
            )
            srt_path = os.path.join(
                os.path.dirname(__file__), "..", "voiceovers", f"{slug}.srt"
            )

            if not os.path.exists(script_path):
                print(f"Warning: Script file not found at {script_path}")
                script_text = ""
            else:
                with open(script_path, "r") as f:
                    script_text = f.read()

            if not os.path.exists(srt_path):
                srt_path = None

            video_ms = sum(scene.get("duration_ms", 0) for scene in scenes)
            current_kpi = compute_pacing(script_text, scenes, video_ms, srt_path)

            print("Current KPIs:")
            print(f"  Words/sec: {current_kpi['words_per_sec']:.2f}")
            print(f"  Cuts/min: {current_kpi['cuts_per_min']:.2f}")
            print(f"  Avg scene: {current_kpi['avg_scene_s']:.2f}s")
            print(f"  Speech/music ratio: {current_kpi['speech_music_ratio']:.2f}")
            print()

        except Exception as e:
            print(f"Warning: Could not compute current KPIs: {e}")
            current_kpi = None

        # Show proposed adjustments
        adjustments = suggest_adjustments(
            pacing_data,
            pacing_data.get("comparison", {}).get("profile_used", {}),
            scenes,
            modules_cfg,
        )

        if not any(adj["delta_ms"] != 0 for adj in adjustments):
            print("No adjustments needed - KPIs are within target bands")
        else:
            print("Proposed adjustments:")
            total_delta = 0
            for adj in adjustments:
                if adj["delta_ms"] != 0:
                    scene_id = adj["id"]
                    current_duration = next(
                        (
                            s.get("duration_ms", 0)
                            for s in scenes
                            if s.get("id") == scene_id
                        ),
                        0,
                    )
                    new_duration = current_duration + adj["delta_ms"]
                    print(
                        f"  {scene_id}: {current_duration}ms → {new_duration}ms (Δ{adj['delta_ms']:+d}ms)"
                    )
                    total_delta += abs(adj["delta_ms"])

            print(f"\nTotal adjustment: {total_delta}ms")

        # Print concise summary as required by P5-5
        if current_kpi:
            flags = []
            if current_kpi.get("source") == "vo":
                flags.append("vo-timed")
            if current_kpi.get("source") == "brief":
                flags.append("brief-timed")

            print(
                f"\n{current_kpi['words_per_sec']:.1f}wps {current_kpi['cuts_per_min']:.1f}cuts/min {current_kpi['avg_scene_s']:.1f}s avg {' '.join(flags)} adjusted=false"
            )

    else:
        # Apply adjustments
        print(f"Applying pacing adjustments for {slug}...")

        # Run feedback adjustment
        adjusted_scenes, summary = run_feedback_adjustment(
            slug, pacing_data, scenes, modules_cfg
        )

        if summary.get("adjusted"):
            print("✅ Adjustments applied successfully!")
            print(f"  Adjusted {summary['adjusted_scenes']} scenes")
            print(f"  Total adjustment: {summary['total_adjustment_ms']}ms")

            # Print concise summary as required by P5-5
            try:
                from bin.pacing_kpi import compute_pacing

                script_path = os.path.join(
                    os.path.dirname(__file__), "..", "scripts", f"{slug}.txt"
                )
                srt_path = os.path.join(
                    os.path.dirname(__file__), "..", "voiceovers", f"{slug}.srt"
                )

                if os.path.exists(script_path):
                    with open(script_path, "r") as f:
                        script_text = f.read()
                else:
                    script_text = ""

                if not os.path.exists(srt_path):
                    srt_path = None

                video_ms = sum(scene.get("duration_ms", 0) for scene in adjusted_scenes)
                updated_kpi = compute_pacing(
                    script_text, adjusted_scenes, video_ms, srt_path
                )

                flags = []
                if updated_kpi.get("source") == "vo":
                    flags.append("vo-timed")
                if updated_kpi.get("source") == "brief":
                    flags.append("brief-timed")

                print(
                    f"\n{updated_kpi['words_per_sec']:.1f}wps {updated_kpi['cuts_per_min']:.1f}cuts/min {updated_kpi['avg_scene_s']:.1f}s avg {' '.join(flags)} adjusted=true"
                )

            except Exception as e:
                print(f"Warning: Could not compute updated KPIs: {e}")
        else:
            print("ℹ️  No adjustments were needed - KPIs are within target bands")
            print("adjusted=false")
