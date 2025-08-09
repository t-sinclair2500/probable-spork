#!/usr/bin/env python3
import json
import os
import re
import time

import requests
from util import BASE, ensure_dirs, load_global_config, log_state, single_lock


def call_ollama(prompt, cfg):
    url = cfg["llm"]["endpoint"]
    model = cfg["llm"]["model"]
    payload = {"model": model, "prompt": prompt, "stream": False}
    r = requests.post(url, json=payload, timeout=1200)
    r.raise_for_status()
    return r.json().get("response", "")


def main():
    cfg = load_global_config()
    ensure_dirs(cfg)
    qpath = os.path.join(BASE, "data", "topics_queue.json")
    topics = json.load(open(qpath, "r")) if os.path.exists(qpath) else []
    topic = topics[0]["topic"] if topics else "AI tools that save time"
    seed_keywords = topics[0].get("keywords") if topics else ["ai", "productivity"]
    with open(os.path.join(BASE, "prompts", "outline.txt"), "r", encoding="utf-8") as f:
        template = f.read()
    # Include tone and target duration hints from config to steer the outline
    tone = cfg.get("pipeline", {}).get("tone", "informative")
    target_len_sec = int(cfg.get("pipeline", {}).get("video_length_seconds", 420))
    prompt = (
        template.replace("{topic}", topic).replace("{seed_keywords}", ", ".join(seed_keywords))
        + f"\nTone: {tone}. Target length (sec): {target_len_sec}."
    )
    try:
        out = call_ollama(prompt, cfg)
        data = json.loads(out)
    except Exception:
        data = {
            "title_options": [f"{topic}: 5 Quick Tips"],
            "sections": [
                {
                    "id": 1,
                    "label": "Hook",
                    "beats": ["Big promise", "Why watch"],
                    "broll": ["typing", "clock"],
                },
                {"id": 2, "label": "Point 1", "beats": ["Tip 1"], "broll": ["keyboard"]},
                {"id": 3, "label": "Point 2", "beats": ["Tip 2"], "broll": ["monitor"]},
                {"id": 4, "label": "Point 3", "beats": ["Tip 3"], "broll": ["notebook"]},
                {"id": 5, "label": "Recap", "beats": ["Summary"], "broll": ["checklist"]},
                {"id": 6, "label": "CTA", "beats": ["Subscribe"], "broll": ["subscribe button"]},
            ],
            "tags": ["ai", "productivity"],
            "tone": tone,
            "target_len_sec": target_len_sec,
        }
    date_tag = time.strftime("%Y-%m-%d")
    outline_path = os.path.join(
        BASE, "scripts", f"{date_tag}_{re.sub(r'[^a-z0-9]+','-',topic.lower())}.outline.json"
    )
    with open(outline_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log_state("llm_outline", "OK", os.path.basename(outline_path))
    print(f"Wrote outline {outline_path}")


if __name__ == "__main__":
    with single_lock():
        main()
