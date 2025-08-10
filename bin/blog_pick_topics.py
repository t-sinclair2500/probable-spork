#!/usr/bin/env python3
import json
import os
import time
import argparse

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


def main(brief_data=None):
    cfg = load_config()
    bcfg = load_blog_cfg()
    
    # Log brief context if available
    if brief_data:
        log_state("blog_pick_topics", "START", f"brief={brief_data.get('title', 'Untitled')}")
    else:
        log_state("blog_pick_topics", "START", "no brief")
    
    qpath = os.path.join(BASE, "data", "topics_queue.json")
    topics = json.load(open(qpath, "r")) if os.path.exists(qpath) else []
    if not topics:
        log_state("blog_pick_topics", "SKIP", "no topics")
        print("No topics")
        return
    
    # Filter topics based on brief if available
    if brief_data:
        filtered_topics = []
        include_keywords = brief_data.get('keywords_include', [])
        exclude_keywords = brief_data.get('keywords_exclude', [])
        
        for topic in topics:
            topic_text = (topic.get("topic") or "").lower()
            topic_keywords = (topic.get("keywords") or "").lower()
            combined_text = f"{topic_text} {topic_keywords}"
            
            # Check for excluded keywords
            if any(exclude_term.lower() in combined_text for exclude_term in exclude_keywords):
                continue
            
            # Score based on include keywords
            score = 0
            for include_term in include_keywords:
                if include_term.lower() in combined_text:
                    score += 1
            
            if include_keywords:  # Only include topics that match at least one include keyword
                if score > 0:
                    filtered_topics.append((topic, score))
            else:  # If no include keywords specified, include all non-excluded topics
                filtered_topics.append((topic, 0))
        
        # Sort by score (highest first) and then by original order
        filtered_topics.sort(key=lambda x: (-x[1], topics.index(x[0])))
        topics = [item[0] for item in filtered_topics]
        
        if not topics:
            log_state("blog_pick_topics", "SKIP", "no topics match brief criteria")
            print("No topics match brief criteria")
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
    
    # Log final selection with brief context
    if brief_data:
        log_state("blog_pick_topics", "OK", f"brief={brief_data.get('title', 'Untitled')} -> {pick.get('topic', '(unknown)')}")
    else:
        log_state("blog_pick_topics", "OK", pick.get("topic", "(unknown)"))
    
    print(f"Picked topic: {pick.get('topic')} -> {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Blog topic selection")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
            # Assuming log_state is available, otherwise this line will cause an error
            # from bin.core import log  # type: ignore
            # log.info(f"Loaded brief: {brief.get('title', 'Untitled')}")
        except (json.JSONDecodeError, TypeError) as e:
            # Assuming log_state is available, otherwise this line will cause an error
            # from bin.core import log  # type: ignore
            # log.warning(f"Failed to parse brief data: {e}")
            print(f"Failed to parse brief data: {e}")
    
    with single_lock():
        main(brief)
