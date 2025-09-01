# tests/test_config_loading.py
import io
import os
from pathlib import Path
import sys
import tempfile
import yaml

from bin.utils.config import load_research_config, load_models_config, ModelsConfig
from bin.config.research import ResearchConfig

def write_yaml(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, sort_keys=False)

def test_load_research_config_dot_access(tmp_path):
    y = {
        "policy": {
            "mode": "reuse",
            "allow_providers": ["fixtures", "web"],
            "min_citations": 3,
            "coverage_threshold": 0.7,
            "fact_guard": "block",
            "rate_limits": {"web": {"max_rps": 2.0, "burst": 4}},
            "domain_scores": {"example.com": 0.1, "nature.com": 0.95}
        }
    }
    p = tmp_path / "research.yaml"
    write_yaml(p, y)
    cfg = load_research_config(str(p))
    assert isinstance(cfg, ResearchConfig)
    assert cfg.policy.min_citations == 3
    assert cfg.policy.rate_limits["web"].max_rps == 2.0
    assert cfg.policy.domain_scores["nature.com"] == 0.95

def test_research_config_back_compat_shim(tmp_path):
    # legacy file without 'policy' wrapper
    y = {
        "min_citations": 2,
        "coverage_threshold": 0.6,
        "domain_scores": {"wiki": 0.8}
    }
    p = tmp_path / "research.yaml"
    write_yaml(p, y)
    cfg = load_research_config(str(p))
    assert cfg.policy.min_citations == 2
    assert cfg.policy.coverage_threshold == 0.6
    assert cfg.policy.domain_scores["wiki"] == 0.8

def test_models_config_ignores_policy_and_warns(tmp_path, capsys):
    y = {
        "script_model": "llama3.2:3b",
        "allow_providers": ["should_not_be_here"]
    }
    p = tmp_path / "models.yaml"
    write_yaml(p, y)
    cfg = load_models_config(str(p))
    assert isinstance(cfg, ModelsConfig)
    assert cfg.script_model == "llama3.2:3b"
    # warning emitted
    captured = capsys.readouterr()
    assert "WARNING: research policy keys" in captured.err

def test_research_config_extra_fields_allowed(tmp_path):
    y = {
        "policy": {
            "mode": "reuse",
            "min_citations": 1
        },
        "extra_field": "should_be_allowed",
        "another_extra": {"nested": "value"}
    }
    p = tmp_path / "research.yaml"
    write_yaml(p, y)
    cfg = load_research_config(str(p))
    assert cfg.policy.min_citations == 1
    # Extra fields should be accessible
    assert hasattr(cfg, 'extra_field')
    assert cfg.extra_field == "should_be_allowed"

def test_models_config_extra_fields_allowed(tmp_path):
    y = {
        "script_model": "llama3.2:3b",
        "extra_model_field": "should_be_allowed"
    }
    p = tmp_path / "models.yaml"
    write_yaml(p, y)
    cfg = load_models_config(str(p))
    assert cfg.script_model == "llama3.2:3b"
    # Extra fields should be accessible
    assert hasattr(cfg, 'extra_model_field')
    assert cfg.extra_model_field == "should_be_allowed"

def test_research_config_defaults():
    cfg = load_research_config("nonexistent.yaml")
    assert isinstance(cfg, ResearchConfig)
    assert cfg.policy.mode == "reuse"
    assert cfg.policy.min_citations == 1
    assert cfg.policy.coverage_threshold == 0.6
    assert cfg.policy.fact_guard == "block"

def test_models_config_defaults():
    cfg = load_models_config("nonexistent.yaml")
    assert isinstance(cfg, ModelsConfig)
    assert cfg.script_model is None
    assert cfg.outline_model is None
