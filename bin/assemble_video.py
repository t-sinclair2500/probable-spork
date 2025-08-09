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
    VideoFileClip,
)

import requests
from rapidfuzz import fuzz


log = get_logger("assemble_video")


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
    # Simple zoom & pan over time without ImageMagick
    img = ImageClip(path)
    iw, ih = img.size
    # Start/End scales (slight zoom)
    start_scale = 1.05
    end_scale = 1.15
    # Compute scaled sizes
    def make_frame(t):
        # progress 0..1
        p = max(0.0, min(1.0, t / max(duration, 0.01)))
        scale = start_scale + (end_scale - start_scale) * p
        w = int(iw * scale)
        h = int(ih * scale)
        frame = img.resize((w, h)).get_frame(0)
        # Pan from left-top to center
        x = int((w - W) * p * 0.5)
        y = int((h - H) * p * 0.5)
        x = max(0, min(x, max(0, w - W)))
        y = max(0, min(y, max(0, h - H)))
        sub = frame[y : y + H, x : x + W]
        return sub

    kb = ImageClip(make_frame, duration=duration)
    return kb


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


def main():
    cfg = load_config()
    guard_system(cfg)
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
    for b in beats:
        sec = float(b.get("sec", 3.0) or 3.0)
        bq = (b.get("broll") or "").strip()
        asset = best_asset_for_query(topic_assets_dir, bq, used_assets)
        clip = None
        try:
            if asset and asset.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
                v = VideoFileClip(os.path.join(topic_assets_dir, os.path.basename(asset))).without_audio()
                v = v.subclip(0, min(sec, max(0.5, v.duration)))
                v = fit_clip_to_frame(v, W, H)
                clip = v
            elif asset:
                img_path = os.path.join(topic_assets_dir, os.path.basename(asset))
                # Ken Burns for stills
                clip = ken_burns_imageclip(img_path, sec, W, H)
            else:
                # Fallback: black frame
                black = ImageClip(color=(0, 0, 0), size=(W, H)).set_duration(sec)
                clip = black
        except Exception:
            black = ImageClip(color=(0, 0, 0), size=(W, H)).set_duration(sec)
            clip = black
        used_assets.add(os.path.basename(asset) if asset else f"black_{len(timeline_clips)}")

        if timeline_clips:
            clip = clip.set_start(t_cursor - xfade).crossfadein(xfade)
        else:
            clip = clip.set_start(t_cursor)
        t_cursor += sec
        timeline_clips.append(clip)

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
    video = video.set_audio(audio).set_duration(max(vo_clip.duration, video.duration))

    # Export
    video.write_videofile(
        out_mp4,
        codec="libx264",
        audio_codec="aac",
        fps=int(cfg.render.fps),
        bitrate=cfg.render.target_bitrate,
        threads=2,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
        verbose=False,
        logger=None,
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
