#!/usr/bin/env python3
import os, json, time
from util import single_lock, log_state, load_global_config, BASE, ensure_dirs

def main():
    cfg = load_global_config(); ensure_dirs(cfg)
    vdir = os.path.join(BASE,"videos")
    vids = [f for f in os.listdir(vdir) if f.endswith(".mp4")]
    if not vids:
        log_state("upload_stage","SKIP","no videos"); print("No videos"); return
    vids.sort(reverse=True)
    latest = vids[0]
    queue_path = os.path.join(BASE,"data","upload_queue.json")
    queue = []
    if os.path.exists(queue_path):
        queue = json.load(open(queue_path,"r",encoding="utf-8"))
    item = {
        "file": os.path.join(vdir, latest),
        "title": latest.replace(".mp4",""),
        "description": "Auto-generated video.",
        "tags": ["education"],
        "visibility": "public"
    }
    queue.append(item)
    with open(queue_path,"w",encoding="utf-8") as f: json.dump(queue,f,indent=2)
    log_state("upload_stage","OK",latest)
    print(f"Staged {latest} for upload (metadata in upload_queue.json).")

if __name__ == "__main__":
    with single_lock():
        main()
