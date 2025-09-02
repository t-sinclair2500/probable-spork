"""
Tests for configuration unification:
- Research policy source validation
- Pydantic model validation
- Config precedence enforcement
"""

import os
from unittest.mock import patch

import pytest


def test_research_policy_source(monkeypatch, tmp_path):
    """Test that research policy is loaded from conf/research.yaml only."""
    # Create test config files
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()

    # Create research.yaml with policy
    research_yaml = conf_dir / "research.yaml"
    research_yaml.write_text(
        """
policy:
  mode: reuse
  min_citations: 2
  allow_providers: ["local_fixtures"]
""",
        encoding="utf-8",
    )

    # Create models.yaml with model names only
    models_yaml = conf_dir / "models.yaml"
    models_yaml.write_text(
        """
defaults:
  chat_model: llama3.2:3b
  generate_model: llama3.2:3b
""",
        encoding="utf-8",
    )

    # Create other required configs
    global_yaml = conf_dir / "global.yaml"
    global_yaml.write_text(
        "performance:\n  max_concurrent_renders: 1", encoding="utf-8"
    )

    pipeline_yaml = conf_dir / "pipeline.yaml"
    pipeline_yaml.write_text("steps:\n  test:\n    required: true", encoding="utf-8")

    # Mock the current working directory
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        from bin.utils.config import get_research_policy, load_all_configs

        bundle = load_all_configs()
        pol = get_research_policy(bundle)

        # Verify research policy comes from research.yaml
        assert pol.mode == "reuse"
        assert pol.min_citations == 2
        assert "local_fixtures" in pol.allow_providers

    finally:
        os.chdir(original_cwd)


def test_models_config_names_only(monkeypatch, tmp_path):
    """Test that models.yaml contains only model names and options."""
    # Create test config files
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()

    # Create models.yaml with model names only
    models_yaml = conf_dir / "models.yaml"
    models_yaml.write_text(
        """
defaults:
  chat_model: llama3.2:3b
  generate_model: llama3.2:3b
  embeddings_model: nomic-embed-text

options:
  num_ctx: 4096
  temperature: 0.4
  seed: 1337
""",
        encoding="utf-8",
    )

    # Create other required configs
    global_yaml = conf_dir / "global.yaml"
    global_yaml.write_text(
        "performance:\n  max_concurrent_renders: 1", encoding="utf-8"
    )

    pipeline_yaml = conf_dir / "pipeline.yaml"
    pipeline_yaml.write_text("steps:\n  test:\n    required: true", encoding="utf-8")

    research_yaml = conf_dir / "research.yaml"
    research_yaml.write_text(
        "policy:\n  mode: reuse\n  min_citations: 1", encoding="utf-8"
    )

    # Mock the current working directory
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        from bin.utils.config import load_all_configs

        bundle = load_all_configs()

        # Verify models config contains only model-related data
        if hasattr(bundle, "models"):
            models_data = bundle.models
        else:
            models_data = bundle.get("models", {})

        # Should have model defaults and options
        assert "defaults" in models_data or hasattr(models_data, "defaults")
        assert "options" in models_data or hasattr(models_data, "options")

        # Should NOT have research policy
        assert not hasattr(models_data, "policy")
        assert "policy" not in models_data if isinstance(models_data, dict) else True

    finally:
        os.chdir(original_cwd)


def test_invalid_research_config_fails_fast(monkeypatch, tmp_path):
    """Test that invalid research config raises validation errors."""
    # Create test config files
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()

    # Create research.yaml with invalid policy
    research_yaml = conf_dir / "research.yaml"
    research_yaml.write_text(
        """
policy:
  mode: invalid_mode  # Invalid mode
  min_citations: -1   # Invalid negative value
""",
        encoding="utf-8",
    )

    # Create other required configs
    global_yaml = conf_dir / "global.yaml"
    global_yaml.write_text(
        "performance:\n  max_concurrent_renders: 1", encoding="utf-8"
    )

    pipeline_yaml = conf_dir / "pipeline.yaml"
    pipeline_yaml.write_text("steps:\n  test:\n    required: true", encoding="utf-8")

    models_yaml = conf_dir / "models.yaml"
    models_yaml.write_text("defaults:\n  chat_model: llama3.2:3b", encoding="utf-8")

    # Mock the current working directory
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        from bin.utils.config import load_all_configs

        # Should raise validation error for invalid config
        with pytest.raises(Exception):
            load_all_configs()

    finally:
        os.chdir(original_cwd)


def test_config_precedence_profile_overlay(monkeypatch, tmp_path):
    """Test that profile overlays are applied correctly."""
    # Create test config files
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()

    # Create base configs
    global_yaml = conf_dir / "global.yaml"
    global_yaml.write_text(
        "performance:\n  max_concurrent_renders: 1", encoding="utf-8"
    )

    pipeline_yaml = conf_dir / "pipeline.yaml"
    pipeline_yaml.write_text("steps:\n  test:\n    required: true", encoding="utf-8")

    research_yaml = conf_dir / "research.yaml"
    research_yaml.write_text(
        "policy:\n  mode: reuse\n  min_citations: 1", encoding="utf-8"
    )

    models_yaml = conf_dir / "models.yaml"
    models_yaml.write_text("defaults:\n  chat_model: llama3.2:3b", encoding="utf-8")

    # Create profile overlay
    profile_yaml = conf_dir / "m2_8gb_optimized.yaml"
    profile_yaml.write_text(
        """
global:
  performance:
    max_concurrent_renders: 4
research:
  policy:
    min_citations: 3
""",
        encoding="utf-8",
    )

    # Mock the current working directory
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        from bin.utils.config import get_research_policy, load_all_configs

        # Load with profile
        bundle = load_all_configs(profile="m2_8gb_optimized")

        # Verify profile overlay was applied
        if hasattr(bundle, "global_"):
            global_data = bundle.global_
        else:
            global_data = bundle.get("global", {})

        # Profile should override base config
        if hasattr(global_data, "performance"):
            assert global_data.performance.max_concurrent_renders == 4
        else:
            assert global_data.get("performance", {}).get("max_concurrent_renders") == 4

        # Research policy should also be overridden
        pol = get_research_policy(bundle)
        assert pol.min_citations == 3

    finally:
        os.chdir(original_cwd)


def test_environment_variable_overlay(monkeypatch, tmp_path):
    """Test that environment variables override config."""
    # Create test config files
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()

    # Create base configs
    global_yaml = conf_dir / "global.yaml"
    global_yaml.write_text(
        "performance:\n  max_concurrent_renders: 1", encoding="utf-8"
    )

    pipeline_yaml = conf_dir / "pipeline.yaml"
    pipeline_yaml.write_text("steps:\n  test:\n    required: true", encoding="utf-8")

    research_yaml = conf_dir / "research.yaml"
    research_yaml.write_text(
        "policy:\n  mode: reuse\n  min_citations: 1", encoding="utf-8"
    )

    models_yaml = conf_dir / "models.yaml"
    models_yaml.write_text(
        """
ollama:
  base_url: http://127.0.0.1:11434
  timeout_sec: 60
""",
        encoding="utf-8",
    )

    # Mock the current working directory
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        from bin.utils.config import load_all_configs

        # Set environment variables
        with patch.dict(
            os.environ,
            {
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "OLLAMA_TIMEOUT_SEC": "120",
                "SHORT_RUN_SECS": "15",
            },
        ):
            bundle = load_all_configs()

            # Verify environment variables override config
            if hasattr(bundle, "models"):
                models_data = bundle.models
            else:
                models_data = bundle.get("models", {})

            if hasattr(models_data, "ollama"):
                assert models_data.ollama.base_url == "http://localhost:11434"
                assert models_data.ollama.timeout_sec == 120.0
            else:
                assert (
                    models_data.get("ollama", {}).get("base_url")
                    == "http://localhost:11434"
                )
                assert models_data.get("ollama", {}).get("timeout_sec") == 120.0

    finally:
        os.chdir(original_cwd)


def test_get_research_policy_helper():
    """Test the get_research_policy helper function."""
    from bin.utils.config import get_research_policy

    # Test with None bundle (should load automatically)
    policy = get_research_policy()
    assert hasattr(policy, "mode")
    assert hasattr(policy, "min_citations")
    assert hasattr(policy, "allow_providers")


if __name__ == "__main__":
    pytest.main([__file__])
