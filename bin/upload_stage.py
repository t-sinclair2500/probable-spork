#!/usr/bin/env python3
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from bin.core import (
    BASE,
    get_logger,
    guard_system,
    load_config,
    load_env,
    log_state,
    single_lock,
)

log = get_logger("upload_stage")

import argparse


def main(brief=None):
    """Main function for upload staging with optional brief context"""
    cfg = load_config()
    guard_system(cfg)
    env = load_env()

    # Log brief context if available
    if brief:
        brief_title = brief.get("title", "Untitled")
        log_state("upload_stage", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")
    else:
        log_state("upload_stage", "START", "brief=none")
        log.info("Running without brief - using default behavior")

    os.makedirs(os.path.join(BASE, "videos"), exist_ok=True)
    vdir = os.path.join(BASE, "videos")
    vids = [f for f in os.listdir(vdir) if f.endswith(".mp4")]
    if not vids:
        log_state("upload_stage", "SKIP", "no videos")
        return
    vids.sort(reverse=True)
    latest = vids[0]
    queue_path = os.path.join(BASE, "data", "upload_queue.json")
    queue = []
    if os.path.exists(queue_path):
        queue = json.load(open(queue_path, "r", encoding="utf-8"))
    item = {
        "file": os.path.join(vdir, latest),
        "title": latest.replace(".mp4", ""),
        "description": "Auto-generated video.",
        "tags": ["education"],
        "visibility": "public",
    }
    queue.append(item)
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
    log_state("upload_stage", "OK", latest)
    # logged via log_state; avoid prints in core pipeline


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload staging")
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
