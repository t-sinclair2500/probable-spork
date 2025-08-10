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
    
    # Log brief context if available
    if brief:
        log_state("make_thumbnail", "START", f"brief={brief.get('title', 'Untitled')}")
    else:
        log_state("make_thumbnail", "START", "no brief")
    
    scripts_dir = os.path.join(BASE, "scripts")
    files = [f for f in os.listdir(scripts_dir) if f.endswith(".metadata.json")]
    if not files:
        log_state("make_thumbnail", "SKIP", "no metadata")
        print("No metadata")
        return
    files.sort(reverse=True)
    meta = json.load(open(os.path.join(scripts_dir, files[0]), "r", encoding="utf-8"))
    
    # Apply brief settings to title if available
    title = meta.get("title", "New Video")
    if brief:
        # Enhance title with brief keywords if available
        brief_keywords = brief.get('keywords_include', [])
        if brief_keywords:
            # Add primary brief keyword to title if not already present
            primary_keyword = brief_keywords[0]
            if primary_keyword.lower() not in title.lower():
                title = f"{title} - {primary_keyword}"
                log.info(f"Enhanced title with brief keyword: {primary_keyword}")
    
    title = safe_text(title, max_len=28)
    out_png = os.path.join(BASE, "videos", files[0].replace(".metadata.json", ".png"))

    # Apply brief tone for visual style if available
    color_scheme = (20, 24, 35)  # Default dark blue
    accent_color = (255, 196, 0)  # Default yellow
    
    if brief:
        brief_tone = brief.get('tone', '').lower()
        if brief_tone:
            log.info(f"Brief tone: {brief_tone}")
            # Adjust color scheme based on tone
            if brief_tone in ['professional', 'corporate', 'formal']:
                color_scheme = (15, 20, 30)  # Darker, more professional
                accent_color = (0, 120, 215)  # Professional blue
                log.info("Applied professional tone: darker colors, blue accent")
            elif brief_tone in ['casual', 'friendly', 'conversational']:
                color_scheme = (25, 30, 40)  # Lighter, warmer
                accent_color = (255, 140, 0)  # Friendly orange
                log.info("Applied casual tone: warmer colors, orange accent")
            elif brief_tone in ['energetic', 'enthusiastic', 'motivational']:
                color_scheme = (30, 20, 40)  # Vibrant purple
                accent_color = (255, 50, 100)  # Energetic pink
                log.info("Applied energetic tone: vibrant colors, pink accent")

    # Simple 1280x720 banner
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), color_scheme)
    d = ImageDraw.Draw(img)
    # Simple stripe with tone-based color
    d.rectangle([0, H - 120, W, H], fill=accent_color)
    # Title text
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 72)
    except Exception:
        font = ImageFont.load_default()
    d.text((50, H - 110), title, fill=(0, 0, 0), font=font)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    img.save(out_png, "PNG")
    
    # Log final result with brief context
    if brief:
        log_state("make_thumbnail", "OK", f"brief={brief.get('title', 'Untitled')} -> {os.path.basename(out_png)}")
    else:
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
