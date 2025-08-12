import hashlib
import json
import logging
import logging.handlers
import math
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import bleach
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ---------------- Logging ----------------


def get_logger(name="pipeline", log_file=None):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        '{"ts":"%(asctime)s","level":"%(levelname)s","step":"%(name)s","msg":"%(message)s"}'
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


log = get_logger("pipeline", os.path.join(BASE, "logs", "pipeline.log"))

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
    niches: List[str] = ["ai tools", "raspberry pi tips", "space trivia"]
    category_ids: List[int] = [27, 28]
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


def _default_whisper_paths():
    """Smart defaults for whisper.cpp paths based on platform"""
    import platform
    home = os.path.expanduser("~")
    
    # Check common whisper.cpp locations
    possible_paths = [
        f"{home}/whisper.cpp/build/bin/whisper-cli",  # Standard user install
        "/usr/local/bin/whisper-cli",                 # System install
        "/opt/whisper.cpp/build/bin/whisper-cli",     # Alternative location
    ]
    
    possible_models = [
        f"{home}/whisper.cpp/models/ggml-base.en.bin",
        "/usr/local/share/whisper.cpp/models/ggml-base.en.bin",
        "/opt/whisper.cpp/models/ggml-base.en.bin",
    ]
    
    # Find first existing binary
    binary_path = None
    for path in possible_paths:
        if os.path.exists(path):
            binary_path = path
            break
    
    # Find first existing model
    model_path = None
    for path in possible_models:
        if os.path.exists(path):
            model_path = path
            break
    
    # Fallback to standard Pi paths if nothing found
    return {
        "binary": binary_path or f"{home}/whisper.cpp/build/bin/whisper-cli",
        "model": model_path or f"{home}/whisper.cpp/models/ggml-base.en.bin"
    }

class ASRCfg(BaseModel):
    provider: str = "whisper_cpp"
    whisper_cpp_path: str = Field(default_factory=lambda: _default_whisper_paths()["binary"])
    model: str = Field(default_factory=lambda: _default_whisper_paths()["model"])
    openai_enabled: bool = False


class TTSCfg(BaseModel):
    provider: str = "piper"
    voice: str = "en_US-amy-medium"
    voice_id: str = "en_US-amy-medium"
    rate_wpm: int = 165
    ssml: bool = True
    lufs_target: float = -16.0
    openai_enabled: bool = False


class AssetsCfg(BaseModel):
    providers: List[str] = ["pixabay", "pexels"]
    max_per_section: int = 3


class RenderCfg(BaseModel):
    resolution: str = "1920x1080"
    fps: int = 30
    music_db: int = -22
    duck_db: int = -15
    xfade_ms: int = 250
    target_bitrate: str = "4000k"
    codec: str = "h264_videotoolbox"  # Hardware acceleration
    preset: str = "fast"  # Encoding speed vs quality trade-off
    crf: int = 23  # Quality setting (18-28 range, lower = better quality)
    threads: int = 0  # Auto-detect optimal thread count
    use_hardware_acceleration: bool = True  # Enable/disable hardware acceleration


class UploadCfg(BaseModel):
    auto_upload: bool = False
    visibility: str = "public"
    schedule: Optional[str] = None


class LicensesCfg(BaseModel):
    require_attribution: bool = True


class LimitsCfg(BaseModel):
    max_retries: int = 2


class VideoCfg(BaseModel):
    animatics_only: bool = True
    enable_legacy_stock: bool = False
    min_coverage: float = 0.85


class ProceduralCfg(BaseModel):
    max_colors_per_scene: int = 3
    seed: Optional[int] = 42
    placement: Optional[Dict[str, Any]] = Field(default_factory=lambda: {
        "min_spacing_px": 64,
        "safe_margin_px": 40
    })
    layout: Optional[Dict[str, Any]] = Field(default_factory=lambda: {
        "strategy": "auto",
        "prefer_thirds": True,
        "max_attempts": 200
    })


class TextureGrainCfg(BaseModel):
    density: float = 0.15
    scale: float = 2.0
    intensity: float = 0.08
    seed_variation: bool = True


class TextureEdgesCfg(BaseModel):
    feather_radius: float = 1.5
    posterization_levels: int = 8
    edge_strength: float = 0.3


class TextureHalftoneCfg(BaseModel):
    enabled: bool = True
    dot_size: float = 1.2
    dot_spacing: float = 3.0
    angle: int = 45
    intensity: float = 0.12


class TextureCfg(BaseModel):
    enabled: bool = True
    cache_dir: str = "render_cache/textures"
    session_based: bool = True
    grain: TextureGrainCfg = Field(default_factory=TextureGrainCfg)
    edges: TextureEdgesCfg = Field(default_factory=TextureEdgesCfg)
    halftone: TextureHalftoneCfg = Field(default_factory=TextureHalftoneCfg)
    color_preservation: bool = True
    brand_palette_only: bool = True


class GlobalCfg(BaseModel):
    storage: StorageCfg
    pipeline: PipelineCfg
    llm: LLMCfg
    asr: ASRCfg
    tts: TTSCfg
    assets: AssetsCfg
    video: VideoCfg
    render: RenderCfg
    upload: UploadCfg
    licenses: LicensesCfg
    limits: LimitsCfg = Field(default_factory=LimitsCfg)
    procedural: ProceduralCfg = Field(default_factory=ProceduralCfg)
    textures: TextureCfg = Field(default_factory=TextureCfg)


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> GlobalCfg:
    path = os.path.join(BASE, "conf", "global.yaml")
    if not os.path.exists(path):
        path = os.path.join(BASE, "conf", "global.example.yaml")
    raw = load_yaml(path)
    
    # Handle auto-detection for whisper.cpp paths
    if raw.get("asr", {}).get("whisper_cpp_path") == "auto":
        defaults = _default_whisper_paths()
        raw["asr"]["whisper_cpp_path"] = defaults["binary"]
    
    if raw.get("asr", {}).get("model") == "auto":
        defaults = _default_whisper_paths()
        raw["asr"]["model"] = defaults["model"]
    
    # Handle relative base_dir
    if raw.get("storage", {}).get("base_dir") == ".":
        raw["storage"]["base_dir"] = BASE
    
    try:
        cfg = GlobalCfg(**raw)
    except ValidationError as e:
        log.error(f"Config validation failed: {e}")
        raise
    return cfg


# ---------------- Env & Validation ----------------


def load_env() -> dict:
    load_dotenv(os.path.join(BASE, ".env"))
    env = {k: v for k, v in os.environ.items()}
    return env


def load_blog_cfg():
    """Load blog configuration from blog.yaml (with fallback to example)"""
    p = os.path.join(BASE, "conf", "blog.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "blog.example.yaml")
    import yaml
    return yaml.safe_load(open(p, "r", encoding="utf-8"))


def load_modules_cfg():
    """Load modules configuration from modules.yaml"""
    p = os.path.join(BASE, "conf", "modules.yaml")
    if not os.path.exists(p):
        log.warning("modules.yaml not found, using empty configuration")
        return {}
    import yaml
    return yaml.safe_load(open(p, "r", encoding="utf-8"))


def load_brief():
    """Load workstream brief from conf/brief.yaml or conf/brief.md"""
    try:
        from .brief_loader import load_brief as _load_brief
        return _load_brief()
    except ImportError:
        # Fallback if brief_loader is not available
        log.warning("brief_loader not available, using empty brief")
        return {
            "title": "",
            "audience": [],
            "tone": "informative",
            "video": {"target_length_min": 5, "target_length_max": 7},
            "blog": {"words_min": 900, "words_max": 1300},
            "keywords_include": [],
            "keywords_exclude": [],
            "sources_preferred": [],
            "monetization": {"primary": ["lead_magnet", "email_capture"], "cta_text": "Download our free guide"},
            "notes": ""
        }


def create_brief_context(brief: dict) -> str:
    """Create a standardized brief context string for injection into prompts"""
    if not brief:
        return ""
    
    context_parts = []
    
    if brief.get('title'):
        context_parts.append(f"Title: {brief['title']}")
    
    if brief.get('audience'):
        audience_str = ', '.join(brief['audience'])
        context_parts.append(f"Audience: {audience_str}")
    
    if brief.get('tone'):
        context_parts.append(f"Tone: {brief['tone']}")
    
    if brief.get('keywords_include'):
        keywords_str = ', '.join(brief['keywords_include'])
        context_parts.append(f"Keywords to include: {keywords_str}")
    
    if brief.get('keywords_exclude'):
        exclude_str = ', '.join(brief['keywords_exclude'])
        context_parts.append(f"Keywords to exclude: {exclude_str}")
    
    if brief.get('video', {}).get('target_length_min') and brief.get('video', {}).get('target_length_max'):
        context_parts.append(f"Video target: {brief['video']['target_length_min']}-{brief['video']['target_length_max']} minutes")
    
    if brief.get('blog', {}).get('words_min') and brief.get('blog', {}).get('words_max'):
        context_parts.append(f"Blog target: {brief['blog']['words_min']}-{brief['blog']['words_max']} words")
    
    if brief.get('sources_preferred'):
        sources_str = ', '.join(brief['sources_preferred'])
        context_parts.append(f"Preferred sources: {sources_str}")
    
    if brief.get('notes'):
        context_parts.append(f"Notes: {brief['notes']}")
    
    if context_parts:
        return "BRIEF CONTEXT:\n" + "\n".join(context_parts) + "\n\n"
    
    return ""


def filter_content_by_brief(content: str, brief: dict) -> tuple[str, list[str]]:
    """
    Filter content based on brief keywords_exclude and return filtered content with rejection reasons.
    
    Args:
        content: Text content to filter
        brief: Brief configuration with keywords_exclude
        
    Returns:
        Tuple of (filtered_content, rejection_reasons)
    """
    if not brief or not brief.get('keywords_exclude'):
        return content, []
    
    exclude_terms = [term.lower().strip() for term in brief['keywords_exclude']]
    content_lower = content.lower()
    rejection_reasons = []
    
    for term in exclude_terms:
        if term in content_lower:
            rejection_reasons.append(f"Contains excluded term: '{term}'")
    
    if rejection_reasons:
        log.warning(f"Content rejected due to excluded terms: {rejection_reasons}")
        return "", rejection_reasons
    
    return content, rejection_reasons


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


def log_state(step: str, status: str = "OK", notes: str = ""):
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "step": step,
        "status": status,
        "notes": notes,
    }
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
        out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True).strip()
        # temp=48.0'C
        m = re.search(r"temp=([\d\.]+)", out)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def disk_free_gb(path: str) -> float:
    total, used, free = shutil.disk_usage(path)
    return round(free / 1e9, 2)


def guard_system(cfg: GlobalCfg, min_free_gb: float = 5.0, max_temp_c: float = 75.0):
    t = cpu_temp_c()
    if t is not None and t > max_temp_c:
        log_state("guard", "DEFERRED", f"cpu_temp_c={t}")
        time.sleep(60)
        sys.exit(0)
    free = disk_free_gb(cfg.storage.base_dir)
    if free < min_free_gb:
        log_state("guard", "FAIL", f"low_disk_free_gb={free}")
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


ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union(
    {
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "ul",
        "ol",
        "li",
        "strong",
        "em",
        "blockquote",
        "code",
        "pre",
        "img",
        "figure",
        "figcaption",
    }
)
ALLOWED_ATTRS = {
    "img": ["src", "alt", "title", "width", "height"],
    "a": ["href", "title", "rel", "target"],
}


def sanitize_html(html: str) -> str:
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


# ---------------- Hashing & Dedupe ----------------


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def sha1_file(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", text)


# ---------------- Beat Timing (fallback) ----------------


def estimate_beats(script_text: str, target_sec: int = 420, wpm: int = 160) -> List[Dict[str, Any]]:
    # Split by sentences; rough duration by words count / wps
    parts = re.split(r"(?<=[.!?])\s+", script_text.strip())
    words = sum(len(p.split()) for p in parts if p.strip())
    wps = max(wpm / 60.0, 1.0)
    scale = target_sec / max(words / wps, 1.0)
    beats = []
    for p in parts:
        if not p.strip():
            continue
        sec = max(round((len(p.split()) / wps) * scale, 2), 1.5)
        # Match first B-ROLL tag in the sentence
        m = re.search(r"\[B-ROLL:\s*([^\]]+)\]", p, flags=re.I)
        bq = m.group(1) if m else ""
        beats.append({"text": p, "sec": float(sec), "broll": bq})
    return beats


# ---------------- Schema.org Article ----------------


def schema_article(
    title: str, desc: str, url: str, img_url: str, author_name: str = "Editor"
) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": desc,
        "author": {"@type": "Person", "name": author_name},
        "image": img_url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "datePublished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return json.dumps(data)


# ---------------- Publish Flags & DRY_RUN Governance ----------------


def get_publish_flags(cli_dry_run: bool = False, target: str = "both") -> Dict[str, bool]:
    """
    Centralized publish flag governance with clear precedence hierarchy.
    
    Args:
        cli_dry_run: CLI --dry-run flag state
        target: "youtube", "blog", or "both" - which publish flags to return
        
    Returns:
        Dict with flags: {"youtube_dry_run": bool, "blog_dry_run": bool, "blog_publish_enabled": bool}
        
    Precedence (highest to lowest):
        1. CLI flags (--dry-run)
        2. Environment variables (YOUTUBE_UPLOAD_DRY_RUN, BLOG_DRY_RUN)
        3. Config files (blog.yaml wordpress.publish_enabled)
        4. Safe defaults (dry_run=True, publish_enabled=False)
    """
    env = load_env()
    flags = {}
    
    # YouTube publish flags
    if target in ("youtube", "both"):
        if cli_dry_run:
            # CLI override: force dry-run
            flags["youtube_dry_run"] = True
        else:
            # Check environment variable (default to safe dry-run)
            env_dry = env.get("YOUTUBE_UPLOAD_DRY_RUN", "true").lower() in ("1", "true", "yes")
            flags["youtube_dry_run"] = env_dry
    
    # Blog publish flags  
    if target in ("blog", "both"):
        if cli_dry_run:
            # CLI override: force dry-run
            flags["blog_dry_run"] = True
            flags["blog_publish_enabled"] = False
        else:
            # Check environment variable first
            env_blog_dry = env.get("BLOG_DRY_RUN", "true").lower() in ("1", "true", "yes")
            flags["blog_dry_run"] = env_blog_dry
            
            # Check blog config for publish_enabled (independent of dry_run)
            try:
                blog_cfg = load_blog_cfg()
                publish_enabled = blog_cfg.get("wordpress", {}).get("publish_enabled", False)
                flags["blog_publish_enabled"] = publish_enabled
                
                # If publish is disabled in config, force dry-run regardless of env
                if not publish_enabled:
                    flags["blog_dry_run"] = True
                    
            except Exception as e:
                log.warning(f"Failed to load blog config for publish flags: {e}")
                flags["blog_publish_enabled"] = False
                flags["blog_dry_run"] = True
    
    return flags


def should_publish_youtube(cli_dry_run: bool = False) -> bool:
    """Check if YouTube upload should be live (not dry-run)"""
    flags = get_publish_flags(cli_dry_run, target="youtube")
    return not flags["youtube_dry_run"]


def should_publish_blog(cli_dry_run: bool = False) -> bool:
    """Check if blog post should be published to WordPress (not dry-run and enabled)"""
    flags = get_publish_flags(cli_dry_run, target="blog")
    return not flags["blog_dry_run"] and flags["blog_publish_enabled"]


def get_publish_summary(cli_dry_run: bool = False) -> str:
    """Get human-readable summary of current publish settings"""
    flags = get_publish_flags(cli_dry_run, target="both")
    
    lines = []
    lines.append("=== PUBLISH FLAGS SUMMARY ===")
    
    # YouTube
    yt_status = "DRY-RUN" if flags["youtube_dry_run"] else "LIVE"
    lines.append(f"YouTube Upload: {yt_status}")
    
    # Blog  
    if not flags["blog_publish_enabled"]:
        blog_status = "DISABLED (staging only)"
    elif flags["blog_dry_run"]:
        blog_status = "DRY-RUN"
    else:
        blog_status = "LIVE"
    lines.append(f"Blog Publishing: {blog_status}")
    
    # Instructions
    lines.append("")
    lines.append("To change settings:")
    lines.append("- CLI: Use --dry-run flag")
    lines.append("- Env: Set YOUTUBE_UPLOAD_DRY_RUN=false, BLOG_DRY_RUN=false")
    lines.append("- Config: Set wordpress.publish_enabled=true in conf/blog.yaml")
    
    return "\n".join(lines)
