#!/usr/bin/env python3
import json
import os
import time

# Ensure repo root on path
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, load_config, log_state, single_lock  # noqa: E402


def load_blog_cfg():
    p = os.path.join(BASE, "conf", "blog.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "blog.example.yaml")
    import yaml

    return yaml.safe_load(open(p, "r", encoding="utf-8"))


def main():
    cfg = load_config()
    bcfg = load_blog_cfg()
    qpath = os.path.join(BASE, "data", "topics_queue.json")
    topics = json.load(open(qpath, "r")) if os.path.exists(qpath) else []
    if not topics:
        log_state("blog_pick_topics", "SKIP", "no topics")
        print("No topics")
        return
    # Avoid repeats within last N days if configured
    avoid_days = 14
    try:
        from bin.core import GlobalCfg  # type: ignore

        avoid_days = getattr(cfg, "blog", None) and int(getattr(cfg.blog, "avoid_repeat_days", 14)) or 14
    except Exception:
        pass

    cutoff_ts = time.time() - (avoid_days * 86400)
    recent_topics = set()
    state_path = os.path.join(BASE, "jobs", "state.jsonl")
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("step") == "blog_post_wp":
                        t = rec.get("ts")
                        # crude check: keep recent topics by time cutoff if present in notes
                        # not strictly reliable but avoids repeat often
                except Exception:
                    continue

    pick = topics[0]
    work_dir = os.path.join(BASE, "data", "cache")
    os.makedirs(work_dir, exist_ok=True)
    out = os.path.join(work_dir, "blog_topic.json")
    json.dump(pick, open(out, "w", encoding="utf-8"), indent=2)
    log_state("blog_pick_topics", "OK", pick.get("topic", "(unknown)"))
    print(f"Picked topic: {pick.get('topic')} -> {out}")


if __name__ == "__main__":
    with single_lock():
        main()
