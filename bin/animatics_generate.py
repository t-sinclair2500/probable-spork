#!/usr/bin/env python3
"""
Animatics Renderer for Branded Animatics Pipeline

Renders each Scene from SceneScript into MP4 files using MoviePy primitives and cache.
Outputs to assets/<slug>_animatics/sN.mp4 with duration accuracy within ±3%.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import (
    BASE,
    get_logger,
    guard_system,
    load_config,
    log_state,
    single_lock,
)
from bin.cutout.sdk import (
    Paths,
    BrandStyle,
    SceneScript,
    Scene,
    Element,
    load_style,
    VIDEO_W,
    VIDEO_H,
    FPS,
)
from bin.cutout.raster_cache import rasterize_svg
from bin.cutout.anim_fx import (
    make_text_clip,
    make_image_clip,
    make_background_clip,
    apply_keyframes,
)
from bin.cutout.layout_engine import LayoutEngine
from bin.cutout.color_engine import load_palette, pick_scene_colors
from bin.cutout.motif_generators import generate_background_motif
from bin.cutout.layout_apply import auto_layout_scene, check_scene_layout_validity
from moviepy.editor import VideoClip, CompositeVideoClip

log = get_logger("animatics_generate")


def load_scenescript(slug: str) -> SceneScript:
    """Load SceneScript from file."""
    script_path = Paths.scene_script(slug)
    if not script_path.exists():
        raise FileNotFoundError(f"SceneScript not found: {script_path}")
    
    with open(script_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return SceneScript(**data)


def ensure_animatics_dir(slug: str) -> Path:
    """Ensure animatics output directory exists."""
    anim_dir = Paths.anim_dir(slug)
    anim_dir.mkdir(parents=True, exist_ok=True)
    return anim_dir


def get_background_path(bg_id: str, style: BrandStyle) -> Optional[str]:
    """Get background image path from brand assets."""
    if not bg_id:
        return None
    
    # Check brand backgrounds directory
    bg_dir = Path("assets/brand/backgrounds")
    if bg_dir.exists():
        bg_path = bg_dir / f"{bg_id}.svg"
        if bg_path.exists():
            return str(bg_path)
    
    # Check for PNG fallback
    bg_path = bg_dir / f"{bg_id}.png"
    if bg_path.exists():
        return str(bg_path)
    
    log.warning(f"Background {bg_id} not found, using default")
    return None


def rasterize_element_assets(elements: List[Element], style: BrandStyle, texture_config: Optional[Dict] = None) -> Dict[str, str]:
    """Rasterize SVG assets for elements and return path mapping with optional texture overlay."""
    asset_paths = {}
    
    # Load brand palette for texture constraints
    brand_palette = []
    try:
        from design.design_language import load_design_colors
        brand_palette = list(load_design_colors().values())
    except ImportError:
        # Fallback to style colors if available
        if hasattr(style, 'colors'):
            brand_palette = list(style.colors.values())
    
    for element in elements:
        if element.type in ["prop", "character"] and element.asset_path:
            try:
                # Rasterize SVG to PNG for MoviePy compatibility
                if element.asset_path.endswith('.svg'):
                    raster_path = rasterize_svg(
                        element.asset_path,
                        width=element.width or 200,
                        height=element.height or 200
                    )
                    if raster_path:
                        # Apply texture overlay if enabled
                        if texture_config and texture_config.get("enabled", False):
                            try:
                                from .cutout.texture_integration import process_rasterized_with_texture
                                textured_path = process_rasterized_with_texture(
                                    raster_path, texture_config, brand_palette
                                )
                                if textured_path != raster_path:
                                    asset_paths[element.id] = textured_path
                                    log.debug(f"Applied texture to {element.asset_path} -> {textured_path}")
                                else:
                                    asset_paths[element.id] = raster_path
                                    log.debug(f"Rasterized {element.asset_path} -> {raster_path}")
                            except ImportError:
                                log.warning("Texture integration not available, using untextured version")
                                asset_paths[element.id] = raster_path
                        else:
                            asset_paths[element.id] = raster_path
                            log.debug(f"Rasterized {element.asset_path} -> {raster_path}")
            except Exception as e:
                log.warning(f"Failed to rasterize {element.asset_path}: {e}")
    
    return asset_paths


def create_element_clip(
    element: Element,
    style: BrandStyle,
    asset_paths: Dict[str, str],
    scene_duration: float
) -> Optional[VideoClip]:
    """Create MoviePy clip for an element."""
    try:
        if element.type == "text":
            clip = make_text_clip(
                element.content or "",
                style,
                element.style.get("font_size", "body") if element.style else "body"
            )
        elif element.type in ["prop", "character"]:
            if element.id in asset_paths:
                clip = make_image_clip(asset_paths[element.id])
            else:
                # Fallback to placeholder
                clip = make_text_clip(f"[{element.type}]", style, "body")
        elif element.type == "shape":
            # Create simple shape placeholder
            clip = make_text_clip(f"[{element.type}]", style, "body")
        elif element.type == "list_step":
            clip = make_text_clip(f"• {element.content or ''}", style, "body")
        elif element.type == "lower_third":
            clip = make_text_clip(element.content or "", style, "lower_third")
        elif element.type == "counter":
            clip = make_text_clip(f"#{element.content or '0'}", style, "body")
        else:
            log.warning(f"Unsupported element type: {element.type}")
            return None
        
        # Set duration to scene duration
        clip = clip.set_duration(scene_duration)
        
        # Position element
        if element.x is not None and element.y is not None:
            clip = clip.set_position((element.x, element.y))
        
        # Apply keyframes if present
        if element.keyframes:
            clip = apply_keyframes(clip, element.keyframes, scene_duration)
        
        return clip
        
    except Exception as e:
        log.error(f"Failed to create clip for element {element.id}: {e}")
        return None


def render_scene(
    scene: Scene,
    style: BrandStyle,
    asset_paths: Dict[str, str],
    output_path: Path,
    vo_cues: Optional[Dict] = None,
    procedural_cfg: Optional[Dict] = None,
    palette: Optional[List[str]] = None
) -> bool:
    """Render a single scene to MP4."""
    try:
        # Check if scene needs layout and apply auto-layout if needed
        need_layout = any(("x" not in e or "y" not in e) for e in scene.elements)
        if need_layout and procedural_cfg:
            try:
                # Convert scene to dict for layout engine
                scene_dict = scene.dict() if hasattr(scene, 'dict') else scene.__dict__
                
                # Get seed for this scene
                seed = procedural_cfg.seed or 42
                scene_seed = seed + hash(scene.id) % 10000
                
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
                
                # Apply auto-layout
                scene_dict = auto_layout_scene(scene_dict, cfg_dict, scene_seed)
                
                # Update scene with positioned elements
                for i, element in enumerate(scene.elements):
                    if element.id in [e.get('id') for e in scene_dict['elements']]:
                        updated_elem = next(e for e in scene_dict['elements'] if e.get('id') == element.id)
                        if 'x' in updated_elem and 'y' in updated_elem:
                            element.x = updated_elem['x']
                            element.y = updated_elem['y']
                
                log.info(f"[layout] Auto-placed {sum(1 for e in scene.elements if 'x' in e and 'y' in e)} elements (seed={scene_seed})")
                
                # Validate layout
                if not check_scene_layout_validity(scene_dict):
                    log.warning(f"[layout] Scene {scene.id} has layout validation issues")
                
            except Exception as e:
                log.warning(f"[layout] Auto-layout failed for scene {scene.id}: {e}")
        
        scene_duration = scene.duration_ms / 1000.0  # Convert to seconds
        
        # Check for audio cue timing adjustments
        timing_adjustment = 0.0
        if vo_cues and scene.id in vo_cues:
            scene_cue_data = vo_cues[scene.id]
            if scene_cue_data.get('cues'):
                # Calculate timing adjustment based on audio cues
                # Allow ±300ms tolerance as per requirements
                tolerance_ms = 300
                scene_start_ms = scene_cue_data['scene_start_ms']
                scene_end_ms = scene_cue_data['scene_end_ms']
                
                # Check if scene timing aligns with audio cues
                expected_duration_ms = scene_end_ms - scene_start_ms
                actual_duration_ms = scene.duration_ms
                timing_diff_ms = abs(expected_duration_ms - actual_duration_ms)
                
                if timing_diff_ms > tolerance_ms:
                    log.warning(
                        f"Scene {scene.id} timing differs from audio cues by "
                        f"{timing_diff_ms}ms (tolerance: ±{tolerance_ms}ms)"
                    )
                    # Adjust scene duration to match audio cues if within reasonable bounds
                    if timing_diff_ms <= 1000:  # Allow up to 1 second adjustment
                        timing_adjustment = (expected_duration_ms - actual_duration_ms) / 1000.0
                        scene_duration += timing_adjustment
                        log.info(f"Adjusted scene {scene.id} duration by {timing_adjustment:.3f}s")
        
        # Create background clip using procedural generation
        clips = []
        if scene.bg:
            # Try procedural background first
            try:
                # Generate scene-specific colors
                scene_colors = pick_scene_colors(
                    seed=hash(scene.id) % 10000,  # Deterministic seed per scene
                    k=getattr(procedural_cfg, "max_colors_per_scene", 3)
                )
                
                # Generate procedural background
                bg_svg = generate_background_motif(
                    scene.bg, 
                    scene_colors, 
                    seed=hash(scene.id) % 10000
                )
                
                if bg_svg:
                    # Save temporary SVG and rasterize
                    temp_bg_path = f"/tmp/procedural_bg_{scene.id}.svg"
                    with open(temp_bg_path, 'w') as f:
                        f.write(bg_svg)
                    
                    bg_clip = make_background_clip(temp_bg_path, scene_duration)
                    clips.append(bg_clip)
                    log.info(f"Generated procedural background for scene {scene.id}")
                else:
                    # Fallback to brand assets
                    bg_path = get_background_path(scene.bg, style)
                    if bg_path:
                        bg_clip = make_background_clip(bg_path, scene_duration)
                        clips.append(bg_clip)
                        log.info(f"Using brand background for scene {scene.id}")
            except Exception as e:
                log.warning(f"Procedural background generation failed for scene {scene.id}: {e}")
                # Fallback to brand assets
                bg_path = get_background_path(scene.bg, style)
                if bg_path:
                    bg_clip = make_background_clip(bg_path, scene_duration)
                    clips.append(bg_clip)
        
        # Create element clips
        for element in scene.elements:
            element_clip = create_element_clip(element, style, asset_paths, scene_duration)
            if element_clip:
                clips.append(element_clip)
        
        if not clips:
            log.warning(f"No clips created for scene {scene.id}")
            return False
        
        # Compose final scene
        if len(clips) == 1:
            final_clip = clips[0]
        else:
            final_clip = CompositeVideoClip(clips, size=(VIDEO_W, VIDEO_H))
        
        # Set duration and export
        final_clip = final_clip.set_duration(scene_duration)
        
        # Export to MP4
        final_clip.write_videofile(
            str(output_path),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            verbose=False,
            logger=None
        )
        
        # Verify duration accuracy (±3%)
        actual_duration = final_clip.duration
        duration_diff = abs(actual_duration - scene_duration)
        duration_tolerance = scene_duration * 0.03
        
        if duration_diff > duration_tolerance:
            log.warning(
                f"Scene {scene.id} duration {actual_duration:.2f}s differs from "
                f"target {scene_duration:.2f}s by {duration_diff:.2f}s "
                f"(tolerance: {duration_tolerance:.2f}s)"
            )
        
        # Cleanup
        final_clip.close()
        for clip in clips:
            clip.close()
        
        log.info(f"Rendered scene {scene.id} to {output_path}")
        return True
        
    except Exception as e:
        log.error(f"Failed to render scene {scene.id}: {e}")
        return False


def render_animatics(slug: str, scene_id: Optional[str] = None) -> bool:
    """Render animatics for a slug, optionally for a specific scene."""
    try:
        # Load configuration and guard system
        cfg = load_config()
        guard_system(cfg)
        
        # Load SceneScript and brand style
        scenescript = load_scenescript(slug)
        style = load_style()
        
        # Initialize procedural engines
        cfg = load_config()
        procedural_cfg = getattr(cfg, 'procedural', {})
        layout_engine = LayoutEngine(seed=getattr(procedural_cfg, 'seed', 42))
        try:
            palette = load_palette()
            log.info(f"Loaded procedural palette with {len(palette)} colors")
        except Exception as e:
            log.warning(f"Failed to load procedural palette: {e}, using brand style colors")
            palette = list(style.colors.values()) if hasattr(style.colors, 'values') else []
        
        # Ensure output directory
        anim_dir = ensure_animatics_dir(slug)
        
        # Filter scenes if specific scene requested
        scenes_to_render = []
        if scene_id:
            scene = next((s for s in scenescript.scenes if s.id == scene_id), None)
            if not scene:
                log.error(f"Scene {scene_id} not found in {slug}")
                return False
            scenes_to_render = [scene]
        else:
            scenes_to_render = scenescript.scenes
        
        log.info(f"Rendering {len(scenes_to_render)} scenes for {slug}")
        
        # Rasterize assets for all scenes
        all_elements = []
        for scene in scenes_to_render:
            all_elements.extend(scene.elements)
        
        # Get texture configuration
        texture_config = getattr(cfg, 'textures', {})
        
        asset_paths = rasterize_element_assets(all_elements, style, texture_config)
        log.info(f"Rasterized {len(asset_paths)} assets")
        
        # Render each scene
        successful_renders = 0
        start_time = time.time()
        
        for scene in scenes_to_render:
            output_path = anim_dir / f"{scene.id}.mp4"
            
            # Check if already rendered (idempotence)
            if output_path.exists():
                log.info(f"Scene {scene.id} already rendered, skipping")
                successful_renders += 1
                continue
            
            # Load voiceover cues if available
            vo_cues = None
            vo_cues_path = os.path.join(BASE, "data", slug, "vo_cues.json")
            if os.path.exists(vo_cues_path):
                try:
                    with open(vo_cues_path, 'r', encoding='utf-8') as f:
                        vo_cues_data = json.load(f)
                        vo_cues = vo_cues_data.get('scene_cues', {})
                    log.info(f"Loaded voiceover cues for {len(vo_cues)} scenes")
                except Exception as e:
                    log.warning(f"Failed to load voiceover cues: {e}")
            
            if render_scene(scene, style, asset_paths, output_path, vo_cues, procedural_cfg, palette):
                successful_renders += 1
        
        total_time = time.time() - start_time
        log.info(
            f"Rendered {successful_renders}/{len(scenes_to_render)} scenes "
            f"in {total_time:.2f}s"
        )
        
        # Log state
        log_state(
            "animatics_generate",
            "COMPLETED" if successful_renders == len(scenes_to_render) else "PARTIAL",
            f"Rendered {successful_renders}/{len(scenes_to_render)} scenes for {slug}"
        )
        
        return successful_renders == len(scenes_to_render)
        
    except Exception as e:
        log.error(f"Failed to render animatics for {slug}: {e}")
        log_state("animatics_generate", "FAILED", str(e))
        return False


def main(brief=None, models_config=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate animatics from SceneScript")
    parser.add_argument("--slug", required=True, help="Content slug identifier")
    parser.add_argument("--scene", help="Specific scene ID to render (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        success = render_animatics(args.slug, args.scene)
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate animatics from SceneScript")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("--slug", required=True, help="Content slug identifier")
    parser.add_argument("--scene", help="Specific scene ID to render (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
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
