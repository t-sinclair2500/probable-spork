import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager

# Ensure repo root is on sys.path so `bin.core` is importable when scripts are
# invoked directly (not via Makefile that sets PYTHONPATH)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Delegate to bin.core for shared functionality to keep behavior consistent
from bin.core import (  # type: ignore
    BASE as CORE_BASE,
    load_config as core_load_config,
    log_state as core_log_state,
    single_lock as core_single_lock,
)

BASE = CORE_BASE


def load_global_config():
    """Compatibility wrapper returning a dict, backed by bin.core.load_config()."""
    cfg = core_load_config()
    try:
        return cfg.model_dump()
    except Exception:
        # Fallback: shallow conversion
        return json.loads(cfg.json())  # type: ignore


def single_lock():  # type: ignore[override]
    return core_single_lock()


def log_state(step, status="OK", notes=""):
    return core_log_state(step, status, notes)


def paced_sleep(cfg, label="cooldown"):
    secs = int(cfg.get("pipeline", {}).get("pacing_cooldown_seconds", 30))
    time.sleep(secs)


def run_cmd(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def ensure_dirs(cfg):
    s = cfg["storage"]
    for key in [
        "videos_dir",
        "assets_dir",
        "scripts_dir",
        "voiceovers_dir",
        "logs_dir",
        "data_dir",
        "jobs_dir",
    ]:
        os.makedirs(os.path.join(BASE, s[key]), exist_ok=True)
