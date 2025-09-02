#!/usr/bin/env python3
"""
Timing Utilities for Duration Policy Management

Provides functions for distributing video duration across scenes, aligning to VO cues,
and normalizing timing to meet brief targets within tolerance.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

from pathlib import Path

log = logging.getLogger(__name__)


def distribute_duration_by_words(
    beats: List[Dict],
    target_ms: int,
    min_scene_ms: int = 2500,
    max_scene_ms: int = 12000,
) -> List[int]:
    """
    Distribute target duration across beats weighted by word count.

    Args:
        beats: List of beat dictionaries with 'text' or 'content' fields
        target_ms: Target total duration in milliseconds
        min_scene_ms: Minimum scene duration in milliseconds
        max_scene_ms: Maximum scene duration in milliseconds

    Returns:
        List of scene durations in milliseconds that sum to target_ms
    """
    if not beats:
        return []

    # Count words per beat
    word_counts = []
    for beat in beats:
        text = beat.get("text", beat.get("content", ""))
        words = len(text.split()) if text else 1
        word_counts.append(max(1, words))

    total_words = sum(word_counts)

    # Allocate duration proportionally
    allocations = []
    for word_count in word_counts:
        allocated = int(target_ms * (word_count / total_words))
        allocations.append(allocated)

    # Clamp to min/max bounds
    clamped = []
    for alloc in allocations:
        clamped.append(min(max(alloc, min_scene_ms), max_scene_ms))

    # Normalize to exact target
    current_total = sum(clamped)
    delta = target_ms - current_total

    if delta != 0:
        # Distribute remainder by adjusting largest fractional parts
        # Sort by how much each scene can be adjusted
        adjustments = []
        for i, alloc in enumerate(clamped):
            if delta > 0:  # Need to add time
                room_to_add = max_scene_ms - alloc
                if room_to_add > 0:
                    adjustments.append((i, room_to_add, 1))
            else:  # Need to remove time
                room_to_remove = alloc - min_scene_ms
                if room_to_remove > 0:
                    adjustments.append((i, room_to_remove, -1))

        # Sort by adjustment room (largest first)
        adjustments.sort(key=lambda x: x[1], reverse=True)

        # Apply adjustments in 1000ms steps
        step = 1000 if delta > 0 else -1000
        i = 0
        while delta != 0 and i < len(adjustments):
            idx, room, direction = adjustments[i]
            if abs(step) <= room:
                clamped[idx] += step
                delta -= step
            i += 1

    log.info(f"Distributed {target_ms}ms across {len(beats)} beats: {clamped}")
    return clamped


def distribute_duration_uniform(
    num_scenes: int, target_ms: int, min_scene_ms: int = 2500, max_scene_ms: int = 12000
) -> List[int]:
    """
    Distribute target duration uniformly across scenes.

    Args:
        num_scenes: Number of scenes to distribute across
        target_ms: Target total duration in milliseconds
        min_scene_ms: Minimum scene duration in milliseconds
        max_scene_ms: Maximum scene duration in milliseconds

    Returns:
        List of scene durations in milliseconds that sum to target_ms
    """
    if num_scenes == 0:
        return []

    base_duration = target_ms // num_scenes
    remainder = target_ms % num_scenes

    # Distribute base duration
    durations = [base_duration] * num_scenes

    # Distribute remainder
    for i in range(remainder):
        durations[i] += 1

    # Clamp to bounds
    clamped = []
    for duration in durations:
        clamped.append(min(max(duration, min_scene_ms), max_scene_ms))

    # Normalize to exact target
    current_total = sum(clamped)
    delta = target_ms - current_total

    if delta != 0:
        # Simple round-robin adjustment
        i = 0
        step = 1000 if delta > 0 else -1000
        while delta != 0:
            if min_scene_ms <= clamped[i] + step <= max_scene_ms:
                clamped[i] += step
                delta -= step
            i = (i + 1) % len(clamped)

    log.info(
        f"Uniformly distributed {target_ms}ms across {num_scenes} scenes: {clamped}"
    )
    return clamped


def load_vo_cues(slug: str) -> Optional[Dict]:
    """
    Load voiceover cues for a slug if they exist.

    Args:
        slug: Content slug identifier

    Returns:
        VO cues dictionary or None if not found
    """
    vo_path = Path("data") / slug / "vo_cues.json"
    if not vo_path.exists():
        return None

    try:
        with open(vo_path, "r") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"Failed to load VO cues: {e}")
        return None


def align_scenes_to_vo(
    scenes: List[Dict],
    vo_cues: Dict,
    min_scene_ms: int = 2500,
    max_scene_ms: int = 12000,
) -> List[int]:
    """
    Align scene durations to voiceover cue windows.

    Args:
        scenes: List of scene dictionaries
        vo_cues: VO cues with scene timing information
        min_scene_ms: Minimum scene duration in milliseconds
        max_scene_ms: Maximum scene duration in milliseconds

    Returns:
        List of scene durations aligned to VO cues
    """
    if not vo_cues.get("scenes"):
        log.warning("No scene timing in VO cues")
        return []

    vo_scenes = vo_cues["scenes"]
    if len(scenes) != len(vo_scenes):
        log.warning(
            f"Scene count mismatch: {len(scenes)} scenes vs {len(vo_scenes)} VO cues"
        )
        return []

    durations = []
    for vo_scene in vo_scenes:
        start_ms = vo_scene.get("start_ms", 0)
        end_ms = vo_scene.get("end_ms", start_ms + 5000)
        duration = end_ms - start_ms

        # Clamp to bounds
        duration = min(max(duration, min_scene_ms), max_scene_ms)
        durations.append(duration)

    log.info(f"Aligned {len(scenes)} scenes to VO cues: {durations}")
    return durations


def compute_scene_durations(
    beats: List[Dict], brief: Dict, timing_config: Dict, slug: str
) -> Tuple[List[int], str, str]:
    """
    Compute scene durations using the appropriate strategy.

    Args:
        beats: List of beat dictionaries
        brief: Brief configuration
        timing_config: Timing configuration from modules.yaml
        slug: Content slug identifier

    Returns:
        Tuple of (durations_list, strategy_used, rationale)
    """
    # Get target duration from brief (with fallback)
    if brief and brief.get("video"):
        target_min = brief["video"].get("target_length_min", 1.5)
        target_max = brief["video"].get("target_length_max", target_min)
    else:
        # Default to 90 seconds (1.5 minutes) for standard content
        target_min = 1.5
        target_max = 1.5

    # Use midpoint if min != max, otherwise use the single value
    if target_min == target_max:
        target_sec = target_min
    else:
        target_sec = (target_min + target_max) / 2

    target_ms = int(target_sec * 60 * 1000)

    # Strategy 1: Use beat durations if present
    if any(beat.get("duration_ms") for beat in beats):
        durations = []
        for beat in beats:
            duration = beat.get(
                "duration_ms", timing_config.get("default_scene_ms", 5000)
            )
            durations.append(duration)

        # Clamp to bounds
        min_scene_ms = timing_config.get("min_scene_ms", 2500)
        max_scene_ms = timing_config.get("max_scene_ms", 12000)
        clamped = [min(max(d, min_scene_ms), max_scene_ms) for d in durations]

        log.info(f"[duration-policy] Using beat-defined durations: {clamped}")
        return clamped, "beat", "Used duration_ms from grounded beats"

    # Strategy 2: Align to VO cues if available and enabled
    if timing_config.get("align_to_vo", True):
        vo_cues = load_vo_cues(slug)
        if vo_cues and vo_cues.get("scenes"):
            durations = align_scenes_to_vo(
                beats,
                vo_cues,
                timing_config.get("min_scene_ms", 2500),
                timing_config.get("max_scene_ms", 12000),
            )
            if durations:
                log.info(f"[duration-policy] Aligned to VO cues: {durations}")
                return (
                    durations,
                    "vo",
                    "Aligned scene durations to voiceover cue windows",
                )

    # Strategy 3: Distribute by chosen strategy
    strategy = timing_config.get("distribute_strategy", "weighted")
    min_scene_ms = timing_config.get("min_scene_ms", 2500)
    max_scene_ms = timing_config.get("max_scene_ms", 12000)

    if strategy == "weighted":
        durations = distribute_duration_by_words(
            beats, target_ms, min_scene_ms, max_scene_ms
        )
        rationale = f"Distributed {target_ms}ms across {len(beats)} beats using word-weighted strategy"
    else:
        durations = distribute_duration_uniform(
            len(beats), target_ms, min_scene_ms, max_scene_ms
        )
        rationale = f"Distributed {target_ms}ms across {len(beats)} beats using uniform strategy"

    log.info(
        f"[duration-policy] Computed durations using {strategy} strategy: {durations}"
    )
    return durations, strategy, rationale


def validate_duration_tolerance(
    actual_ms: int, target_ms: int, tolerance_pct: float = 5.0
) -> Tuple[bool, float, str]:
    """
    Validate if actual duration is within tolerance of target.

    Args:
        actual_ms: Actual duration in milliseconds
        target_ms: Target duration in milliseconds
        tolerance_pct: Tolerance percentage (default 5.0%)

    Returns:
        Tuple of (is_valid, deviation_pct, message)
    """
    if target_ms == 0:
        return False, 0.0, "Target duration is zero"

    deviation_pct = abs(actual_ms - target_ms) / target_ms * 100
    is_valid = deviation_pct <= tolerance_pct

    if is_valid:
        message = f"Duration {actual_ms}ms is within {tolerance_pct}% of target {target_ms}ms (deviation: {deviation_pct:.1f}%)"
    else:
        message = f"Duration {actual_ms}ms exceeds {tolerance_pct}% tolerance of target {target_ms}ms (deviation: {deviation_pct:.1f}%)"

    return is_valid, deviation_pct, message
