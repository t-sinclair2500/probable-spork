#!/usr/bin/env python3
import json
import os
import re
import argparse

from PIL import Image, ImageDraw, ImageFont

# Ensure repo root on path
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, log_state, single_lock  # noqa: E402


log = get_logger("make_thumbnail")


def safe_text(t, max_len=28):
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:max_len] + "…") if len(t) > max_len else t


def main(brief=None):
    """Main function for thumbnail generation with optional brief context"""
    cfg = load_config()
    scripts_dir = os.path.join(BASE, "scripts")
    files = [f for f in os.listdir(scripts_dir) if f.endswith(".metadata.json")]
    if not files:
        log_state("make_thumbnail", "SKIP", "no metadata")
        print("No metadata")
        return
    files.sort(reverse=True)
    meta = json.load(open(os.path.join(scripts_dir, files[0]), "r", encoding="utf-8"))
    title = safe_text(meta.get("title", "New Video"))
    out_png = os.path.join(BASE, "videos", files[0].replace(".metadata.json", ".png"))

    # Simple 1280x720 banner
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (20, 24, 35))
    d = ImageDraw.Draw(img)
    # Simple stripe
    d.rectangle([0, H - 120, W, H], fill=(255, 196, 0))
    # Title text
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 72)
    except Exception:
        font = ImageFont.load_default()
    d.text((50, H - 110), title, fill=(0, 0, 0), font=font)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    img.save(out_png, "PNG")
    log_state("make_thumbnail", "OK", os.path.basename(out_png))
    print(f"Wrote thumbnail {out_png} (placeholder).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thumbnail generation")
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
