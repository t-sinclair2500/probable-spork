#!/usr/bin/env python3
import os, json, time
from bin.util import single_lock, log_state, load_global_config, BASE, ensure_dirs

def load_blog_cfg():
    p = os.path.join(BASE, "conf", "blog.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "blog.example.yaml")
    import yaml
    return yaml.safe_load(open(p, "r", encoding="utf-8"))

def main():
    cfg = load_global_config(); ensure_dirs(cfg)
    bcfg = load_blog_cfg()
    qpath = os.path.join(BASE,"data","topics_queue.json")
    topics = json.load(open(qpath,"r")) if os.path.exists(qpath) else []
    if not topics:
        log_state("blog_pick_topics","SKIP","no topics"); print("No topics"); return
    # very simple: pick first topic not used in last N days
    pick = topics[0]
    work_dir = os.path.join(BASE, "data", "cache")
    os.makedirs(work_dir, exist_ok=True)
    out = os.path.join(work_dir, "blog_topic.json")
    json.dump(pick, open(out,"w",encoding="utf-8"), indent=2)
    log_state("blog_pick_topics","OK", pick.get("topic","(unknown)"))
    print(f"Picked topic: {pick.get('topic')} -> {out}")

if __name__ == "__main__":
    with single_lock():
        main()
