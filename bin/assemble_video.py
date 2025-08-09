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


def best_asset_for_query(assets_dir: str, query: str, used: set) -> str:
    files = [f for f in os.listdir(assets_dir) if os.path.isfile(os.path.join(assets_dir, f)) and not f.endswith((".json", ".txt"))]
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


def main():
    cfg = load_config()
    guard_system(cfg)
    env = load_env()
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

    # Build visual timeline
    W, H = [int(x) for x in cfg.render.resolution.split("x")]
    xfade = max(0.0, float(cfg.render.xfade_ms) / 1000.0)
    timeline_clips = []
    t_cursor = 0.0
    used_assets = set()
    last_heartbeat = time.time()
    total_beats = max(len(beats), 1)
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
        bq = (b.get("broll") or "").strip()
        asset = best_asset_for_query(topic_assets_dir, bq, used_assets)
        clip = None
        try:
            if asset and asset.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
                log_state("assemble_pick", "OK", f"beat={i};type=video;asset={os.path.basename(asset)};q={bq}")
                print(f"Beat {i}: video {os.path.basename(asset)}")
                v = VideoFileClip(asset).without_audio()
                v = v.subclip(0, min(sec, max(0.5, v.duration)))
                v = fit_clip_to_frame(v, W, H)
                clip = v
            elif asset:
                log_state("assemble_pick", "OK", f"beat={i};type=image;asset={os.path.basename(asset)};q={bq}")
                print(f"Beat {i}: image {os.path.basename(asset)}")
                # Ken Burns for stills
                clip = ken_burns_imageclip(asset, sec, W, H)
            else:
                # Fallback: black frame
                black = ColorClip(size=(W, H), color=(0, 0, 0)).set_duration(sec)
                clip = black
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:120]}"
            log_state("assemble_pick", "WARN", f"beat={i};fallback=black;asset={os.path.basename(asset) if asset else ''};err={err}")
            print(f"Beat {i}: fallback black ({err})")
            black = ColorClip(size=(W, H), color=(0, 0, 0)).set_duration(sec)
            clip = black
        used_assets.add(os.path.basename(asset) if asset else f"black_{len(timeline_clips)}")

        if timeline_clips:
            clip = clip.set_start(t_cursor - xfade).crossfadein(xfade)
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

    # Audio: VO + optional background music
    vo_clip = AudioFileClip(vo)
    if short_secs:
        vo_clip = vo_clip.subclip(0, min(float(short_secs), float(getattr(vo_clip, "duration", 0.0) or 0.0)))
    bg_path = os.path.join(topic_assets_dir, "bg.mp3")
    audio = vo_clip
    if os.path.exists(bg_path):
        try:
            music = AudioFileClip(bg_path)
            # Convert dB to linear gain
            gain = pow(10.0, float(cfg.render.music_db) / 20.0)
            audio = CompositeAudioClip([vo_clip, music.volumex(gain)])
        except Exception:
            pass
    # Clamp final duration to avoid seeking past end of audio due to float rounding.
    safe_audio_dur = max(0.0, float(getattr(vo_clip, "duration", 0.0)) - 0.05)
    target_dur = max(0.0, min(float(getattr(video, "duration", 0.0)), safe_audio_dur)) or float(getattr(video, "duration", 0.0))
    video = video.set_audio(audio).set_duration(target_dur)

    # Export
    video.write_videofile(
        out_mp4,
        codec="libx264",
        audio_codec="aac",
        fps=int(cfg.render.fps),
        bitrate=cfg.render.target_bitrate,
        threads=2,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
        verbose=True,
        logger=TenSecProgressLogger(emit_interval_seconds=10.0),
    )

    # Optional caption burn-in via ffmpeg (no ImageMagick dependency)
    final_out = out_mp4
    if getattr(cfg.pipeline, "enable_captions", True) and os.path.exists(srt):
        try:
            burned = out_mp4.replace(".mp4", "_cc.mp4")
            # Use ffmpeg subtitles filter
            cmd = f"ffmpeg -y -i {shlex.quote(out_mp4)} -vf subtitles={shlex.quote(srt)} -c:a copy -c:v libx264 -pix_fmt yuv420p {shlex.quote(burned)}"
            subprocess.run(cmd, shell=True, check=False)
            if os.path.exists(burned):
                final_out = burned
        except Exception:
            pass
    log_state("assemble_video", "OK", os.path.basename(out_mp4))
    print(f"Wrote video {final_out}")


if __name__ == "__main__":
    with single_lock():
        main()
