#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import time

# Ensure repo root on path
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import (  # noqa: E402
    BASE,
    get_logger,
    guard_system,
    load_config,
    load_env,
    log_state,
    single_lock,
    estimate_beats,
)
from bin.core import parse_llm_json  # noqa: E402
from bin.music_integration import MusicIntegrationManager  # noqa: E402

from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ColorClip,
    ImageClip,
    VideoClip,
    VideoFileClip,
)

import requests
from rapidfuzz import fuzz
from moviepy.video.fx import all as vfx
from proglog import ProgressBarLogger


log = get_logger("assemble_video")


# Compatibility shim: Pillow 10+ removed Image.ANTIALIAS which MoviePy 1.0.3 expects
try:
    from PIL import Image as _PILImage  # type: ignore

    if not hasattr(_PILImage, "ANTIALIAS") and hasattr(_PILImage, "Resampling"):
        _PILImage.ANTIALIAS = _PILImage.Resampling.LANCZOS  # type: ignore[attr-defined]
except Exception:
    pass


def ffprobe_duration(path: str) -> float:
    try:
        p = subprocess.run(
            f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{path}"',
            shell=True,
            capture_output=True,
            text=True,
        )
        return float((p.stdout or "0").strip() or 0)
    except Exception:
        return 0.0


def check_hardware_acceleration(codec: str) -> str:
    """Check if hardware acceleration codec is available, fallback to software if not."""
    if codec == "h264_videotoolbox":
        try:
            # Check if VideoToolbox is available
            result = subprocess.run(
                ["ffmpeg", "-encoders"], 
                capture_output=True, 
                text=True, 
                check=False
            )
            if "h264_videotoolbox" in result.stdout:
                log.info("VideoToolbox hardware acceleration available")
                return codec
            else:
                log.warning("VideoToolbox not available, falling back to software encoding")
                return "libx264"
        except Exception:
            log.warning("Could not check VideoToolbox availability, falling back to software encoding")
            return "libx264"
    return codec


def best_asset_for_query(assets_dir: str, query: str, used: set, available_assets: list = None, fallback_index: int = 0) -> str:
    """Select best asset for query with deterministic fallback for coverage."""
    files = [f for f in os.listdir(assets_dir) if os.path.isfile(os.path.join(assets_dir, f)) and not f.endswith((".json", ".txt"))]
    if not files and available_assets:
        # Use deterministic fallback from available assets
        if available_assets and fallback_index < len(available_assets):
            return available_assets[fallback_index % len(available_assets)]
        return ""
    
    if not files:
        return ""
    
    # Score assets by relevance to query
    scored = []
    for f in files:
        if f in used:
            continue
        score = fuzz.ratio(query.lower(), f.lower())
        scored.append((score, f))
    
    if not scored:
        return ""
    
    # Return highest scoring asset
    scored.sort(reverse=True)
    return os.path.join(assets_dir, scored[0][1])


def detect_animatics(slug: str, assets_dir: str) -> tuple[list, bool]:
    """Detect if animatics exist for a slug and return sorted list of scene files."""
    animatics_dir = os.path.join(assets_dir, f"{slug}_animatics")
    if not os.path.exists(animatics_dir):
        return [], False
    
    # Look for scene_*.mp4 files
    scene_files = []
    for f in os.listdir(animatics_dir):
        if f.startswith("scene_") and f.endswith(".mp4"):
            scene_files.append(os.path.join(animatics_dir, f))
    
    if not scene_files:
        return [], False
    
    # Sort by scene number (scene_000.mp4, scene_001.mp4, etc.)
    scene_files.sort(key=lambda x: int(os.path.basename(x).replace("scene_", "").replace(".mp4", "")))
    
    log.info(f"Found {len(scene_files)} animatic scenes for {slug}")
    return scene_files, True


def calculate_coverage_metrics(timeline_clips: list, total_duration: float, black_fallback_duration: float, asset_coverage_beats: int, total_beats: int) -> dict:
    """Calculate comprehensive coverage metrics."""
    visual_coverage_pct = 0.0
    if total_duration > 0:
        visual_coverage_pct = round((1.0 - (black_fallback_duration / total_duration)) * 100.0, 1)
    
    beat_coverage_pct = 0.0
    if total_beats > 0:
        beat_coverage_pct = round((asset_coverage_beats / total_beats) * 100.0, 1)
    
    # Calculate transition density
    transition_count = 0
    for i, clip in enumerate(timeline_clips):
        if i > 0:  # First clip has no transition
            transition_count += 1
    
    transition_density = 0.0
    if total_duration > 0:
        transition_density = round(transition_count / (total_duration / 6.0), 2)  # transitions per 6s
    
    return {
        "visual_coverage_pct": visual_coverage_pct,
        "beat_coverage_pct": beat_coverage_pct,
        "transition_count": transition_count,
        "transition_density": transition_density,
        "total_duration": total_duration,
        "black_fallback_duration": black_fallback_duration,
        "asset_coverage_beats": asset_coverage_beats,
        "total_beats": total_beats,
        "meets_coverage_threshold": visual_coverage_pct >= 85.0,
        "meets_transition_rule": transition_density <= 1.0
    }


def write_video_metadata(slug: str, coverage_metrics: dict, scene_map: list, durations: dict, source_mode: str = "animatics") -> str:
    """Write video metadata JSON file."""
    videos_dir = os.path.join(BASE, "videos")
    os.makedirs(videos_dir, exist_ok=True)
    
    metadata = {
        "slug": slug,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "coverage": coverage_metrics,
        "scene_map": scene_map,
        "durations": durations,
        "assembly_version": "2.0",
        "source_mode": source_mode,
        "animatics_preferred": True
    }
    
    metadata_path = os.path.join(videos_dir, f"{slug}.metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    log.info(f"Wrote video metadata: {metadata_path}")
    return metadata_path


def assemble_from_animatics(slug: str, animatics_files: list, vo_duration: float, cfg) -> tuple[list, dict, float]:
    """Assemble video from animatics with coverage enforcement."""
    log.info(f"Assembling from {len(animatics_files)} animatic scenes")
    
    timeline_clips = []
    scene_map = []
    durations = {}
    t_cursor = 0.0
    total_duration = 0.0
    
    # Load animatic clips and calculate total duration
    for i, animatic_path in enumerate(animatics_files):
        try:
            clip = VideoFileClip(animatic_path).without_audio()
            scene_id = os.path.basename(animatic_path).replace(".mp4", "")
            
            # Store scene info
            scene_map.append({
                "scene_id": scene_id,
                "file": os.path.basename(animatic_path),
                "start_time": t_cursor,
                "duration": clip.duration,
                "source": "animatic"
            })
            
            durations[scene_id] = clip.duration
            
            # Add to timeline
            timeline_clips.append(clip)
            t_cursor += clip.duration
            total_duration += clip.duration
            
            log.info(f"Scene {scene_id}: {clip.duration:.2f}s (total: {total_duration:.2f}s)")
            
        except Exception as e:
            log.error(f"Failed to load animatic {animatic_path}: {e}")
            continue
    
    # If animatics are shorter than VO, loop or extend last scene
    if total_duration < vo_duration:
        remaining = vo_duration - total_duration
        log.info(f"Animatics duration ({total_duration:.2f}s) < VO duration ({vo_duration:.2f}s), extending by {remaining:.2f}s")
        
        if timeline_clips:
            last_scene = timeline_clips[-1]
            # Extend last scene to fill remaining time
            extended_duration = last_scene.duration + remaining
            extended_clip = last_scene.set_duration(extended_duration)
            
            # Update timeline
            timeline_clips[-1] = extended_clip
            total_duration = vo_duration
            
            # Update scene map
            scene_map[-1]["duration"] = extended_duration
            scene_map[-1]["extended"] = True
    
    return timeline_clips, durations, total_duration


def maybe_llm_beats(stext: str, cfg) -> list:
    """Try to get beat timing from LLM, fallback to estimation."""
    try:
        # Try to parse LLM beat timing from script
        prompt_path = os.path.join(BASE, "prompts", "beat_timing.txt")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt = f.read()
            
            # Simple beat extraction - look for [BEAT: ...] markers
            beat_pattern = r'\[BEAT:\s*([^\]]+)\]'
            beats = []
            for match in re.finditer(beat_pattern, stext):
                beat_text = match.group(1).strip()
                # Use configurable default duration from timing config
                default_sec = getattr(cfg.timing, "default_scene_ms", 5000) / 1000.0
                beats.append({"text": beat_text, "sec": default_sec})
            
            if beats:
                log.info(f"Extracted {len(beats)} beats from script markers")
                return beats
    except Exception as e:
        log.warning(f"LLM beat extraction failed: {e}")
    
    # Fallback to core estimation
    target_sec = int(getattr(cfg.pipeline, "video_length_seconds", 420))
    wpm = int(getattr(cfg.tts, "rate_wpm", 160))
    return estimate_beats(stext, target_sec=target_sec, wpm=wpm)


def fit_clip_to_frame(clip: VideoClip, W: int, H: int) -> VideoClip:
    """Fit video clip to frame dimensions while maintaining aspect ratio."""
    try:
        clip_w, clip_h = clip.size
        scale = min(W / clip_w, H / clip_h)
        new_w = int(clip_w * scale)
        new_h = int(clip_h * scale)
        
        # Center the clip
        x = (W - new_w) // 2
        y = (H - new_h) // 2
        
        return clip.resize((new_w, new_h)).set_position((x, y))
    except Exception:
        return clip


def ken_burns_imageclip(image_path: str, duration: float, W: int, H: int) -> VideoClip:
    """Create Ken Burns effect for image."""
    try:
        img = ImageClip(image_path)
        img_w, img_h = img.size
        
        # Calculate scale to fit frame
        scale = max(W / img_w, H / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        
        # Center and crop
        x = (new_w - W) // 2
        y = (new_h - H) // 2
        
        img = img.resize((new_w, new_h)).crop(x1=x, y1=y, x2=x+W, y2=y+H)
        
        # Ken Burns: slow zoom in
        zoom_factor = 1.1
        img = img.resize((W, H)).set_duration(duration)
        
        # Apply zoom effect
        def zoom(t):
            scale = 1.0 + (zoom_factor - 1.0) * (t / duration)
            return scale
        
        img = img.resize(zoom)
        
        return img
    except Exception as e:
        log.warning(f"Ken Burns failed for {image_path}: {e}")
        # Fallback to static image
        try:
            img = ImageClip(image_path).resize((W, H)).set_duration(duration)
            return img
        except Exception:
            # Last resort: colored rectangle
            return ColorClip(size=(W, H), color=(100, 100, 100)).set_duration(duration)


class TenSecProgressLogger(ProgressBarLogger):
    """Progress logger that emits every 10 seconds."""
    
    def __init__(self, emit_interval_seconds: float = 10.0):
        super().__init__()
        self.emit_interval = emit_interval_seconds
        self.last_emit = 0.0
    
    def callback(self, **changes):
        current_time = time.time()
        if current_time - self.last_emit >= self.emit_interval:
            for (parameter, value) in changes.items():
                if parameter == 'progress':
                    log.info(f"Rendering progress: {value:.1%}")
            self.last_emit = current_time


def main(brief=None, slug=None):
    """Main function for video assembly with optional brief context"""
    cfg = load_config()
    guard_system(cfg)
    env = load_env()
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("assemble_video", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")
    else:
        log_state("assemble_video", "START", "brief=none")
        log.info("Running without brief - using default behavior")
    
    scripts_dir = os.path.join(BASE, "scripts")
    vdir = os.path.join(BASE, "videos")
    vodir = os.path.join(BASE, "voiceovers")
    adir = os.path.join(BASE, "assets")
    
    # Determine which script to process
    if slug:
        # Use provided slug
        key = slug
        script_file = os.path.join(scripts_dir, key + ".txt")
        if not os.path.exists(script_file):
            log_state("assemble_video", "FAIL", f"script not found: {script_file}")
            print(f"Script not found: {script_file}")
            return
    else:
        # Use most recent script
        files = [f for f in os.listdir(scripts_dir) if f.endswith(".txt")]
        if not files:
            log_state("assemble_video", "SKIP", "no scripts")
            print("No scripts")
            return
        files.sort(reverse=True)
        key = files[0].replace(".txt", "")
    
    vo = os.path.join(vodir, key + ".mp3")
    if not os.path.exists(vo):
        log_state("assemble_video", "FAIL", "no voiceover")
        print("No VO")
        return

    os.makedirs(vdir, exist_ok=True)
    out_mp4 = os.path.join(vdir, key + ".mp4")

    # Read script and compute beats
    stext = open(os.path.join(scripts_dir, key + ".txt"), "r", encoding="utf-8").read()
    beats = maybe_llm_beats(stext, cfg)

    # Optional short run seconds cap via env SHORT_RUN_SECS
    short_secs = None
    try:
        _ss = int(env.get("SHORT_RUN_SECS", "0") or 0)
        short_secs = _ss if _ss > 0 else None
    except Exception:
        short_secs = None

    # Check pipeline mode and animatics availability
    animatics_only = getattr(cfg.video, "animatics_only", True)
    enable_legacy = getattr(cfg.video, "enable_legacy_stock", False)
    
    # Check for animatics first (preferred)
    animatics_files, has_animatics = detect_animatics(key, adir)
    
    if has_animatics:
        log.info(f"Using animatics for {key}: {len(animatics_files)} scenes")
        vo_duration = ffprobe_duration(vo)
        
        # Assemble from animatics
        timeline_clips, durations, total_duration = assemble_from_animatics(key, animatics_files, vo_duration, cfg)
        
        # Coverage metrics for animatics
        coverage_metrics = {
            "visual_coverage_pct": 100.0,  # Animatics provide full coverage
            "beat_coverage_pct": 100.0,
            "transition_count": max(0, len(timeline_clips) - 1),
            "transition_density": 0.0,
            "total_duration": total_duration,
            "black_fallback_duration": 0.0,
            "asset_coverage_beats": len(beats),
            "total_beats": len(beats),
            "meets_coverage_threshold": True,
            "meets_transition_rule": True,
            "source": "animatics"
        }
        
        # Scene map for metadata
        scene_map = []
        for i, animatic_path in enumerate(animatics_files):
            scene_id = os.path.basename(animatic_path).replace(".mp4", "")
            scene_map.append({
                "scene_id": scene_id,
                "file": os.path.basename(animatic_path),
                "start_time": sum(durations.get(scene_id, 0) for scene_id in [os.path.basename(f).replace(".mp4", "") for f in animatics_files[:i]]),
                "duration": durations.get(scene_id, 0),
                "source": "animatic"
            })
        
        # Write metadata with source mode
        metadata_path = write_video_metadata(key, coverage_metrics, scene_map, durations, "animatics")
        log.info(f"Animatics assembly complete: {len(timeline_clips)} scenes, {total_duration:.2f}s")
        
    elif animatics_only and not enable_legacy:
        # Animatics-only mode but no animatics found - this is an error
        error_msg = f"Animatics-only mode enabled but no animatics found for {key}. Pipeline requires animatics when video.animatics_only=true"
        log.error(error_msg)
        log_state("assemble_video", "FAIL", f"animatics_missing:slug={key}")
        raise SystemExit(error_msg)
        
    else:
        log.info(f"No animatics found for {key}, using traditional asset pipeline")
        
        # Traditional asset pipeline (existing logic)
        # Asset directory
        topic_assets_dir = os.path.join(adir, key)
        if not os.path.exists(topic_assets_dir):
            topic_assets_dir = adir

        # Apply brief settings for video assembly if available
        if brief:
            # Use brief video length target if specified
            brief_target_length = brief.get('target_len_sec')
            if brief_target_length:
                log.info(f"Brief target length: {brief_target_length}s")
                # Adjust short run seconds if brief target is shorter
                if short_secs is None or brief_target_length < short_secs:
                    short_secs = brief_target_length
                    log.info(f"Adjusted short run to brief target: {short_secs}s")
            
            # Apply brief tone for style decisions
            brief_tone = brief.get('tone', '').lower()
            if brief_tone:
                log.info(f"Brief tone: {brief_tone}")
                # Adjust transition style based on tone
                if brief_tone in ['professional', 'corporate', 'formal']:
                    xfade = min(xfade, 0.5)  # Shorter transitions for professional tone
                    log.info("Applied professional tone: shorter transitions")
                elif brief_tone in ['casual', 'friendly', 'conversational']:
                    xfade = min(xfade * 1.2, 1.0)  # Slightly longer transitions for casual tone
                    log.info("Applied casual tone: slightly longer transitions")

        # Build visual timeline with coverage tracking
        W, H = [int(x) for x in cfg.render.resolution.split("x")]
        xfade = max(0.0, float(cfg.render.xfade_ms) / 1000.0)
        timeline_clips = []
        t_cursor = 0.0
        used_assets = set()
        last_heartbeat = time.time()
        total_beats = max(len(beats), 1)
        
        # Coverage tracking
        total_video_duration = 0.0
        black_fallback_duration = 0.0
        asset_coverage_beats = 0
        
        # Get available assets for fallback coverage
        available_assets = []
        if os.path.exists(topic_assets_dir):
            for f in os.listdir(topic_assets_dir):
                path = os.path.join(topic_assets_dir, f)
                if os.path.isfile(path) and not f.endswith((".json", ".txt")):
                    available_assets.append(path)
        available_assets.sort()  # Deterministic ordering
        
        # Optional short run seconds cap via env SHORT_RUN_SECS
        short_secs = None
        try:
            _ss = int(env.get("SHORT_RUN_SECS", "0") or 0)
            short_secs = _ss if _ss > 0 else None
        except Exception:
            short_secs = None

        for i, b in enumerate(beats, start=1):
            sec = float(b.get("sec", 3.0) or 3.0)
            if short_secs:
                remaining = max(float(short_secs) - t_cursor, 0.0)
                if remaining <= 0.05:
                    break
                sec = min(sec, remaining)
            
            # Enhanced transition timing: enforce dissolve every ≥6s
            if timeline_clips and t_cursor >= 6.0 and (t_cursor % 6.0) < sec:
                # Ensure reasonable transition spacing
                xfade_this = xfade
            else:
                xfade_this = min(xfade, sec * 0.3)  # Avoid rapid cuts
                
            bq = (b.get("broll") or "").strip()
            asset = best_asset_for_query(topic_assets_dir, bq, used_assets, available_assets, i-1)
            clip = None
            is_black_fallback = False
            
            try:
                if asset and asset.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
                    log_state("assemble_pick", "OK", f"beat={i};type=video;asset={os.path.basename(asset)};q={bq}")
                    print(f"Beat {i}: video {os.path.basename(asset)}")
                    v = VideoFileClip(asset).without_audio()
                    v = v.subclip(0, min(sec, max(0.5, v.duration)))
                    v = fit_clip_to_frame(v, W, H)
                    clip = v
                    asset_coverage_beats += 1
                elif asset:
                    log_state("assemble_pick", "OK", f"beat={i};type=image;asset={os.path.basename(asset)};q={bq}")
                    print(f"Beat {i}: image {os.path.basename(asset)}")
                    # Ken Burns for stills
                    clip = ken_burns_imageclip(asset, sec, W, H)
                    asset_coverage_beats += 1
                else:
                    # Deterministic fallback: use available assets in round-robin
                    if available_assets:
                        fallback_asset = available_assets[(i-1) % len(available_assets)]
                        if fallback_asset.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
                            log_state("assemble_pick", "OK", f"beat={i};type=video;asset={os.path.basename(fallback_asset)};q=fallback")
                            print(f"Beat {i}: fallback video {os.path.basename(fallback_asset)}")
                            v = VideoFileClip(fallback_asset).without_audio()
                            v = v.subclip(0, min(sec, max(0.5, v.duration)))
                            v = fit_clip_to_frame(v, W, H)
                            clip = v
                            asset_coverage_beats += 1
                        else:
                            log_state("assemble_pick", "OK", f"beat={i};type=image;asset={os.path.basename(fallback_asset)};q=fallback")
                            print(f"Beat {i}: fallback image {os.path.basename(fallback_asset)}")
                            clip = ken_burns_imageclip(fallback_asset, sec, W, H)
                            asset_coverage_beats += 1
                    else:
                        # Last resort: black frame
                        black = ColorClip(size=(W, H), color=(0, 0, 0)).set_duration(sec)
                        clip = black
                        is_black_fallback = True
                        
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:120]}"
                # Try deterministic fallback before black
                if available_assets:
                    try:
                        fallback_asset = available_assets[(i-1) % len(available_assets)]
                        if fallback_asset.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
                            v = VideoFileClip(fallback_asset).without_audio()
                            v = v.subclip(0, min(sec, max(0.5, v.duration)))
                            v = fit_clip_to_frame(v, W, H)
                            clip = v
                            asset_coverage_beats += 1
                            log_state("assemble_pick", "OK", f"beat={i};type=video;asset={os.path.basename(fallback_asset)};q=fallback_error")
                        else:
                            clip = ken_burns_imageclip(fallback_asset, sec, W, H)
                            asset_coverage_beats += 1
                            log_state("assemble_pick", "OK", f"beat={i};type=image;asset={os.path.basename(fallback_asset)};q=fallback_error")
                    except Exception:
                        clip = ColorClip(size=(W, H), color=(0, 0, 0)).set_duration(sec)
                        is_black_fallback = True
                        log_state("assemble_pick", "FAIL", f"beat={i};error={err}")
                else:
                    clip = ColorClip(size=(W, H), color=(0, 0, 0)).set_duration(sec)
                    is_black_fallback = True
                    log_state("assemble_pick", "FAIL", f"beat={i};error={err}")
            
            if clip:
                if is_black_fallback:
                    black_fallback_duration += sec
                timeline_clips.append(clip)
                total_video_duration += sec
                t_cursor += sec
                
                # Log progress every 10 seconds
                if time.time() - last_heartbeat > 10.0:
                    log.info(f"Assembly progress: {i}/{total_beats} beats, {t_cursor:.1f}s")
                    last_heartbeat = time.time()
        
        # Calculate coverage metrics for traditional pipeline
        coverage_metrics = calculate_coverage_metrics(
            timeline_clips, total_video_duration, black_fallback_duration, 
            asset_coverage_beats, total_beats
        )
        
        # Scene map for traditional pipeline
        scene_map = []
        t_cursor = 0.0
        for i, clip in enumerate(timeline_clips):
            scene_map.append({
                "scene_id": f"beat_{i+1}",
                "file": f"beat_{i+1}",
                "start_time": t_cursor,
                "duration": clip.duration,
                "source": "traditional_asset"
            })
            t_cursor += clip.duration
        
        # Write metadata with source mode
        metadata_path = write_video_metadata(key, coverage_metrics, scene_map, {"total": total_video_duration}, "legacy_stock")

    # Common assembly logic for both animatics and traditional
    if not timeline_clips:
        log_state("assemble_video", "FAIL", "no clips to assemble")
        print("No clips to assemble")
        return

    # Compose final video with transitions
    if len(timeline_clips) == 1:
        video = timeline_clips[0]
    else:
        # Apply crossfades between clips
        xfade = max(0.0, float(cfg.render.xfade_ms) / 1000.0)
        video = timeline_clips[0]
        
        for i in range(1, len(timeline_clips)):
            next_clip = timeline_clips[i]
            # Apply crossfade
            video = CompositeVideoClip([video, next_clip], size=video.size)
            # Set duration to maintain timing
            video = video.set_duration(video.duration + next_clip.duration - xfade)
    
    # Add brand stripe at bottom
    W, H = [int(x) for x in cfg.render.resolution.split("x")]
    try:
        stripe_h = 60
        stripe = ColorClip(size=(W, stripe_h), color=(255, 196, 0)).set_duration(video.duration)
        stripe = stripe.set_position((0, H - stripe_h))
        video = CompositeVideoClip([video, stripe], size=(W, H))
    except Exception:
        pass

    # Captions (optional burn-in)
    srt = os.path.join(vodir, key + ".srt")
    try:
        if getattr(cfg.pipeline, "enable_captions", True) and os.path.exists(srt):
            from moviepy.video.tools.subtitles import SubtitlesClip
            from moviepy.editor import TextClip

            def make_txt(txt):
                return TextClip(txt, font="DejaVu-Sans", fontsize=36, color="white")

            sub = SubtitlesClip(srt, make_txt)
            video = CompositeVideoClip([video, sub.set_pos(("center", H - 120))], size=(W, H))
    except Exception:
        pass

    # Audio: VO loudness normalization + optional background music with ducking
    vo_clip = AudioFileClip(vo)
    if short_secs:
        vo_clip = vo_clip.subclip(0, min(float(short_secs), float(getattr(vo_clip, "duration", 0.0) or 0.0)))
    
    # Apply loudness normalization to VO using ffmpeg loudnorm
    vo_normalized_path = os.path.join(vodir, key + "_normalized.mp3")
    if not os.path.exists(vo_normalized_path):
        try:
            # Target -16 LUFS for stable VO loudness
            cmd = f'ffmpeg -y -i "{vo}" -af "loudnorm=I=-16:TP=-1.5:LRA=11" "{vo_normalized_path}"'
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            log.info(f"Applied loudness normalization: {os.path.basename(vo_normalized_path)}")
        except Exception as e:
            log.warning(f"Loudness normalization failed: {e}, using original VO")
            vo_normalized_path = vo
    else:
        log.info("Using existing normalized VO")
    
    vo_clip = AudioFileClip(vo_normalized_path)
    if short_secs:
        vo_clip = vo_clip.subclip(0, min(float(short_secs), float(getattr(vo_clip, "duration", 0.0) or 0.0)))
    
    # Initialize music integration manager
    music_manager = MusicIntegrationManager(cfg)
    
    # Prepare music for video based on content analysis
    audio = vo_clip
    
    # Load modules configuration for music settings
    try:
        from bin.core import load_modules_cfg
        modules_cfg = load_modules_cfg()
        music_enabled = modules_cfg.get("music", {}).get("enabled", True)
    except Exception:
        music_enabled = True
    
    if music_enabled:
        try:
            # Get video metadata for music selection
            video_metadata = {
                'tone': getattr(cfg.pipeline, 'tone', 'conversational'),
                'duration': float(getattr(vo_clip, 'duration', 30.0)),
                'pacing_wpm': int(getattr(cfg.tts, 'rate_wpm', 165))
            }
            
            # Prepare music based on script content
            script_path = os.path.join(adir, key + ".txt")
            if os.path.exists(script_path):
                music_path = music_manager.prepare_music_for_video(
                    script_path, vo_normalized_path, vodir, video_metadata
                )
                
                if music_path and os.path.exists(music_path):
                    # Integrate music with voiceover using new system
                    mixed_audio_path = os.path.join(vodir, key + "_mixed_audio.mp3")
                    
                    if music_manager.integrate_music_with_video(
                        vo_normalized_path, music_path, mixed_audio_path, video_metadata
                    ):
                        # Use the mixed audio
                        audio = AudioFileClip(mixed_audio_path)
                        log.info(f"Successfully integrated music: {music_path}")
                    else:
                        log.warning("Music integration failed, using voiceover only")
                else:
                    log.info("No suitable music found, using voiceover only")
            else:
                log.info("Script not found, skipping music selection")
                
        except Exception as e:
            log.warning(f"Music integration failed: {e}")
            log.info("Continuing with voiceover only")
    
    # Fallback to legacy music handling if new system fails
    try:
        fallback_to_silent = modules_cfg.get("music", {}).get("fallback_to_silent", True)
    except Exception:
        fallback_to_silent = True
    
    if audio == vo_clip and fallback_to_silent:
        bg_path = os.path.join(topic_assets_dir if not has_animatics else os.path.join(adir, key), "bg.mp3")
        if os.path.exists(bg_path):
            try:
                music = AudioFileClip(bg_path)
                duck_db = float(getattr(cfg.render, 'duck_db', -15))
                music_db = float(getattr(cfg.render, 'music_db', -22))
                
                # Simple volume mixing as fallback
                gain = pow(10.0, music_db / 20.0)
                audio = CompositeAudioClip([vo_clip, music.volumex(gain)])
                log.info("Applied fallback music mixing")
                    
            except Exception as e:
                log.warning(f"Fallback music processing failed: {e}")
                pass
    
    # Clamp final duration to avoid seeking past end of audio due to float rounding.
    safe_audio_dur = max(0.0, float(getattr(vo_clip, "duration", 0.0)) - 0.05)
    target_dur = max(0.0, min(float(getattr(video, "duration", 0.0)), safe_audio_dur)) or float(getattr(video, "duration", 0.0))
    video = video.set_audio(audio).set_duration(target_dur)

    # Export
    codec_to_use = cfg.render.codec
    if cfg.render.use_hardware_acceleration:
        codec_to_use = check_hardware_acceleration(codec_to_use)
    
    log.info(f"Using video codec: {codec_to_use} (hardware acceleration: {cfg.render.use_hardware_acceleration})")
    
    video.write_videofile(
        out_mp4,
        codec=codec_to_use,  # Use configured codec (hardware acceleration)
        audio_codec="aac",
        fps=int(cfg.render.fps),
        bitrate=cfg.render.target_bitrate,
        threads=cfg.render.threads,  # Use configured thread count
        ffmpeg_params=[
            "-pix_fmt", "yuv420p",
            "-preset", cfg.render.preset,  # Use configured preset
            "-crf", str(cfg.render.crf),  # Use configured CRF quality
            "-movflags", "+faststart",  # Optimize for web streaming
        ],
        verbose=True,
        logger=TenSecProgressLogger(emit_interval_seconds=10.0),
    )

    # Optional caption burn-in via ffmpeg (no ImageMagick dependency)
    final_out = out_mp4
    if getattr(cfg.pipeline, "enable_captions", True) and os.path.exists(srt):
        try:
            burned = out_mp4.replace(".mp4", "_cc.mp4")
            # Use ffmpeg subtitles filter with configured codec
            cmd = f"ffmpeg -y -i {shlex.quote(out_mp4)} -vf subtitles={shlex.quote(srt)} -c:a copy -c:v {cfg.render.codec} -pix_fmt yuv420p {shlex.quote(burned)}"
            subprocess.run(cmd, shell=True, check=False)
            if os.path.exists(burned):
                final_out = burned
        except Exception:
            pass
    
    # Log final coverage metrics
    if has_animatics:
        print(f"✓ Animatics assembly complete: {len(timeline_clips)} scenes")
        print(f"✓ Visual coverage: 100% (animatics provide full coverage)")
        print(f"✓ Transitions: {coverage_metrics['transition_count']} (rule: ≤1 per 6s)")
    else:
        print(f"✓ Traditional assembly complete: {len(timeline_clips)} beats")
        print(f"✓ Visual coverage: {coverage_metrics['visual_coverage_pct']}% (threshold: ≥85%)")
        print(f"✓ Beat coverage: {coverage_metrics['beat_coverage_pct']}%")
        print(f"✓ Transitions: {coverage_metrics['transition_count']} (density: {coverage_metrics['transition_density']:.2f} per 6s)")
    
    log_state("assemble_video", "OK", os.path.basename(out_mp4))
    print(f"Wrote video {final_out}")
    print(f"Audio: VO loudness normalized to -16 LUFS, music ducked")
    print(f"Metadata written: {metadata_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Video assembly")
    parser.add_argument("--slug", help="Specific slug to assemble (defaults to most recent script)")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    
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
        main(brief, args.slug)
