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

    cutoff = time.time() - (avoid_days * 86400)
    recent = set()
    ledger_path = os.path.join(BASE, "data", "recent_blog_topics.json")
    if os.path.exists(ledger_path):
        try:
            recent_data = json.load(open(ledger_path, "r", encoding="utf-8"))
            for item in recent_data:
                if float(item.get("ts", 0)) >= cutoff:
                    recent.add(item.get("topic", "").strip().lower())
        except Exception:
            recent = set()

    pick = None
    for cand in topics:
        t = (cand.get("topic") or "").strip().lower()
        if t and t not in recent:
            pick = cand
            break
    pick = pick or topics[0]
    work_dir = os.path.join(BASE, "data", "cache")
    os.makedirs(work_dir, exist_ok=True)
    out = os.path.join(work_dir, "blog_topic.json")
    json.dump(pick, open(out, "w", encoding="utf-8"), indent=2)
    # Append to recent ledger
    try:
        data = []
        if os.path.exists(ledger_path):
            data = json.load(open(ledger_path, "r", encoding="utf-8"))
        data.append({"ts": time.time(), "topic": pick.get("topic", "")})
        json.dump(data[-100:], open(ledger_path, "w", encoding="utf-8"), indent=2)
    except Exception:
        pass
    log_state("blog_pick_topics", "OK", pick.get("topic", "(unknown)"))
    print(f"Picked topic: {pick.get('topic')} -> {out}")


if __name__ == "__main__":
    with single_lock():
        main()
