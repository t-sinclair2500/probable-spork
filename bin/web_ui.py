#!/usr/bin/env python3
import json
import os
import subprocess
import time
import secrets
import hashlib
from functools import wraps

from flask import Flask, jsonify, request, abort, render_template_string, session
from flask_socketio import SocketIO, emit, disconnect
import threading
import queue

from bin.core import BASE, load_env
from bin.analytics_collector import MetricsCollector

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Generate a secure secret key

# Initialize SocketIO with CORS support
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Rate limiting storage (simple in-memory for demo)
rate_limit_store = {}

# Initialize analytics collector
analytics_collector = MetricsCollector()

# WebSocket state management
connected_clients = set()
log_watchers = set()
metrics_watchers = set()
broadcast_queue = queue.Queue()


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


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    connected_clients.add(request.sid)
    emit('status', {'type': 'connection', 'message': 'Connected to pipeline dashboard'})
    print(f"Client {request.sid} connected. Total clients: {len(connected_clients)}")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    connected_clients.discard(request.sid)
    log_watchers.discard(request.sid)
    metrics_watchers.discard(request.sid)
    print(f"Client {request.sid} disconnected. Total clients: {len(connected_clients)}")


@socketio.on('subscribe_logs')
def handle_subscribe_logs(data):
    """Subscribe to real-time log updates."""
    log_watchers.add(request.sid)
    source = data.get('source', 'state')
    emit('log_subscription', {'status': 'subscribed', 'source': source})
    
    # Send initial log data
    log_sources = {
        "state": os.path.join(BASE, "jobs", "state.jsonl"),
        "pipeline": os.path.join(BASE, "logs", "pipeline.log"),
    }
    
    if source in log_sources:
        content = tail(log_sources[source], 50)
        emit('log_update', {
            'source': source,
            'content': content,
            'timestamp': time.time()
        })


@socketio.on('unsubscribe_logs')
def handle_unsubscribe_logs():
    """Unsubscribe from log updates."""
    log_watchers.discard(request.sid)
    emit('log_subscription', {'status': 'unsubscribed'})


@socketio.on('subscribe_metrics')
def handle_subscribe_metrics():
    """Subscribe to real-time metrics updates."""
    metrics_watchers.add(request.sid)
    emit('metrics_subscription', {'status': 'subscribed'})
    
    # Send initial metrics
    try:
        metrics = analytics_collector.collect_system_metrics()
        emit('metrics_update', {
            'type': 'system',
            'data': metrics,
            'timestamp': time.time()
        })
    except Exception as e:
        emit('error', {'message': f'Failed to get initial metrics: {e}'})


@socketio.on('unsubscribe_metrics')
def handle_unsubscribe_metrics():
    """Unsubscribe from metrics updates."""
    metrics_watchers.discard(request.sid)
    emit('metrics_subscription', {'status': 'unsubscribed'})


@socketio.on('request_full_update')
def handle_request_full_update():
    """Send complete dashboard update to client."""
    try:
        # Get all current data
        state_data = get_pipeline_state()
        metrics_data = analytics_collector.collect_system_metrics()
        queue_data = get_upload_queue()
        
        emit('full_update', {
            'state': state_data,
            'metrics': metrics_data,
            'queue': queue_data,
            'timestamp': time.time()
        })
    except Exception as e:
        emit('error', {'message': f'Failed to get full update: {e}'})


def get_pipeline_state():
    """Get current pipeline state for WebSocket broadcasting."""
    p = os.path.join(BASE, "jobs", "state.jsonl")
    lines = []
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            lines = [json.loads(x) for x in f.read().splitlines() if x.strip()]
    
    recent_lines = lines[-20:] if lines else []
    step_counts = {}
    for line in lines:
        step = line.get('step', 'unknown')
        status = line.get('status', 'unknown')
        key = f"{step}:{status}"
        step_counts[key] = step_counts.get(key, 0) + 1
    
    return {
        "count": len(lines),
        "last": (lines[-1] if lines else {}),
        "recent": recent_lines,
        "step_counts": step_counts
    }


def get_upload_queue():
    """Get current upload queue for WebSocket broadcasting."""
    q = os.path.join(BASE, "data", "upload_queue.json")
    try:
        arr = json.load(open(q, "r", encoding="utf-8")) if os.path.exists(q) else []
    except Exception:
        arr = []
    return {"count": len(arr), "items": arr[-10:]}


def broadcast_update(update_type, data):
    """Broadcast updates to subscribed clients."""
    if update_type == 'logs' and log_watchers:
        socketio.emit('log_update', data, room=None)
    elif update_type == 'metrics' and metrics_watchers:
        socketio.emit('metrics_update', data, room=None)
    elif update_type == 'state' and connected_clients:
        socketio.emit('state_update', data, room=None)


def start_background_monitor():
    """Start background monitoring for real-time updates."""
    def monitor_logs():
        """Monitor log files for changes."""
        last_state_size = 0
        state_file = os.path.join(BASE, "jobs", "state.jsonl")
        
        while True:
            try:
                if os.path.exists(state_file):
                    current_size = os.path.getsize(state_file)
                    if current_size > last_state_size and log_watchers:
                        # New log entries detected
                        content = tail(state_file, 10)  # Get last 10 lines
                        broadcast_update('logs', {
                            'source': 'state',
                            'content': content,
                            'timestamp': time.time(),
                            'type': 'incremental'
                        })
                        last_state_size = current_size
                
                time.sleep(2)  # Check every 2 seconds
            except Exception as e:
                print(f"Log monitoring error: {e}")
                time.sleep(5)
    
    def monitor_metrics():
        """Monitor system metrics for changes."""
        last_metrics = None
        
        while True:
            try:
                if metrics_watchers:
                    current_metrics = analytics_collector.collect_system_metrics()
                    
                    # Only broadcast if metrics changed significantly
                    if last_metrics is None or metrics_changed(last_metrics, current_metrics):
                        broadcast_update('metrics', {
                            'type': 'system',
                            'data': current_metrics,
                            'timestamp': time.time()
                        })
                        last_metrics = current_metrics
                
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                print(f"Metrics monitoring error: {e}")
                time.sleep(15)
    
    # Start monitoring threads
    log_thread = threading.Thread(target=monitor_logs, daemon=True)
    metrics_thread = threading.Thread(target=monitor_metrics, daemon=True)
    
    log_thread.start()
    metrics_thread.start()


def metrics_changed(old_metrics, new_metrics, threshold=5.0):
    """Check if metrics changed significantly enough to broadcast."""
    try:
        old_cpu = old_metrics.get('cpu', {}).get('percent', 0)
        new_cpu = new_metrics.get('cpu', {}).get('percent', 0)
        
        old_memory = old_metrics.get('memory', {}).get('percent', 0)
        new_memory = new_metrics.get('memory', {}).get('percent', 0)
        
        cpu_change = abs(new_cpu - old_cpu)
        memory_change = abs(new_memory - old_memory)
        
        return cpu_change > threshold or memory_change > threshold
    except Exception:
        return True  # If we can't compare, assume changed


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


@app.get("/api/analytics/metrics")
@rate_limit(60)
def api_analytics_metrics():
    """Get current analytics metrics."""
    try:
        metrics = analytics_collector.collect_all_metrics()
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/analytics/trends")
@rate_limit(30)
def api_analytics_trends():
    """Get trend data for charts."""
    hours = int(request.args.get("hours", 24))
    try:
        trends = analytics_collector.get_trend_data(hours)
        return jsonify(trends)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/analytics/system")
@rate_limit(120)
def api_analytics_system():
    """Get current system metrics only."""
    try:
        system_metrics = analytics_collector.collect_system_metrics()
        return jsonify(system_metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/analytics/pipeline")
@rate_limit(60)
def api_analytics_pipeline():
    """Get pipeline performance metrics."""
    hours = int(request.args.get("hours", 24))
    try:
        pipeline_metrics = analytics_collector.parse_state_logs(hours)
        return jsonify(pipeline_metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/analytics/alerts")
@rate_limit(60)
def api_analytics_alerts():
    """Get active alerts."""
    try:
        metrics = analytics_collector.collect_all_metrics()
        alerts = metrics.get("alerts", [])
        return jsonify({"alerts": alerts, "count": len(alerts)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/analytics")
def analytics_dashboard():
    """Advanced analytics dashboard with charts and metrics."""
    html = '''
<!doctype html>
<html><head><meta charset='utf-8'><title>Analytics Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;background:#f5f5f5;}
.container{max-width:1400px;margin:0 auto;padding:20px;}
.header{background:white;border-radius:8px;padding:20px;margin-bottom:20px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
.metrics-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:20px;}
.metric-card{background:white;border-radius:8px;padding:20px;box-shadow:0 2px 4px rgba(0,0,0,0.1);text-align:center;}
.metric-value{font-size:2em;font-weight:bold;color:#007bff;}
.metric-label{color:#666;margin-top:5px;}
.charts-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;}
.chart-container{background:white;border-radius:8px;padding:20px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
.alerts-section{background:white;border-radius:8px;padding:20px;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:20px;}
.alert{padding:10px;border-radius:4px;margin:5px 0;}
.alert.warning{background:#fff3cd;border:1px solid #ffeaa7;color:#856404;}
.alert.error{background:#f8d7da;border:1px solid #f5c6cb;color:#721c24;}
.nav-tabs{background:white;border-radius:8px;padding:10px;margin-bottom:20px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
.nav-tab{display:inline-block;padding:10px 20px;background:#e9ecef;border:none;border-radius:4px;margin:0 5px;cursor:pointer;text-decoration:none;color:#495057;}
.nav-tab.active{background:#007bff;color:white;}
.performance-table{width:100%;border-collapse:collapse;margin-top:15px;}
.performance-table th,.performance-table td{padding:8px;text-align:left;border-bottom:1px solid #ddd;}
.performance-table th{background:#f8f9fa;}
.status-indicator{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;}
.status-ok{background:#28a745;}
.status-warn{background:#ffc107;}
.status-error{background:#dc3545;}
</style>
</head><body>
<div class="container">
  <div class="header">
    <h1>Analytics Dashboard</h1>
    <p>Real-time pipeline performance and system monitoring</p>
  </div>
  
  <div class="nav-tabs">
    <a href="/" class="nav-tab">Basic Dashboard</a>
    <a href="/analytics" class="nav-tab active">Analytics</a>
  </div>
  
  <div class="alerts-section" id="alerts-section" style="display:none;">
    <h3>Active Alerts</h3>
    <div id="alerts-container"></div>
  </div>
  
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-value" id="cpu-metric">-</div>
      <div class="metric-label">CPU Usage</div>
    </div>
    <div class="metric-card">
      <div class="metric-value" id="memory-metric">-</div>
      <div class="metric-label">Memory Usage</div>
    </div>
    <div class="metric-card">
      <div class="metric-value" id="disk-metric">-</div>
      <div class="metric-label">Disk Usage</div>
    </div>
    <div class="metric-card">
      <div class="metric-value" id="pipeline-success">-</div>
      <div class="metric-label">Pipeline Success Rate</div>
    </div>
  </div>
  
  <div class="charts-grid">
    <div class="chart-container">
      <h3>System Resources (24h)</h3>
      <canvas id="system-chart" width="400" height="200"></canvas>
    </div>
    <div class="chart-container">
      <h3>Pipeline Performance</h3>
      <canvas id="pipeline-chart" width="400" height="200"></canvas>
    </div>
  </div>
  
  <div class="chart-container">
    <h3>Step Performance Analysis</h3>
    <table class="performance-table" id="performance-table">
      <thead>
        <tr>
          <th>Step</th>
          <th>Success Rate</th>
          <th>Total Runs</th>
          <th>Recent Status</th>
          <th>Errors</th>
        </tr>
      </thead>
      <tbody id="performance-tbody">
      </tbody>
    </table>
  </div>
</div>

<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<script>
let systemChart, pipelineChart;
let socket = null;
let useWebSocket = true;
let pollInterval = null;

// Initialize WebSocket connection
function initWebSocket() {
  try {
    socket = io();
    
    socket.on('connect', function() {
      console.log('WebSocket connected');
      useWebSocket = true;
      
      // Clear polling if active
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
      
      // Subscribe to metrics updates
      socket.emit('subscribe_metrics');
      socket.emit('request_full_update');
    });
    
    socket.on('disconnect', function() {
      console.log('WebSocket disconnected, falling back to polling');
      useWebSocket = false;
      startPolling();
    });
    
    socket.on('metrics_update', function(data) {
      if (data.type === 'system') {
        updateMetrics(data.data);
      }
    });
    
    socket.on('full_update', function(data) {
      updateMetrics(data.metrics);
      // Also fetch trends and alerts initially
      fetchInitialData();
    });
    
    socket.on('error', function(error) {
      console.error('WebSocket error:', error);
    });
    
    return true;
  } catch (error) {
    console.error('Failed to initialize WebSocket:', error);
    return false;
  }
}

// Fallback polling function
function startPolling() {
  if (pollInterval) return; // Already polling
  
  console.log('Starting polling fallback');
  fetchMetrics(); // Initial fetch
  pollInterval = setInterval(fetchMetrics, 10000);
}

async function fetchMetrics() {
  try {
    const [metrics, trends, alerts] = await Promise.all([
      fetch('/api/analytics/system').then(r => r.json()),
      fetch('/api/analytics/trends?hours=24').then(r => r.json()),
      fetch('/api/analytics/alerts').then(r => r.json())
    ]);
    
    updateMetrics(metrics);
    updateCharts(trends);
    updateAlerts(alerts);
    
    // Also fetch pipeline data
    const pipeline = await fetch('/api/analytics/pipeline?hours=24').then(r => r.json());
    updatePipelineTable(pipeline);
    
  } catch (error) {
    console.error('Failed to fetch metrics:', error);
  }
}

async function fetchInitialData() {
  try {
    const [trends, alerts, pipeline] = await Promise.all([
      fetch('/api/analytics/trends?hours=24').then(r => r.json()),
      fetch('/api/analytics/alerts').then(r => r.json()),
      fetch('/api/analytics/pipeline?hours=24').then(r => r.json())
    ]);
    
    updateCharts(trends);
    updateAlerts(alerts);
    updatePipelineTable(pipeline);
  } catch (error) {
    console.error('Failed to fetch initial data:', error);
  }
}

function updateMetrics(metrics) {
  const cpu = metrics.cpu?.percent || 0;
  const memory = metrics.memory?.percent || 0;
  const disk = metrics.disk?.percent || 0;
  
  document.getElementById('cpu-metric').textContent = cpu.toFixed(1) + '%';
  document.getElementById('memory-metric').textContent = memory.toFixed(1) + '%';
  document.getElementById('disk-metric').textContent = disk.toFixed(1) + '%';
  
  // Color code based on thresholds
  colorCodeMetric('cpu-metric', cpu, 80, 90);
  colorCodeMetric('memory-metric', memory, 85, 95);
  colorCodeMetric('disk-metric', disk, 80, 90);
}

function updateCharts(trends) {
  const ctx1 = document.getElementById('system-chart').getContext('2d');
  const ctx2 = document.getElementById('pipeline-chart').getContext('2d');
  
  const timestamps = trends.timestamps || [];
  const labels = timestamps.map(ts => new Date(ts * 1000).toLocaleTimeString());
  
  // Destroy existing charts
  if (systemChart) systemChart.destroy();
  if (pipelineChart) pipelineChart.destroy();
  
  // System resources chart
  systemChart = new Chart(ctx1, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'CPU %',
          data: trends.cpu || [],
          borderColor: '#007bff',
          backgroundColor: 'rgba(0,123,255,0.1)',
          fill: false
        },
        {
          label: 'Memory %',
          data: trends.memory || [],
          borderColor: '#28a745',
          backgroundColor: 'rgba(40,167,69,0.1)',
          fill: false
        },
        {
          label: 'Disk %',
          data: trends.disk || [],
          borderColor: '#ffc107',
          backgroundColor: 'rgba(255,193,7,0.1)',
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
          max: 100
        }
      }
    }
  });
  
  // Pipeline success chart
  pipelineChart = new Chart(ctx2, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Success Rate %',
          data: trends.pipeline_success || [],
          borderColor: '#17a2b8',
          backgroundColor: 'rgba(23,162,184,0.1)',
          fill: true
        }
      ]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
          max: 100
        }
      }
    }
  });
}

function updateAlerts(alertData) {
  const alerts = alertData.alerts || [];
  const alertsSection = document.getElementById('alerts-section');
  const alertsContainer = document.getElementById('alerts-container');
  
  if (alerts.length === 0) {
    alertsSection.style.display = 'none';
    return;
  }
  
  alertsSection.style.display = 'block';
  alertsContainer.innerHTML = '';
  
  alerts.forEach(alert => {
    const div = document.createElement('div');
    div.className = `alert ${alert.type}`;
    div.innerHTML = `
      <strong>${alert.category.toUpperCase()}:</strong> ${alert.message}
      <small style="float:right;">${new Date(alert.timestamp * 1000).toLocaleTimeString()}</small>
    `;
    alertsContainer.appendChild(div);
  });
}

function updatePipelineTable(pipeline) {
  const tbody = document.getElementById('performance-tbody');
  const performance = pipeline.performance || {};
  
  tbody.innerHTML = '';
  
  Object.entries(performance).forEach(([step, data]) => {
    const row = document.createElement('tr');
    const successRate = data.success_rate || 0;
    const statusClass = successRate >= 90 ? 'ok' : successRate >= 70 ? 'warn' : 'error';
    
    row.innerHTML = `
      <td>${step}</td>
      <td>
        <span class="status-indicator status-${statusClass}"></span>
        ${successRate.toFixed(1)}%
      </td>
      <td>${data.total_runs || 0}</td>
      <td>${Object.entries(data.statuses || {}).map(([s,c]) => `${s}:${c}`).join(', ')}</td>
      <td>${data.error_count || 0}</td>
    `;
    tbody.appendChild(row);
  });
  
  // Update overall pipeline success rate
  const allRates = Object.values(performance).map(p => p.success_rate || 0);
  const avgRate = allRates.length > 0 ? allRates.reduce((a,b) => a+b, 0) / allRates.length : 0;
  document.getElementById('pipeline-success').textContent = avgRate.toFixed(1) + '%';
  colorCodeMetric('pipeline-success', avgRate, 70, 90);
}

function colorCodeMetric(elementId, value, warnThreshold, errorThreshold) {
  const element = document.getElementById(elementId);
  if (value >= errorThreshold) {
    element.style.color = '#dc3545';
  } else if (value >= warnThreshold) {
    element.style.color = '#ffc107';
  } else {
    element.style.color = '#28a745';
  }
}

// Initialize - try WebSocket first, fallback to polling
if (!initWebSocket()) {
  startPolling();
}
</script>
</body></html>
    '''
    return html


if __name__ == "__main__":
    # Start background monitoring
    start_background_monitor()
    
    # Run with SocketIO support
    socketio.run(app, host="0.0.0.0", port=8099, debug=False)

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
    <p><a href="/analytics" style="color:#007bff;">View Advanced Analytics →</a></p>
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

<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
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

// Initialize with WebSocket support
function initBasicWebSocket() {
  try {
    const socket = io();
    
    socket.on('connect', function() {
      document.getElementById('connection-status').textContent = 'Connected (Live)';
      document.getElementById('connection-status').style.color = 'green';
      
      // Clear polling interval
      if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
      }
      
      // Subscribe to log updates
      socket.emit('subscribe_logs', {source: currentLogSource});
      socket.emit('request_full_update');
    });
    
    socket.on('disconnect', function() {
      document.getElementById('connection-status').textContent = 'Disconnected';
      document.getElementById('connection-status').style.color = 'red';
      
      // Fallback to polling
      refresh();
      refreshInterval = setInterval(refresh, 5000);
    });
    
    socket.on('log_update', function(data) {
      if (data.source === currentLogSource) {
        document.getElementById('logs').textContent = data.content;
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
      }
    });
    
    socket.on('full_update', function(data) {
      updateStateDisplay(data.state);
      document.getElementById('queue').textContent = JSON.stringify(data.queue, null, 2);
      document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
    });
    
    socket.on('state_update', function(data) {
      updateStateDisplay(data);
    });
    
    // Override switchLogSource to use WebSocket
    window.switchLogSourceWebSocket = function(source) {
      currentLogSource = source;
      document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
      event.target.classList.add('active');
      socket.emit('subscribe_logs', {source: source});
    };
    
    return true;
  } catch (error) {
    console.error('WebSocket initialization failed:', error);
    return false;
  }
}

// Try WebSocket first, fallback to polling
if (!initBasicWebSocket()) {
  refresh();
  refreshInterval = setInterval(refresh, 5000);
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (refreshInterval) clearInterval(refreshInterval);
});
</script>
</body></html>
"""
    return render_template_string(html, pw="yes" if pw_required else "no")
