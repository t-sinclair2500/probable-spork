#!/usr/bin/env python3
import json
import os
import subprocess
import time

from flask import Flask, jsonify, request, abort, render_template_string

from bin.core import BASE, load_env

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


@app.get("/api/queue")
def api_queue():
    q = os.path.join(BASE, "data", "upload_queue.json")
    try:
        arr = json.load(open(q, "r", encoding="utf-8")) if os.path.exists(q) else []
    except Exception:
        arr = []
    return jsonify({"count": len(arr), "items": arr[-10:]})


@app.post("/api/run")
def api_run():
    # Simple password auth via WEB_UI_PASSWORD in .env (optional). If set, require header.
    env = load_env()
    required_pw = env.get("WEB_UI_PASSWORD", "")
    if required_pw:
        provided = request.headers.get("X-Auth-Token", "")
        if provided != required_pw:
            return jsonify({"error": "unauthorized"}), 401
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
    cmd = f"python3 {mapping[step]}"
    subprocess.Popen(cmd, shell=True, cwd=BASE)
    return jsonify({"status": "started", "step": step})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099)

# Basic dashboard page (inline template) for convenience
@app.get("/")
def dashboard():
    env = load_env()
    pw_required = bool(env.get("WEB_UI_PASSWORD"))
    html = """
<!doctype html>
<html><head><meta charset='utf-8'><title>Pipeline Dashboard</title>
<style>body{font-family:sans-serif;margin:20px;}code,pre{background:#f6f8fa;padding:8px;border-radius:6px}</style>
</head><body>
<h1>Pipeline Dashboard</h1>
<p>Password required for actions: {{pw}}</p>
<h2>State</h2>
<pre id="state">loading...</pre>
<h2>Logs</h2>
<pre id="logs">loading...</pre>
<h2>Upload Queue</h2>
<pre id="queue">loading...</pre>
<h2>Actions</h2>
<div>
  <input type="password" id="pw" placeholder="X-Auth-Token" />
  <button onclick="run('outline')">Outline</button>
  <button onclick="run('script')">Script</button>
  <button onclick="run('assets')">Assets</button>
  <button onclick="run('tts')">TTS</button>
  <button onclick="run('captions')">Captions</button>
  <button onclick="run('assemble')">Assemble</button>
  <button onclick="run('stage')">Stage</button>
</div>
<script>
async function refresh(){
  const s = await fetch('/api/state').then(r=>r.json());
  document.getElementById('state').textContent = JSON.stringify(s,null,2);
  const l = await fetch('/api/logs').then(r=>r.json());
  document.getElementById('logs').textContent = l.tail;
  const q = await fetch('/api/queue').then(r=>r.json());
  document.getElementById('queue').textContent = JSON.stringify(q,null,2);
}
async function run(step){
  const headers = {};
  const t = document.getElementById('pw').value;
  if(t) headers['X-Auth-Token']=t;
  const r = await fetch('/api/run?step='+encodeURIComponent(step), {method:'POST', headers});
  const j = await r.json();
  alert(JSON.stringify(j));
  setTimeout(refresh, 1500);
}
refresh();
setInterval(refresh, 5000);
</script>
</body></html>
"""
    return render_template_string(html, pw="yes" if pw_required else "no")
