#!/usr/bin/env python3
import json
import os
import time

import sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from bin.core import BASE, load_config, log_state, single_lock


def main():
    cfg = load_config()
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
    with single_lock():
        main()
