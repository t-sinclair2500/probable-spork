#!/usr/bin/env python3
import json
import os
import re
import sqlite3
import time

import requests
import sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from bin.core import BASE, load_config, log_state, single_lock

try:
    from bin.core import parse_llm_json  # when repo root is on sys.path
except Exception:
    # Fallback: local parser identical to bin.core.parse_llm_json
    def parse_llm_json(text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.DOTALL)
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if m:
                return json.loads(m.group(0))
            raise ValueError("No JSON object found in LLM output.")


def call_ollama(prompt, cfg):
    url = cfg["llm"]["endpoint"]
    model = cfg["llm"]["model"]
    payload = {"model": model, "prompt": prompt, "stream": False}
    r = requests.post(url, json=payload, timeout=600)
    r.raise_for_status()
    # Ollama returns {"response": "..."} with the text
    return r.json().get("response", "")


def main():
    cfg = load_config()
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    # Collect recent titles/tags from sqlite
    db_path = os.path.join(BASE, "data", "trending_topics.db")
    rows = []
    if os.path.exists(db_path):
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        for ts, source, title, tags in cur.execute(
            "SELECT ts, source, title, tags FROM trends ORDER BY rowid DESC LIMIT 50"
        ):
            rows.append({"title": title, "tags": tags, "source": source})
        con.close()
    # Build prompt
    with open(os.path.join(BASE, "prompts", "cluster_topics.txt"), "r", encoding="utf-8") as f:
        template = f.read()
    prompt = template + "\nINPUT:\n" + json.dumps(rows)
    # Call local LLM
    topics = []
    try:
        out = call_ollama(prompt, cfg)
        parsed = parse_llm_json(out)
        topics = parsed.get("topics", [])
    except Exception:
        topics = [
            {
                "topic": "ai tools",
                "score": 0.6,
                "hook": "5 AI tools to save hours",
                "keywords": ["ai", "tools"],
            },
            {
                "topic": "space trivia",
                "score": 0.5,
                "hook": "10 wild space facts",
                "keywords": ["space", "trivia"],
            },
        ]
    # Enrich with created_at and clamp to top 10 by score
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for t in topics:
        t.setdefault("score", 0.5)
        t.setdefault("keywords", [])
        t["created_at"] = now
    topics.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    topics = topics[:10]
    # Save queue
    queue_path = os.path.join(BASE, "data", "topics_queue.json")
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=2)
    log_state("llm_cluster", "OK", f"topics={len(topics)}")
    print(f"Wrote {queue_path}")


if __name__ == "__main__":
    with single_lock():
        main()
