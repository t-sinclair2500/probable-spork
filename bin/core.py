import os, sys, json, time, hashlib, math, subprocess, shutil, re
from typing import Any, Dict, Optional, List
from contextlib import contextmanager
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
import yaml
import logging
import logging.handlers
import bleach

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ---------------- Logging ----------------

def get_logger(name="pipeline", log_file=None):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter('{"ts":"%(asctime)s","level":"%(levelname)s","step":"%(name)s","msg":"%(message)s"}')
    sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt); logger.addHandler(sh)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5)
        fh.setFormatter(fmt); logger.addHandler(fh)
    return logger

log = get_logger("pipeline", os.path.join(BASE,"logs","pipeline.log"))

# ---------------- Config Models ----------------

class LLMCfg(BaseModel):
    provider: str = "ollama"
    model: str = "phi3:mini"
    endpoint: str = "http://127.0.0.1:11434/api/generate"
    temperature: float = 0.7
    max_tokens: int = 1200

class PipelineCfg(BaseModel):
    daily_videos: int = 1
    video_length_seconds: int = 420
    tone: str = "conversational"
    niches: List[str] = ["ai tools","raspberry pi tips","space trivia"]
    category_ids: List[int] = [27,28]
    enable_captions: bool = True
    enable_thumbnails: bool = True
    pacing_cooldown_seconds: int = 60

class StorageCfg(BaseModel):
    base_dir: str = Field(default_factory=lambda: BASE)
    videos_dir: str = "videos"
    assets_dir: str = "assets"
    scripts_dir: str = "scripts"
    voiceovers_dir: str = "voiceovers"
    logs_dir: str = "logs"
    data_dir: str = "data"
    jobs_dir: str = "jobs"

class ASRCfg(BaseModel):
    provider: str = "whisper_cpp"
    whisper_cpp_path: str = "/home/pi/whisper.cpp/main"
    model: str = "ggml-base.en.bin"
    openai_enabled: bool = False

class TTSCfg(BaseModel):
    provider: str = "coqui"
    voice: str = "tts_models/en/ljspeech/tacotron2-DDC"
    rate_wpm: int = 165
    openai_enabled: bool = False

class AssetsCfg(BaseModel):
    providers: List[str] = ["pixabay","pexels"]
    max_per_section: int = 3

class RenderCfg(BaseModel):
    resolution: str = "1920x1080"
    fps: int = 30
    music_db: int = -22
    duck_db: int = -15
    xfade_ms: int = 250
    target_bitrate: str = "4000k"

class UploadCfg(BaseModel):
    auto_upload: bool = False
    visibility: str = "public"
    schedule: Optional[str] = None

class LicensesCfg(BaseModel):
    require_attribution: bool = True

class GlobalCfg(BaseModel):
    storage: StorageCfg
    pipeline: PipelineCfg
    llm: LLMCfg
    asr: ASRCfg
    tts: TTSCfg
    assets: AssetsCfg
    render: RenderCfg
    upload: UploadCfg
    licenses: LicensesCfg

def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_config() -> GlobalCfg:
    path = os.path.join(BASE, "conf", "global.yaml")
    if not os.path.exists(path):
        path = os.path.join(BASE, "conf", "global.example.yaml")
    raw = load_yaml(path)
    try:
        cfg = GlobalCfg(**raw)
    except ValidationError as e:
        log.error(f"Config validation failed: {e}")
        raise
    return cfg

# ---------------- Env & Validation ----------------

def load_env() -> dict:
    load_dotenv(os.path.join(BASE, ".env"))
    env = {k:v for k,v in os.environ.items()}
    return env

def require_keys(env: dict, keys: List[str], feature_name: str):
    missing = [k for k in keys if not env.get(k)]
    if missing:
        raise SystemExit(f"{feature_name} requires missing env keys: {missing}")

# ---------------- Locking ----------------

@contextmanager
def single_lock():
    lock_path = os.path.join(BASE, "jobs", "lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        import fcntl
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError:
        log.info("Another job is running. Exiting.")
        sys.exit(0)
    finally:
        try:
            import fcntl
            fcntl.lockf(fd, fcntl.LOCK_UN)
            os.close(fd)
            os.remove(lock_path)
        except Exception:
            pass

def log_state(step: str, status: str="OK", notes: str=""):
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "step": step, "status": status, "notes": notes}
    path = os.path.join(BASE, "jobs", "state.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    log.info(json.dumps(rec))

def paced_sleep(cfg: GlobalCfg):
    secs = int(cfg.pipeline.pacing_cooldown_seconds)
    time.sleep(secs)

# ---------------- Guards ----------------

def cpu_temp_c() -> Optional[float]:
    try:
        out = subprocess.check_output(["vcgencmd","measure_temp"], text=True).strip()
        # temp=48.0'C
        m = re.search(r"temp=([\d\.]+)", out)
        return float(m.group(1)) if m else None
    except Exception:
        return None

def disk_free_gb(path: str) -> float:
    total, used, free = shutil.disk_usage(path)
    return round(free/1e9,2)

def guard_system(cfg: GlobalCfg, min_free_gb: float=5.0, max_temp_c: float=75.0):
    t = cpu_temp_c()
    if t is not None and t > max_temp_c:
        log_state("guard","DEFERRED", f"cpu_temp_c={t}")
        time.sleep(60)
        sys.exit(0)
    free = disk_free_gb(cfg.storage.base_dir)
    if free < min_free_gb:
        log_state("guard","FAIL", f"low_disk_free_gb={free}")
        raise SystemExit(f"Low disk space: {free} GB")

# ---------------- JSON & Sanitization ----------------

def parse_llm_json(text: str) -> dict:
    # Remove code fences and leading/trailing junk
    text = text.strip()
    text = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.DOTALL)
    text = text.strip()
    # Attempt direct parse; fallback extract first {...}
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception as e:
                raise ValueError(f"Failed to parse LLM JSON: {e}")
        raise ValueError("No JSON object found in LLM output.")

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union({"p","h1","h2","h3","h4","ul","ol","li","strong","em","blockquote","code","pre","img","figure","figcaption"})
ALLOWED_ATTRS = {"img": ["src","alt","title","width","height"], "a": ["href","title","rel","target"]}

def sanitize_html(html: str) -> str:
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

# ---------------- Hashing & Dedupe ----------------

def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()

def sha1_file(path: str) -> str:
    h = hashlib.sha1()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", text)

# ---------------- Beat Timing (fallback) ----------------

def estimate_beats(script_text: str, target_sec: int=420, wpm: int=160) -> List[Dict[str, Any]]:
    # Split by sentences; rough duration by words count / wps
    parts = re.split(r"(?<=[.!?])\s+", script_text.strip())
    words = sum(len(p.split()) for p in parts if p.strip())
    wps = max(wpm/60.0, 1.0)
    scale = target_sec / max(words / wps, 1.0)
    beats = []
    for p in parts:
        if not p.strip(): continue
        sec = max(round((len(p.split())/wps) * scale, 2), 1.5)
        # Match first B-ROLL tag in the sentence
        m = re.search(r"\[B-ROLL:\s*([^\]]+)\]", p, flags=re.I)
        bq = m.group(1) if m else ""
        beats.append({"text": p, "sec": float(sec), "broll": bq})
    return beats

# ---------------- Schema.org Article ----------------

def schema_article(title: str, desc: str, url: str, img_url: str, author_name: str="Editor") -> str:
    data = {
        "@context":"https://schema.org",
        "@type":"Article",
        "headline": title,
        "description": desc,
        "author": {"@type":"Person","name": author_name},
        "image": img_url,
        "mainEntityOfPage": {"@type":"WebPage","@id": url},
        "datePublished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    return json.dumps(data)
