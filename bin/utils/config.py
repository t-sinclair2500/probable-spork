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

from bin.config.pipeline import PipelineConfig as LegacyPipelineConfig
from bin.config.research import ResearchConfig as LegacyResearchConfig

# New unified schemas (non-breaking; legacy loaders preserved)
try:  # optional import for greenlight bundle
    from bin.config.schemas import (
        Bundle,
        GlobalConfig,
        ModelsConfig,
        PipelineConfig,
        ResearchConfig,
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


def read_or_die(
    path: str, required_keys: list, schema_hint: str = ""
) -> Dict[str, Any]:
    """
    Read YAML file and validate required top-level keys exist.

    Args:
        path: Path to YAML file
        required_keys: List of required top-level keys
        schema_hint: Optional hint about the expected schema

    Returns:
        Validated YAML data as dict

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If required keys are missing
    """
    p = Path(path)
    if not p.exists():
        missing_keys_str = ", ".join(required_keys)
        error_msg = f"Configuration file missing: {path}\n"
        error_msg += f"Required keys: {missing_keys_str}\n"
        if schema_hint:
            error_msg += f"Schema hint: {schema_hint}\n"
        error_msg += f"Create {path} with the required configuration."
        raise FileNotFoundError(error_msg)

    try:
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
            if not isinstance(data, dict):
                raise ValueError(f"YAML at {path} must be a mapping/object.")
    except Exception as e:
        raise ValueError(f"Failed to parse {path}: {e}")

    # Check for required keys
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        missing_keys_str = ", ".join(missing_keys)
        error_msg = (
            f"Configuration file {path} is missing required keys: {missing_keys_str}\n"
        )
        error_msg += f"Required keys: {', '.join(required_keys)}\n"
        if schema_hint:
            error_msg += f"Schema hint: {schema_hint}\n"
        error_msg += f"Please add the missing keys to {path}"
        raise ValueError(error_msg)

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
            "mode",
            "allow_providers",
            "deny_providers",
            "min_citations",
            "coverage_threshold",
            "fact_guard",
            "rate_limits",
            "domain_scores",
            "min_domain_score",
        }
        policy_blob = {k: v for k, v in data.items() if k in possible_keys}
        if policy_blob:
            data = {
                "policy": policy_blob,
                **{k: v for k, v in data.items() if k not in possible_keys},
            }
    return LegacyResearchConfig(**data)


class ModelsConfigShim(BaseModel):
    # Keep only model identifiers/names. No research policy here.
    script_model: Optional[str] = Field(None)
    outline_model: Optional[str] = Field(None)
    caption_asr_model: Optional[str] = Field(None)
    tts_voice: Optional[str] = Field(None)
    # add other pure model-name fields as needed

    class Config:
        extra = "allow"  # tolerate legacy keys; they will be ignored by code


def load_models_config(path: str = "conf/models.yaml") -> ModelsConfigShim:
    data = _read_yaml(path)
    # Warn if legacy research keys are present here; they will be ignored.
    legacy_keys = {
        "allow_providers",
        "deny_providers",
        "rate_limits",
        "domain_scores",
        "min_citations",
        "coverage_threshold",
        "fact_guard",
        "mode",
        "min_domain_score",
        "policy",
    }
    if any(k in data for k in legacy_keys):
        print(
            "[config] WARNING: research policy keys found in conf/models.yaml; they are ignored. "
            "Move all research/grounding policy into conf/research.yaml under 'policy'.",
            file=sys.stderr,
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
        out.setdefault("models", {}).setdefault("ollama", {})["base_url"] = os.getenv(
            "OLLAMA_BASE_URL"
        )
    if os.getenv("OLLAMA_TIMEOUT_SEC"):
        try:
            out.setdefault("models", {}).setdefault("ollama", {})["timeout_sec"] = (
                float(os.getenv("OLLAMA_TIMEOUT_SEC") or 0)
            )
        except Exception:
            pass
    if os.getenv("SHORT_RUN_SECS"):
        try:
            out.setdefault("global", {}).setdefault("performance", {})[
                "pacing_cooldown_seconds"
            ] = int(os.getenv("SHORT_RUN_SECS") or 0)
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


def load_all_configs(
    *, profile: Optional[str] = None, cli_overrides: Optional[Dict[str, Any]] = None
):
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
        bundle = Bundle(
            **{
                "global": g.dict(),
                "pipeline": p.dict(),
                "research": r.dict(),
                "models": m.dict(),
                "profile": merged.get("profile"),
            }
        )
        return bundle

    # Fallback: dict merge with run_id
    merged.setdefault("global", {}).setdefault("run_id", str(uuid.uuid4()))
    return merged


def get_research_policy(bundle=None) -> "ResearchPolicy":
    """
    Get research policy from unified config bundle.

    Args:
        bundle: Optional config bundle from load_all_configs()

    Returns:
        ResearchPolicy object with validated research settings
    """
    if bundle is None:
        bundle = load_all_configs()

    # Handle both Bundle and dict return types
    if hasattr(bundle, "research") and hasattr(bundle.research, "policy"):
        return bundle.research.policy
    elif isinstance(bundle, dict) and "research" in bundle:
        # Fallback for dict-based config
        from bin.config.research import ResearchPolicy as LegacyResearchPolicy

        research_data = bundle["research"]
        if "policy" in research_data:
            return LegacyResearchPolicy(**research_data["policy"])
        else:
            # Back-compat: treat top-level as policy
            return LegacyResearchPolicy(**research_data)
    else:
        # Ultimate fallback: load directly
        return load_research_config().policy
