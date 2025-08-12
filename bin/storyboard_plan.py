#!/usr/bin/env python3
"""
Storyboard Planner - Convert grounded beats to SceneScript

Converts grounded beats + brief into a valid SceneScript, enforcing style & legibility.
Respects upstream timing data and distributes duration intelligently across scenes.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.core import get_logger, load_config, single_lock
from bin.cutout.sdk import (
    SceneScript, Scene, Element, Keyframe, BrandStyle,
    MAX_WORDS_PER_CARD, SAFE_MARGINS_PX, VIDEO_W, VIDEO_H,
    load_style, validate_scene_script, save_scene_script, Paths
)
from bin.cutout.asset_loop import run_asset_loop
from bin.cutout.qa_gates import run_all as run_qa_gates, qa_result_to_dict
from bin.cutout.layout_apply import auto_layout_scene
from bin.timing_utils import compute_scene_durations

log = get_logger("storyboard_plan")


def load_grounded_beats(slug: str) -> List[Dict]:
    """Load grounded beats from data directory."""
    beats_path = Path("data") / slug / "grounded_beats.json"
    if not beats_path.exists():
        log.error(f"Grounded beats not found: {beats_path}")
        return []
    
    try:
        with open(beats_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load grounded beats: {e}")
        return []


def load_brief() -> Dict:
    """Load brief configuration."""
    try:
        from bin.core import load_brief as core_load_brief
        return core_load_brief()
    except Exception as e:
        log.error(f"Failed to load brief config: {e}")
        return {}


def truncate_text(text: str, max_words: int = MAX_WORDS_PER_CARD) -> str:
    """Truncate text to respect MAX_WORDS_PER_CARD limit."""
    words = text.split()
    if len(words) <= max_words:
        return text
    
    truncated = " ".join(words[:max_words])
    if not truncated.endswith(('.', '!', '?')):
        truncated += "..."
    
    log.info(f"Truncated text from {len(words)} to {max_words} words: {truncated[:50]}...")
    return truncated


def create_text_element(
    content: str, 
    element_id: str, 
    x: float, 
    y: float,
    font_size: str = "body"
) -> Element:
    """Create a text element with proper styling."""
    return Element(
        id=element_id,
        type="text",
        content=truncate_text(content),
        x=x,
        y=y,
        style={
            "font_size": font_size,
            "text_align": "center",
            "max_width": VIDEO_W - (2 * SAFE_MARGINS_PX)
        }
    )


def create_scene_from_beat(
    beat: Dict, 
    scene_id: str, 
    duration_ms: int,
    brand_style: BrandStyle
) -> Scene:
    """Create a scene from a beat with appropriate elements."""
    elements = []
    
    # Create main text element
    main_text = beat.get("text", beat.get("content", "Content"))
    main_element = create_text_element(
        content=main_text,
        element_id=f"{scene_id}_main",
        x=VIDEO_W / 2,
        y=VIDEO_H / 2,
        font_size="body"
    )
    elements.append(main_element)
    
    # Add fade-in animation
    main_element.keyframes = [
        Keyframe(t=0, opacity=0.0),
        Keyframe(t=200, opacity=1.0)
    ]
    
    # Add fade-out animation
    main_element.keyframes.extend([
        Keyframe(t=duration_ms - 300, opacity=1.0),
        Keyframe(t=duration_ms, opacity=0.0)
    ])
    
    return Scene(
        id=scene_id,
        duration_ms=duration_ms,
        bg="gradient1",  # Use brand style background
        elements=elements
    )


def map_beats_to_scenes(beats: List[Dict], brief: Dict, timing_config: Dict, slug: str) -> List[Scene]:
    """Map beats to scenes with intelligent duration allocation."""
    if len(beats) == 0:
        # Fallback: create a single scene with default duration
        default_duration = timing_config.get('default_scene_ms', 5000)
        fallback_scene = Scene(
            id="fallback",
            duration_ms=default_duration,
            bg="gradient1",
            elements=[
                Element(
                    id="fallback_text",
                    type="text",
                    content="Content coming soon...",
                    x=VIDEO_W / 2,
                    y=VIDEO_H / 2
                )
            ]
        )
        return [fallback_scene]
    
    # Compute scene durations using timing utilities
    durations, strategy, rationale = compute_scene_durations(beats, brief, timing_config, slug)
    
    if not durations:
        log.error("Failed to compute scene durations")
        return []
    
    # Create scenes with computed durations
    scenes = []
    for i, (beat, duration) in enumerate(zip(beats, durations)):
        scene_id = f"scene_{i:03d}"
        scene = create_scene_from_beat(beat, scene_id, duration, None)
        scenes.append(scene)
        
        log.info(f"Scene {scene_id}: {duration}ms ({rationale})")
    
    return scenes


def create_storyboard(
    slug: str, 
    beats: List[Dict], 
    brief: Dict, 
    brand_style: BrandStyle
) -> SceneScript:
    """Create a complete SceneScript from beats and brief."""
    # Load configuration for timing settings
    try:
        from bin.core import load_modules_cfg
        timing_config = load_modules_cfg().get('timing', {})
        log.info(f"Loaded timing configuration: {timing_config}")
    except Exception as e:
        log.warning(f"Failed to load timing config: {e}, using defaults")
        timing_config = {
            'target_tolerance_pct': 5,
            'default_scene_ms': 5000,
            'min_scene_ms': 2500,
            'max_scene_ms': 30000,
            'distribute_strategy': 'weighted',
            'align_to_vo': True
        }
    
    # Map beats to scenes with proper timing
    scenes = map_beats_to_scenes(beats, brief, timing_config, slug)
    
    # Calculate compliance metrics
    total_scenes = len(scenes)
    total_duration_ms = sum(s.duration_ms for s in scenes)
    
    # Get target duration from brief
    target_min = brief.get('video', {}).get('target_length_min', 1.5)
    target_max = brief.get('video', {}).get('target_length_max', target_min)
    target_sec = target_min if target_min == target_max else (target_min + target_max) / 2
    target_ms = int(target_sec * 60 * 1000)
    
    # Check timing compliance
    timing_tolerance = timing_config.get('target_tolerance_pct', 5.0)
    deviation_pct = abs(total_duration_ms - target_ms) / target_ms * 100 if target_ms > 0 else 0
    timing_compliant = deviation_pct <= timing_tolerance
    
    log.info(f"Created {total_scenes} scenes, total duration: {total_duration_ms}ms")
    log.info(f"Target: {target_ms}ms, deviation: {deviation_pct:.1f}%, compliant: {timing_compliant}")
    
    # Count text truncations
    truncation_count = 0
    for scene in scenes:
        for element in scene.elements:
            if element.type == "text" and element.content:
                original_words = len(element.content.split())
                if original_words > MAX_WORDS_PER_CARD:
                    truncation_count += 1
    
    if truncation_count > 0:
        log.info(f"Applied {truncation_count} text truncations to respect {MAX_WORDS_PER_CARD} word limit")
    
    # Apply auto-layout to scenes that need positioning
    try:
        procedural_cfg = load_config().procedural
        seed = procedural_cfg.seed or 42
        
        layout_strategy = procedural_cfg.layout.get('strategy', 'auto') if procedural_cfg.layout else 'auto'
        if layout_strategy != 'manual':
            log.info(f"Applying auto-layout strategy: {layout_strategy} (seed: {seed})")
            
            for scene in scenes:
                # Convert scene to dict for layout engine
                scene_dict = scene.dict() if hasattr(scene, 'dict') else scene.__dict__
                
                # Check if scene needs layout
                needs_layout = any(("x" not in e or "y" not in e) for e in scene.elements)
                if needs_layout:
                    # Convert procedural_cfg to dict for layout engine
                    cfg_dict = {
                        "procedural": {
                            "seed": procedural_cfg.seed,
                            "placement": {
                                "min_spacing_px": getattr(procedural_cfg.placement, 'min_spacing_px', 64) if procedural_cfg.placement else 64,
                                "safe_margin_px": getattr(procedural_cfg.placement, 'safe_margin_px', 40) if procedural_cfg.placement else 40
                            },
                            "layout": {
                                "strategy": getattr(procedural_cfg.layout, 'strategy', 'auto') if procedural_cfg.layout else 'auto',
                                "prefer_thirds": getattr(procedural_cfg.layout, 'prefer_thirds', True) if procedural_cfg.layout else True,
                                "max_attempts": getattr(procedural_cfg.layout, 'max_attempts', 200) if procedural_cfg.layout else 200
                            }
                        }
                    }
                    
                    scene_dict = auto_layout_scene(scene_dict, cfg_dict, seed + hash(scene.id) % 10000)
                    
                    # Update scene with positioned elements
                    for i, element in enumerate(scene.elements):
                        if element.id in [e.get('id') for e in scene_dict['elements']]:
                            updated_elem = next(e for e in scene_dict['elements'] if e.get('id') == element.id)
                            if 'x' in updated_elem and 'y' in updated_elem:
                                element.x = updated_elem['x']
                                element.y = updated_elem['y']
                                log.debug(f"[layout] Auto-positioned element {element.id} to ({element.x}, {element.y})")
                    
                    log.info(f"[layout] Applied auto-layout to scene {scene.id}")
        else:
            log.info("Manual layout mode - skipping auto-positioning")
    except Exception as e:
        log.warning(f"Auto-layout failed: {e}, scenes will use default positioning")
    
    return SceneScript(
        slug=slug,
        fps=30,
        scenes=scenes,
        metadata={
            "total_scenes": total_scenes,
            "total_duration_ms": total_duration_ms,
            "target_duration_ms": target_ms,
            "deviation_pct": round(deviation_pct, 2),
            "timing_compliant": timing_compliant,
            "timing_tolerance_pct": timing_tolerance,
            "truncation_count": truncation_count
        }
    )


def main(brief=None, models_config=None):
    """Main entry point for storyboard planning."""
    parser = argparse.ArgumentParser(description="Convert grounded beats to SceneScript")
    parser.add_argument("--slug", required=True, help="Content slug identifier")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    args = parser.parse_args()
    
    log.info(f"Starting storyboard planning for slug: {args.slug}")
    
    # Load inputs
    beats = load_grounded_beats(args.slug)
    if not beats:
        log.error("No grounded beats found, exiting")
        sys.exit(1)
    
    brief = load_brief()
    if not brief:
        log.warning("No brief config found, using defaults")
        brief = {"video": {"target_length_max": 7}}
    
    try:
        brand_style = load_style()
        log.info("Loaded brand style configuration")
    except Exception as e:
        log.warning(f"Failed to load brand style: {e}, using defaults")
        brand_style = BrandStyle(
            colors={"primary": "#2563eb"},
            fonts={"primary": "Inter"},
            font_sizes={"hook": 48, "body": 24, "lower_third": 32}
        )
    
    # Get seed for deterministic asset generation
    try:
        from bin.core import load_config
        cfg = load_config()
        seed = getattr(cfg.procedural, 'seed', 42) if hasattr(cfg, 'procedural') else 42
    except Exception as e:
        log.warning(f"Failed to load config for seed: {e}, using default seed 42")
        seed = 42
    
    # Create storyboard
    storyboard = create_storyboard(args.slug, beats, brief, brand_style)
    
    # Validate against schema
    try:
        validate_scene_script(storyboard)
        log.info("SceneScript validation passed")
    except Exception as e:
        log.error(f"SceneScript validation failed: {e}")
        sys.exit(1)
    
    if args.dry_run:
        log.info("Dry run mode - SceneScript validated successfully")
        return
    
    # Run QA gates
    qa_results = []
    palette = brand_style.colors.values() if hasattr(brand_style.colors, 'values') else list(brand_style.colors.values())
    
    for scene in storyboard.scenes:
        # Convert scene to dict for QA gates
        scene_dict = scene.dict() if hasattr(scene, 'dict') else scene.__dict__
        scenes_meta = [{"duration_ms": s.duration_ms} for s in storyboard.scenes]
        
        scene_qa = run_qa_gates(scene_dict, scenes_meta, palette)
        qa_results.append(scene_qa)
        
        if not scene_qa.ok:
            log.warning(f"QA issues in scene: {scene_qa.fails}")
    
    # Log QA summary
    total_qa_issues = sum(1 for r in qa_results if not r.ok)
    log.info(f"QA Gates completed: {len(qa_results)} scenes checked, {total_qa_issues} with issues")

    # Run asset loop to ensure 100% asset coverage
    log.info("Starting asset loop to ensure complete asset coverage...")
    try:
        updated_storyboard, coverage_results = run_asset_loop(args.slug, storyboard, brand_style, seed=42)
        
        if coverage_results["is_fully_covered"]:
            log.info("Asset loop completed successfully - 100% coverage achieved")
            storyboard = updated_storyboard
        else:
            log.warning(f"Asset loop completed with {coverage_results['coverage_pct']:.1f}% coverage")
            # Continue with partial coverage - assets will be generated during rendering
        
        log.info(f"Asset coverage: {coverage_results['covered_requirements']}/{coverage_results['total_requirements']} ({coverage_results['coverage_pct']:.1f}%)")
        
    except Exception as e:
        log.error(f"Asset loop failed: {e}")
        log.warning("Continuing with original storyboard - assets will be generated during rendering")

    # Save to scenescripts directory
    output_path = Path("scenescripts") / f"{args.slug}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        save_scene_script(storyboard, output_path)
        log.info(f"SceneScript saved to: {output_path}")
    except Exception as e:
        log.error(f"Failed to save SceneScript: {e}")
        sys.exit(1)
    
    log.info("Storyboard planning completed successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert grounded beats to SceneScript")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("--slug", required=True, help="Content slug identifier")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
            log.info(f"Loaded brief: {brief.get('title', 'Untitled')}")
        except (json.JSONDecodeError, TypeError) as e:
            log.warning(f"Failed to parse brief data: {e}")
    
    with single_lock():
        main(brief, models_config=None)  # models_config not passed via CLI
