#!/usr/bin/env python3
import json
import os
import re
import time

from util import BASE, ensure_dirs, load_global_config, log_state, single_lock


def main():
    cfg = load_global_config()
    ensure_dirs(cfg)
    scripts_dir = os.path.join(BASE, "scripts")
    vdir = os.path.join(BASE, "videos")
    vodir = os.path.join(BASE, "voiceovers")
    assets_dir = os.path.join(BASE, "assets")
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
    # Minimal black-slide + audio video to keep pipeline working
    os.makedirs(vdir, exist_ok=True)
    out_mp4 = os.path.join(vdir, key + ".mp4")
    # Use ffmpeg to produce a 1920x1080 black video matching audio length
    import subprocess

    probe = subprocess.run(
        f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{vo}"',
        shell=True,
        capture_output=True,
        text=True,
    )
    dur = float(probe.stdout.strip() or 3.0)
    # Add simple background music ducking if a music file exists under assets/<topic>/bg.mp3
    music = os.path.join(assets_dir, "bg.mp3")
    if os.path.exists(music):
        cmd = (
            f'ffmpeg -f lavfi -i color=c=black:s={cfg["render"]["resolution"]}:r={cfg["render"]["fps"]} '
            f'-stream_loop -1 -i "{music}" -i "{vo}" '
            f'-filter_complex "[1:a]volume=1.0[a1];[0:a]anull[a0];[a1][2:a]sidechaincompress=threshold=0.015:ratio=8:attack=5:release=100:makeup=3[mix]" '
            f'-map 0:v -map "[mix]" -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac -b:v {cfg["render"]["target_bitrate"]} -y "{out_mp4}"'
        )
    else:
        cmd = f'ffmpeg -f lavfi -i color=c=black:s={cfg["render"]["resolution"]}:r={cfg["render"]["fps"]} -i "{vo}" -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac -b:v {cfg["render"]["target_bitrate"]} -y "{out_mp4}"'
    subprocess.run(cmd, shell=True, check=True)
    log_state("assemble_video", "OK", os.path.basename(out_mp4))
    print(f"Wrote minimal video {out_mp4}. Replace with full MoviePy assembly in Phase 2.")


if __name__ == "__main__":
    with single_lock():
        main()
