#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, load_config, load_env, get_logger

log = get_logger("healthcheck")


def cpu_temp():
    """Get CPU temperature - works on Raspberry Pi with vcgencmd"""
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True).strip()
        # Extract numeric value for threshold checking
        temp_str = out.replace("temp=", "").replace("'C", "")
        temp_val = float(temp_str)
        return {"raw": out, "celsius": temp_val, "status": "ok" if temp_val < 75 else "warning"}
    except Exception:
        # Fallback for non-Pi systems
        try:
            # Try macOS/Linux sensors
            result = subprocess.run(["sensors"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and "temp" in result.stdout.lower():
                return {"raw": "sensors_available", "celsius": None, "status": "ok"}
        except Exception:
            pass
        return {"raw": "unknown", "celsius": None, "status": "unknown"}


def disk_free():
    """Get disk usage information"""
    total, used, free = shutil.disk_usage(BASE)
    free_pct = (free / total) * 100
    return {
        "total_gb": round(total / 1e9, 2), 
        "free_gb": round(free / 1e9, 2),
        "free_pct": round(free_pct, 1),
        "status": "ok" if free_pct > 10 else "warning" if free_pct > 5 else "critical"
    }


def check_service_status():
    """Check status of key services"""
    services = {}
    
    # Check Ollama
    try:
        cfg = load_config()
        endpoint = cfg.llm.endpoint
        import requests
        r = requests.get(endpoint.replace('/api/generate', '/api/tags'), timeout=5)
        services['ollama'] = {
            "status": "ok" if r.status_code == 200 else "error",
            "endpoint": endpoint,
            "response_code": r.status_code
        }
    except Exception as e:
        services['ollama'] = {"status": "error", "error": str(e)}
    
    # Check whisper.cpp
    try:
        cfg = load_config()
        whisper_path = cfg.asr.whisper_cpp_path
        if whisper_path == "auto":
            # Try common locations
            possible_paths = [
                os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli"),
                "/usr/local/bin/whisper-cli",
                "/opt/whisper.cpp/build/bin/whisper-cli",
            ]
            found = False
            for path in possible_paths:
                if os.path.exists(path):
                    services['whisper_cpp'] = {"status": "ok", "path": path}
                    found = True
                    break
            if not found:
                services['whisper_cpp'] = {"status": "missing", "searched": possible_paths}
        else:
            services['whisper_cpp'] = {
                "status": "ok" if os.path.exists(whisper_path) else "missing",
                "path": whisper_path
            }
    except Exception as e:
        services['whisper_cpp'] = {"status": "error", "error": str(e)}
    
    return services


def check_api_keys():
    """Check availability of API keys"""
    env = load_env()
    api_status = {}
    
    # YouTube/Google
    api_status['youtube'] = bool(env.get("YOUTUBE_API_KEY") or env.get("GOOGLE_API_KEY"))
    
    # Asset providers
    api_status['asset_providers'] = {
        'pixabay': bool(env.get("PIXABAY_API_KEY")),
        'pexels': bool(env.get("PEXELS_API_KEY")),
        'unsplash': bool(env.get("UNSPLASH_ACCESS_KEY")),
        'any_available': any([
            env.get("PIXABAY_API_KEY"),
            env.get("PEXELS_API_KEY"), 
            env.get("UNSPLASH_ACCESS_KEY")
        ])
    }
    
    # Reddit
    api_status['reddit'] = bool(env.get("REDDIT_CLIENT_ID") and env.get("REDDIT_CLIENT_SECRET"))
    
    # OpenAI (optional)
    api_status['openai'] = bool(env.get("OPENAI_API_KEY"))
    
    return api_status


def get_queue_depths():
    """Get depths of various queues and pipeline state"""
    queues = {}
    
    # Topics queue
    try:
        topics_path = os.path.join(BASE, "data", "topics_queue.json")
        if os.path.exists(topics_path):
            with open(topics_path, 'r') as f:
                topics = json.load(f)
                queues['topics_queue'] = {
                    "count": len(topics),
                    "items": topics if len(topics) <= 5 else topics[:5]  # Show first 5
                }
        else:
            queues['topics_queue'] = {"count": 0, "status": "missing"}
    except Exception as e:
        queues['topics_queue'] = {"count": -1, "error": str(e)}
    
    # Upload queue
    try:
        upload_path = os.path.join(BASE, "data", "upload_queue.json")
        if os.path.exists(upload_path):
            with open(upload_path, 'r') as f:
                uploads = json.load(f)
                queues['upload_queue'] = {"count": len(uploads)}
        else:
            queues['upload_queue'] = {"count": 0, "status": "missing"}
    except Exception as e:
        queues['upload_queue'] = {"count": -1, "error": str(e)}
    
    # Recent artifacts
    try:
        videos_dir = os.path.join(BASE, "videos")
        scripts_dir = os.path.join(BASE, "scripts")
        assets_dir = os.path.join(BASE, "assets")
        
        video_count = len([f for f in os.listdir(videos_dir) if f.endswith('.mp4')]) if os.path.exists(videos_dir) else 0
        script_count = len([f for f in os.listdir(scripts_dir) if f.endswith('.txt')]) if os.path.exists(scripts_dir) else 0
        asset_dirs = len([d for d in os.listdir(assets_dir) if os.path.isdir(os.path.join(assets_dir, d))]) if os.path.exists(assets_dir) else 0
        
        queues['artifacts'] = {
            "videos": video_count,
            "scripts": script_count, 
            "asset_collections": asset_dirs
        }
    except Exception as e:
        queues['artifacts'] = {"error": str(e)}
    
    return queues


def get_last_pipeline_status():
    """Get status of last pipeline run from state.jsonl"""
    try:
        state_path = os.path.join(BASE, "jobs", "state.jsonl")
        if not os.path.exists(state_path):
            return {"status": "no_logs", "last_run": None}
        
        # Read last 20 lines to get recent activity
        lines = []
        with open(state_path, 'r') as f:
            lines = f.readlines()
        
        if not lines:
            return {"status": "empty_logs", "last_run": None}
        
        recent_lines = lines[-20:] if len(lines) > 20 else lines
        recent_events = []
        
        for line in recent_lines:
            try:
                event = json.loads(line.strip())
                recent_events.append(event)
            except json.JSONDecodeError:
                continue
        
        if not recent_events:
            return {"status": "no_valid_logs", "last_run": None}
        
        # Find the most recent completed step
        last_event = recent_events[-1]
        
        # Count successes and failures in recent events
        successes = sum(1 for e in recent_events if e.get('status') == 'OK')
        failures = sum(1 for e in recent_events if e.get('status') in ['FAIL', 'ERROR'])
        warnings = sum(1 for e in recent_events if e.get('status') in ['WARN', 'VALIDATE_WARN'])
        
        return {
            "status": "active",
            "last_event": last_event,
            "recent_stats": {
                "successes": successes,
                "failures": failures, 
                "warnings": warnings,
                "total_events": len(recent_events)
            },
            "last_step": last_event.get('step'),
            "last_status": last_event.get('status'),
            "last_ts": last_event.get('ts')
        }
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    """Enhanced healthcheck with comprehensive monitoring"""
    try:
        cfg = load_config()
        
        # Gather all health information
        health_report = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "system": {
                "cpu_temp": cpu_temp(),
                "disk": disk_free(),
            },
            "services": check_service_status(),
            "api_keys": check_api_keys(),
            "queues": get_queue_depths(),
            "pipeline": get_last_pipeline_status(),
            "config": {
                "llm_model": cfg.llm.model,
                "llm_provider": cfg.llm.provider,
                "tts_provider": cfg.tts.provider,
                "asr_provider": cfg.asr.provider,
                "asset_providers": cfg.assets.providers,
                "daily_videos": cfg.pipeline.daily_videos
            }
        }
        
        # Determine overall health status
        warnings = []
        errors = []
        
        # System checks
        if health_report["system"]["cpu_temp"]["status"] == "warning":
            warnings.append(f"High CPU temperature: {health_report['system']['cpu_temp']['celsius']}°C")
        if health_report["system"]["disk"]["status"] in ["warning", "critical"]:
            level = "critical" if health_report["system"]["disk"]["status"] == "critical" else "warning"
            warnings.append(f"Low disk space: {health_report['system']['disk']['free_pct']}% free")
            if level == "critical":
                errors.append("Critical disk space")
        
        # Service checks
        if health_report["services"]["ollama"]["status"] != "ok":
            errors.append("Ollama service unavailable")
        if health_report["services"]["whisper_cpp"]["status"] not in ["ok", "missing"]:
            warnings.append("whisper.cpp error")
        
        # API key checks
        if not health_report["api_keys"]["asset_providers"]["any_available"]:
            warnings.append("No asset provider API keys available")
        
        # Pipeline checks
        pipeline_status = health_report["pipeline"]["status"]
        if pipeline_status == "error":
            errors.append("Pipeline logging error")
        elif health_report["pipeline"].get("recent_stats", {}).get("failures", 0) > 0:
            warnings.append(f"Recent pipeline failures: {health_report['pipeline']['recent_stats']['failures']}")
        
        # Overall status
        if errors:
            overall_status = "error"
        elif warnings:
            overall_status = "warning" 
        else:
            overall_status = "ok"
        
        health_report["health"] = {
            "status": overall_status,
            "warnings": warnings,
            "errors": errors,
            "summary": f"System {overall_status.upper()}: {len(errors)} errors, {len(warnings)} warnings"
        }
        
        # Pretty print for human readability
        print(json.dumps(health_report, indent=2))
        
        # Exit with appropriate code for monitoring systems
        sys.exit(0 if overall_status == "ok" else 1 if overall_status == "warning" else 2)
        
    except Exception as e:
        error_report = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "health": {
                "status": "error",
                "errors": [f"Healthcheck failed: {e}"],
                "warnings": [],
                "summary": "HEALTHCHECK ERROR"
            }
        }
        print(json.dumps(error_report, indent=2))
        sys.exit(2)


if __name__ == "__main__":
    main()
