# bin/utils/config.py
import os
import sys
from typing import Any, Dict, Optional
from pathlib import Path

try:
    import yaml
except Exception as e:  # pragma: no cover
    raise RuntimeError("PyYAML is required: pip install pyyaml") from e

from pydantic import BaseModel, Field
from bin.config.research import ResearchConfig as LegacyResearchConfig, ResearchPolicy as LegacyResearchPolicy
from bin.config.pipeline import PipelineConfig as LegacyPipelineConfig

# New unified schemas (non-breaking; legacy loaders preserved)
try:  # optional import for greenlight bundle
    from bin.config.schemas import (
        Bundle,
        GlobalConfig,
        PipelineConfig,
        ResearchConfig,
        ModelsConfig,
    )
except Exception:  # pragma: no cover
    Bundle = None  # type: ignore
    GlobalConfig = None  # type: ignore
    PipelineConfig = None  # type: ignore
    ResearchConfig = None  # type: ignore
    ModelsConfig = None  # type: ignore

def _read_yaml(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError(f"YAML at {path} must be a mapping/object.")
        return data

def load_research_config(path: str = "conf/research.yaml") -> LegacyResearchConfig:
    """
    Load research policy exclusively from conf/research.yaml.
    Back-compat: if top-level keys look like policy (e.g., min_citations), wrap them under 'policy'.
    """
    data = _read_yaml(path)
    if "policy" not in data:
        # Back-compat shim: move likely policy keys into a 'policy' block
        possible_keys = {
            "mode", "allow_providers", "deny_providers", "min_citations",
            "coverage_threshold", "fact_guard", "rate_limits", "domain_scores",
            "min_domain_score"
        }
        policy_blob = {k: v for k, v in data.items() if k in possible_keys}
        if policy_blob:
            data = {"policy": policy_blob, **{k: v for k, v in data.items() if k not in possible_keys}}
    return LegacyResearchConfig(**data)

class ModelsConfigShim(BaseModel):
    # Keep only model identifiers/names. No research policy here.
    script_model: Optional[str] = Field(None)
    outline_model: Optional[str] = Field(None)
    caption_asr_model: Optional[str] = Field(None)
    tts_voice: Optional[str] = Field(None)
    # add other pure model-name fields as needed

    class Config:
        extra = "allow"   # tolerate legacy keys; they will be ignored by code

def load_models_config(path: str = "conf/models.yaml") -> ModelsConfigShim:
    data = _read_yaml(path)
    # Warn if legacy research keys are present here; they will be ignored.
    legacy_keys = {"allow_providers", "deny_providers", "rate_limits", "domain_scores", "min_citations", "coverage_threshold", "fact_guard", "mode", "min_domain_score", "policy"}
    if any(k in data for k in legacy_keys):
        print(
            "[config] WARNING: research policy keys found in conf/models.yaml; they are ignored. "
            "Move all research/grounding policy into conf/research.yaml under 'policy'.",
            file=sys.stderr
        )
    return ModelsConfigShim(**data)

def load_pipeline_config(path: str = "conf/pipeline.yaml") -> LegacyPipelineConfig:
    data = _read_yaml(path)
    # Back-compat shim: if not wrapped, allow top-level map to be the "steps"
    if "steps" not in data and isinstance(data, dict):
        data = {"steps": data}
    return LegacyPipelineConfig(**data)


# ---------- Greenlight unified loader with strict precedence ----------
def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _env_overlay() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if os.getenv("OLLAMA_BASE_URL"):
        out.setdefault("models", {}).setdefault("ollama", {})["base_url"] = os.getenv("OLLAMA_BASE_URL")
    if os.getenv("OLLAMA_TIMEOUT_SEC"):
        try:
            out.setdefault("models", {}).setdefault("ollama", {})["timeout_sec"] = float(os.getenv("OLLAMA_TIMEOUT_SEC") or 0)
        except Exception:
            pass
    if os.getenv("SHORT_RUN_SECS"):
        try:
            out.setdefault("global", {}).setdefault("performance", {})["pacing_cooldown_seconds"] = int(os.getenv("SHORT_RUN_SECS") or 0)
        except Exception:
            pass
    return out


def _profile_overlay(profile: Optional[str]) -> Dict[str, Any]:
    if not profile:
        return {}
    candidates = {
        "m2_8gb_optimized": "conf/m2_8gb_optimized.yaml",
        "pi_8gb": "conf/pi_8gb.yaml",
    }
    path = candidates.get(profile)
    return _read_yaml(path) if path else {}


def load_all_configs(*, profile: Optional[str] = None, cli_overrides: Optional[Dict[str, Any]] = None):
    """
    Greenlight: Load and validate all configs with strict precedence.
    Precedence (low -> high):
      1) Defaults baked into models
      2) conf/*.yaml (base)
      3) Profile overlay
      4) Environment variables
      5) CLI overrides

    Returns a typed Bundle when schemas are available; otherwise a merged dict.
    """
    base_global = _read_yaml("conf/global.yaml")
    base_pipeline = _read_yaml("conf/pipeline.yaml")
    base_research = _read_yaml("conf/research.yaml")
    base_models = _read_yaml("conf/models.yaml")

    merged: Dict[str, Any] = {
        "global": base_global or {},
        "pipeline": base_pipeline or {},
        "research": base_research or {},
        "models": base_models or {},
        "profile": profile,
    }

    merged = _deep_merge(merged, _profile_overlay(profile))
    merged = _deep_merge(merged, _env_overlay())
    if cli_overrides:
        merged = _deep_merge(merged, cli_overrides)

    # Inject defaults via model validation and assign run_id
    import uuid
    if Bundle and GlobalConfig and PipelineConfig and ResearchConfig and ModelsConfig:
        # validate sub-models to apply defaults
        g = GlobalConfig(**(merged.get("global") or {}))
        if not getattr(g, "run_id", None):
            g.run_id = str(uuid.uuid4())
        p = PipelineConfig(**(merged.get("pipeline") or {}))
        r = ResearchConfig(**(merged.get("research") or {}))
        m = ModelsConfig(**(merged.get("models") or {}))
        bundle = Bundle(**{"global": g.dict(), "pipeline": p.dict(), "research": r.dict(), "models": m.dict(), "profile": merged.get("profile")})
        return bundle

    # Fallback: dict merge with run_id
    merged.setdefault("global", {}).setdefault("run_id", str(uuid.uuid4()))
    return merged
