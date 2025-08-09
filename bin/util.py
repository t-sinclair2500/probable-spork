import os, json, yaml, time, fcntl, sys, subprocess, pathlib
from contextlib import contextmanager
from rich import print

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def load_global_config():
    p = os.path.join(BASE, "conf", "global.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "global.example.yaml")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def env(key, default=""):
    return os.environ.get(key, default)

@contextmanager
def single_lock():
    lock_path = os.path.join(BASE, "jobs", "lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError:
        print("[yellow]Another job is running. Exiting.[/yellow]")
        sys.exit(0)
    finally:
        try:
            fcntl.lockf(fd, fcntl.LOCK_UN)
            os.close(fd)
            os.remove(lock_path)
        except Exception:
            pass

def log_state(step, status="OK", notes=""):
    state_path = os.path.join(BASE, "jobs", "state.jsonl")
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "step": step, "status": status, "notes": notes}
    with open(state_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

def paced_sleep(cfg, label="cooldown"):
    secs = int(cfg.get("pipeline", {}).get("pacing_cooldown_seconds", 30))
    time.sleep(secs)

def run_cmd(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def load_json(path, default=None):
    if not os.path.exists(path): return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def dump_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

def ensure_dirs(cfg):
    s = cfg["storage"]
    for key in ["videos_dir","assets_dir","scripts_dir","voiceovers_dir","logs_dir","data_dir","jobs_dir"]:
        os.makedirs(os.path.join(BASE, s[key]), exist_ok=True)
