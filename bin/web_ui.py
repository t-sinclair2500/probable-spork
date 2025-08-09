#!/usr/bin/env python3
import json
import os
import subprocess
import time
import secrets
import hashlib
from functools import wraps

from flask import Flask, jsonify, request, abort, render_template_string, session

from bin.core import BASE, load_env

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Generate a secure secret key

# Rate limiting storage (simple in-memory for demo)
rate_limit_store = {}


def requires_auth(f):
    """Authentication decorator with session management."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        env = load_env()
        required_pw = env.get("WEB_UI_PASSWORD", "")
        
        if not required_pw:
            return f(*args, **kwargs)  # No auth required
        
        # Check session first
        if session.get('authenticated'):
            return f(*args, **kwargs)
        
        # Check X-Auth-Token header
        provided = request.headers.get("X-Auth-Token", "")
        if provided and provided == required_pw:
            session['authenticated'] = True
            return f(*args, **kwargs)
        
        return jsonify({"error": "unauthorized"}), 401
    return decorated_function


def rate_limit(calls_per_minute=30):
    """Simple rate limiting decorator."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            current_time = time.time()
            
            # Clean old entries
            rate_limit_store[client_ip] = [
                timestamp for timestamp in rate_limit_store.get(client_ip, [])
                if current_time - timestamp < 60
            ]
            
            # Check rate limit
            if len(rate_limit_store.get(client_ip, [])) >= calls_per_minute:
                return jsonify({"error": "rate_limit_exceeded"}), 429
            
            # Add current request
            rate_limit_store.setdefault(client_ip, []).append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def tail(path, n=200):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    return "\n".join(lines[-n:])


@app.get("/api/state")
@rate_limit(60)
def api_state():
    p = os.path.join(BASE, "jobs", "state.jsonl")
    lines = []
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            lines = [json.loads(x) for x in f.read().splitlines() if x.strip()]
    
    # Enhanced state information
    recent_lines = lines[-20:] if lines else []
    step_counts = {}
    for line in lines:
        step = line.get('step', 'unknown')
        status = line.get('status', 'unknown')
        key = f"{step}:{status}"
        step_counts[key] = step_counts.get(key, 0) + 1
    
    return jsonify({
        "count": len(lines), 
        "last": (lines[-1] if lines else {}),
        "recent": recent_lines,
        "step_counts": step_counts
    })


@app.get("/api/topics")
@rate_limit(60)
def api_topics():
    p = os.path.join(BASE, "data", "topics_queue.json")
    arr = []
    if os.path.exists(p):
        arr = json.load(open(p, "r", encoding="utf-8"))
    return jsonify(arr)


@app.get("/api/logs")
@rate_limit(120)
def api_logs():
    # Support multiple log sources
    log_sources = {
        "state": os.path.join(BASE, "jobs", "state.jsonl"),
        "pipeline": os.path.join(BASE, "logs", "pipeline.log"),
    }
    
    source = request.args.get("source", "state")
    lines = int(request.args.get("lines", 200))
    
    if source not in log_sources:
        return jsonify({"error": "invalid log source"}), 400
    
    log_path = log_sources[source]
    content = tail(log_path, lines)
    
    return jsonify({
        "source": source,
        "lines": lines,
        "content": content,
        "path": log_path,
        "exists": os.path.exists(log_path)
    })


@app.get("/api/queue")
@rate_limit(60)
def api_queue():
    q = os.path.join(BASE, "data", "upload_queue.json")
    try:
        arr = json.load(open(q, "r", encoding="utf-8")) if os.path.exists(q) else []
    except Exception:
        arr = []
    return jsonify({"count": len(arr), "items": arr[-10:]})


@app.post("/api/run")
@rate_limit(10)  # Stricter rate limit for job triggers
@requires_auth
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
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;background:#f5f5f5;}
.container{max-width:1200px;margin:0 auto;padding:20px;}
.header{background:white;border-radius:8px;padding:20px;margin-bottom:20px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;}
.card{background:white;border-radius:8px;padding:20px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
.actions{background:white;border-radius:8px;padding:20px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
.log-container{background:white;border-radius:8px;padding:20px;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:20px;}
pre{background:#f8f9fa;padding:15px;border-radius:6px;overflow-x:auto;font-size:12px;max-height:300px;overflow-y:auto;}
button{background:#007bff;color:white;border:none;padding:8px 16px;border-radius:4px;margin:4px;cursor:pointer;}
button:hover{background:#0056b3;}
input{padding:8px;border:1px solid #ddd;border-radius:4px;margin:4px;}
.status{display:inline-block;padding:4px 8px;border-radius:4px;font-size:12px;font-weight:bold;}
.status.ok{background:#d4edda;color:#155724;}
.status.warn{background:#fff3cd;color:#856404;}
.status.fail{background:#f8d7da;color:#721c24;}
.tabs{margin-bottom:15px;}
.tab{display:inline-block;padding:8px 16px;background:#e9ecef;border:none;border-radius:4px 4px 0 0;margin-right:4px;cursor:pointer;}
.tab.active{background:#007bff;color:white;}
</style>
</head><body>
<div class="container">
  <div class="header">
    <h1>Pipeline Dashboard</h1>
    <p>Auth required: <span style="color:{{pw == 'yes' and 'red' or 'green'}}">{{pw}}</span> | 
       Status: <span id="connection-status">Connected</span> | 
       Last update: <span id="last-update">-</span></p>
  </div>
  
  <div class="grid">
    <div class="card">
      <h3>Pipeline State</h3>
      <div id="state-summary"></div>
      <pre id="state-detail"></pre>
    </div>
    <div class="card">
      <h3>Upload Queue</h3>
      <pre id="queue"></pre>
    </div>
  </div>
  
  <div class="log-container">
    <h3>Logs</h3>
    <div class="tabs">
      <button class="tab active" onclick="switchLogSource('state')">State Log</button>
      <button class="tab" onclick="switchLogSource('pipeline')">Pipeline Log</button>
    </div>
    <pre id="logs"></pre>
  </div>
  
  <div class="actions">
    <h3>Actions</h3>
    <input type="password" id="pw" placeholder="Password (if required)" />
    <div style="margin-top:15px;">
      <h4>Content Generation:</h4>
      <button onclick="run('fetch_trends')">Fetch Trends</button>
      <button onclick="run('cluster')">Cluster Topics</button>
      <button onclick="run('outline')">Generate Outline</button>
      <button onclick="run('script')">Write Script</button>
      <button onclick="run('assets')">Download Assets</button>
      
      <h4>Video Production:</h4>
      <button onclick="run('tts')">Generate TTS</button>
      <button onclick="run('captions')">Generate Captions</button>
      <button onclick="run('assemble')">Assemble Video</button>
      <button onclick="run('stage')">Stage Upload</button>
      
      <h4>Blog Publishing:</h4>
      <button onclick="run('blog_pick')">Pick Topic</button>
      <button onclick="run('blog_gen')">Generate Post</button>
      <button onclick="run('blog_render')">Render HTML</button>
      <button onclick="run('blog_post')">Post to WordPress</button>
      <button onclick="run('blog_ping')">Ping Search</button>
    </div>
  </div>
</div>

<script>
let currentLogSource = 'state';
let refreshInterval;

async function fetchWithTimeout(url, options = {}, timeout = 10000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}

async function refresh() {
  try {
    document.getElementById('connection-status').textContent = 'Fetching...';
    
    // Fetch state
    const s = await fetchWithTimeout('/api/state').then(r => r.json());
    updateStateDisplay(s);
    
    // Fetch logs
    const l = await fetchWithTimeout(`/api/logs?source=${currentLogSource}&lines=100`).then(r => r.json());
    document.getElementById('logs').textContent = l.content;
    
    // Fetch queue
    const q = await fetchWithTimeout('/api/queue').then(r => r.json());
    document.getElementById('queue').textContent = JSON.stringify(q, null, 2);
    
    document.getElementById('connection-status').textContent = 'Connected';
    document.getElementById('connection-status').style.color = 'green';
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
  } catch (error) {
    document.getElementById('connection-status').textContent = 'Error';
    document.getElementById('connection-status').style.color = 'red';
    console.error('Refresh failed:', error);
  }
}

function updateStateDisplay(state) {
  const summary = document.getElementById('state-summary');
  const detail = document.getElementById('state-detail');
  
  if (state.last && state.last.step) {
    const status = state.last.status || 'unknown';
    const statusClass = status.toLowerCase() === 'ok' ? 'ok' : 
                       status.toLowerCase().includes('warn') ? 'warn' : 'fail';
    
    summary.innerHTML = `
      <p>Last step: <strong>${state.last.step}</strong> 
         <span class="status ${statusClass}">${status}</span></p>
      <p>Total entries: ${state.count}</p>
      <p>Time: ${state.last.ts || 'unknown'}</p>
    `;
  } else {
    summary.innerHTML = '<p>No pipeline activity</p>';
  }
  
  detail.textContent = JSON.stringify(state, null, 2);
}

function switchLogSource(source) {
  currentLogSource = source;
  document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
  event.target.classList.add('active');
  refresh();
}

async function run(step) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    const token = document.getElementById('pw').value;
    if (token) headers['X-Auth-Token'] = token;
    
    const r = await fetchWithTimeout('/api/run?step=' + encodeURIComponent(step), {
      method: 'POST', 
      headers
    });
    
    const result = await r.json();
    
    if (r.ok) {
      alert(`Started: ${step}`);
      setTimeout(refresh, 2000);
    } else {
      alert(`Error: ${result.error || 'Unknown error'}`);
    }
  } catch (error) {
    alert(`Failed to start ${step}: ${error.message}`);
  }
}

// Start refresh cycle
refresh();
refreshInterval = setInterval(refresh, 5000);

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (refreshInterval) clearInterval(refreshInterval);
});
</script>
</body></html>
"""
    return render_template_string(html, pw="yes" if pw_required else "no")
