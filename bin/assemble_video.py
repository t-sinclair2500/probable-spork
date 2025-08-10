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
    
    # Prefer unused first
    candidates = [f for f in files if f not in used]
    if not candidates:
        candidates = files
    
    if not query:
        return os.path.join(assets_dir, candidates[0])
    
    # Score by fuzzy match against filename
    scored = [(f, fuzz.token_set_ratio(query, f)) for f in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return os.path.join(assets_dir, scored[0][0])


def fit_clip_to_frame(clip, W: int, H: int):
    cw, ch = clip.size
    scale = min(W / cw, H / ch)
    clip = clip.resize(scale)
    # letterbox on black
    clip = clip.on_color(size=(W, H), color=(0, 0, 0), pos=("center", "center"))
    return clip


def ken_burns_imageclip(path: str, duration: float, W: int, H: int):
    # Simple zoom over time using MoviePy's resize fx, then letterbox-fit
    base = ImageClip(path).set_duration(duration)
    # Zoom from 1.05x to ~1.15x across duration
    def zoom_factor(t: float):
        p = 0.0 if duration <= 0 else max(0.0, min(1.0, t / duration))
        return 1.05 + (1.15 - 1.05) * p

    zoomed = base.fx(vfx.resize, zoom_factor)
    fitted = fit_clip_to_frame(zoomed, W, H)
    return fitted


def maybe_llm_beats(text: str, cfg) -> list:
    try:
        prompt_path = os.path.join(BASE, "prompts", "beat_timing.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            tmpl = f.read()
        payload = {
            "model": cfg.llm.model,
            "prompt": tmpl + "\n\nSCRIPT:\n" + text,
            "stream": False,
        }
        r = requests.post(cfg.llm.endpoint, json=payload, timeout=120)
        if r.ok:
            data = parse_llm_json(r.json().get("response", "{}"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "beats" in data:
                return data["beats"]
    except Exception:
        pass
    # Fallback: estimate by words/s
    target_sec = int(getattr(cfg.pipeline, "video_length_seconds", 420))
    wpm = int(getattr(cfg.tts, "rate_wpm", 160))
    beats = estimate_beats(text, target_sec=target_sec, wpm=wpm)
    return beats


class TenSecProgressLogger(ProgressBarLogger):
    """Minimal progress logger that emits a heartbeat ~every 10s.

    MoviePy uses proglog; we subclass to periodically print overall percent.
    """

    def __init__(self, emit_interval_seconds: float = 10.0):
        super().__init__()
        self.emit_interval_seconds = emit_interval_seconds
        self._last_emit_ts = 0.0

    def bars_callback(self, bar, attr, value, old_value=None):  # type: ignore[override]
        try:
            now = time.time()
            bar_state = self.bars.get(bar) or {}
            total = float(bar_state.get("total") or 0.0) or 0.0
            index = float(bar_state.get("index") or 0.0)
            pct = 0.0 if total <= 0.0 else round((index / total) * 100.0, 1)
            if (now - self._last_emit_ts) >= self.emit_interval_seconds or (total > 0 and index >= total):
                log_state("assemble_video_progress", "OK", f"{pct}% ({bar})")
                print(f"Encoding progress: {pct}% ({bar})")
                self._last_emit_ts = now
        except Exception:
            pass


def main(brief=None):
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
            if available_assets and not is_black_fallback:
                try:
                    fallback_asset = available_assets[(i-1) % len(available_assets)]
                    if fallback_asset.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
                        v = VideoFileClip(fallback_asset).without_audio()
                        v = v.subclip(0, min(sec, max(0.5, v.duration)))
                        v = fit_clip_to_frame(v, W, H)
                        clip = v
                        log_state("assemble_pick", "OK", f"beat={i};type=video;asset={os.path.basename(fallback_asset)};q=error_fallback")
                        asset_coverage_beats += 1
                    else:
                        clip = ken_burns_imageclip(fallback_asset, sec, W, H)
                        log_state("assemble_pick", "OK", f"beat={i};type=image;asset={os.path.basename(fallback_asset)};q=error_fallback")
                        asset_coverage_beats += 1
                except Exception:
                    black = ColorClip(size=(W, H), color=(0, 0, 0)).set_duration(sec)
                    clip = black
                    is_black_fallback = True
                    log_state("assemble_pick", "WARN", f"beat={i};fallback=black;asset={os.path.basename(asset) if asset else ''};err={err}")
            else:
                black = ColorClip(size=(W, H), color=(0, 0, 0)).set_duration(sec)
                clip = black
                is_black_fallback = True
                log_state("assemble_pick", "WARN", f"beat={i};fallback=black;asset={os.path.basename(asset) if asset else ''};err={err}")
                
        # Track coverage
        total_video_duration += sec
        if is_black_fallback:
            black_fallback_duration += sec
            
        used_assets.add(os.path.basename(asset) if asset else f"black_{len(timeline_clips)}")

        if timeline_clips:
            clip = clip.set_start(t_cursor - xfade_this).crossfadein(xfade_this)
        else:
            clip = clip.set_start(t_cursor)
        t_cursor += sec
        timeline_clips.append(clip)

        # Heartbeat during timeline construction
        if (time.time() - last_heartbeat) >= 10.0 or i == total_beats:
            pct = round((i / float(total_beats)) * 100.0, 1)
            log_state("assemble_timeline_progress", "OK", f"{pct}% beats")
            print(f"Timeline build: {pct}% ({i}/{total_beats})")
            last_heartbeat = time.time()

    base_video = CompositeVideoClip(timeline_clips, size=(W, H))

    # Brand stripe overlay (optional)
    try:
        stripe_h = 60
        stripe = ColorClip(size=(W, stripe_h), color=(255, 196, 0)).set_duration(base_video.duration)
        stripe = stripe.set_position((0, H - stripe_h))
        video = CompositeVideoClip([base_video, stripe], size=(W, H))
    except Exception:
        video = base_video

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
    
    bg_path = os.path.join(topic_assets_dir, "bg.mp3")
    audio = vo_clip
    if os.path.exists(bg_path):
        try:
            music = AudioFileClip(bg_path)
            # Apply sidechain ducking: compress music when VO is present
            duck_db = float(getattr(cfg.render, 'duck_db', -15))
            music_db = float(getattr(cfg.render, 'music_db', -22))
            
            # Create ducked music track using ffmpeg's sidechaincompress
            temp_music_path = os.path.join(vodir, key + "_music_temp.mp3")
            ducked_music_path = os.path.join(vodir, key + "_music_ducked.mp3")
            
            # First normalize music duration to match VO
            music_duration = min(music.duration, vo_clip.duration)
            music.subclip(0, music_duration).write_audiofile(temp_music_path, verbose=False, logger=None)
            
            # Apply sidechain compression: duck music when VO is present
            cmd = f'ffmpeg -y -i "{temp_music_path}" -i "{vo_normalized_path}" -filter_complex "[0:a][1:a]sidechaincompress=threshold=0.1:ratio=4:attack=5:release=50[music]; [music]volume={music_db}dB[final]" -map "[final]" "{ducked_music_path}"'
            result = subprocess.run(cmd, shell=True, capture_output=True)
            
            if result.returncode == 0 and os.path.exists(ducked_music_path):
                ducked_music = AudioFileClip(ducked_music_path)
                audio = CompositeAudioClip([vo_clip, ducked_music])
                log.info(f"Applied sidechain ducking: music dB={music_db}, duck dB={duck_db}")
            else:
                # Fallback to simple volume mixing
                gain = pow(10.0, music_db / 20.0)
                audio = CompositeAudioClip([vo_clip, music.volumex(gain)])
                log.warning("Sidechain ducking failed, using simple volume mixing")
                
            # Cleanup temp files
            for temp_file in [temp_music_path, ducked_music_path]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception:
                    pass
                    
        except Exception as e:
            log.warning(f"Music processing failed: {e}")
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
    # Calculate and log coverage metrics
    visual_coverage_pct = 0.0
    if total_video_duration > 0:
        visual_coverage_pct = round((1.0 - (black_fallback_duration / total_video_duration)) * 100.0, 1)
    
    beat_coverage_pct = 0.0
    if total_beats > 0:
        beat_coverage_pct = round((asset_coverage_beats / total_beats) * 100.0, 1)
    
    # Log coverage metrics
    log_state("assemble_video_coverage", "METRIC", f"visual={visual_coverage_pct}%;beats={beat_coverage_pct}%;total_dur={total_video_duration:.1f}s;black_dur={black_fallback_duration:.1f}s")
    
    # Check if coverage meets threshold
    coverage_threshold = 85.0
    if visual_coverage_pct >= coverage_threshold:
        log_state("assemble_video_coverage", "OK", f"coverage={visual_coverage_pct}% meets threshold ≥{coverage_threshold}%")
        print(f"✓ Visual coverage: {visual_coverage_pct}% (meets ≥{coverage_threshold}% threshold)")
    else:
        log_state("assemble_video_coverage", "WARN", f"coverage={visual_coverage_pct}% below threshold ≥{coverage_threshold}%")
        print(f"⚠ Visual coverage: {visual_coverage_pct}% (below ≥{coverage_threshold}% threshold)")
    
    log_state("assemble_video", "OK", os.path.basename(out_mp4))
    print(f"Wrote video {final_out}")
    print(f"Audio: VO loudness normalized to -16 LUFS, music ducked")
    print(f"Visual: {visual_coverage_pct}% asset coverage, {beat_coverage_pct}% beats with assets")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Video assembly")
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
        main(brief)
