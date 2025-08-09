#!/usr/bin/env python3
import json
import os
import subprocess
import time

from flask import Flask, jsonify, request

from bin.core import BASE

app = Flask(__name__)


def tail(path, n=200):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    return "\n".join(lines[-n:])


@app.get("/api/state")
def api_state():
    p = os.path.join(BASE, "jobs", "state.jsonl")
    lines = []
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            lines = [json.loads(x) for x in f.read().splitlines() if x.strip()]
    return jsonify({"count": len(lines), "last": (lines[-1] if lines else {})})


@app.get("/api/topics")
def api_topics():
    p = os.path.join(BASE, "data", "topics_queue.json")
    arr = []
    if os.path.exists(p):
        arr = json.load(open(p, "r", encoding="utf-8"))
    return jsonify(arr)


@app.get("/api/logs")
def api_logs():
    p = os.path.join(BASE, "logs", "pipeline.log")
    return jsonify({"tail": tail(p, 200)})


@app.post("/api/run")
def api_run():
    step = request.args.get("step", "")
    mapping = {
        "fetch_trends": "bin/niche_trends.py",
        "cluster": "bin/llm_cluster.py",
        "outline": "bin/llm_outline.py",
        "script": "bin/llm_script.py",
        "assets": "bin/fetch_assets.py",
        "tts": "bin/tts_generate.py",
        "captions": "bin/generate_captions.py",
        "assemble": "bin/assemble_video.py",
        "stage": "bin/upload_stage.py",
        "blog_pick": "bin/blog_pick_topics.py",
        "blog_gen": "bin/blog_generate_post.py",
        "blog_render": "bin/blog_render_html.py",
        "blog_post": "bin/blog_post_wp.py",
        "blog_ping": "bin/blog_ping_search.py",
    }
    if step not in mapping:
        return jsonify({"error": "unknown step"}), 400
    cmd = f"python {mapping[step]}"
    subprocess.Popen(cmd, shell=True, cwd=BASE)
    return jsonify({"status": "started", "step": step})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099)
