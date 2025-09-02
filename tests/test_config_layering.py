from bin.utils.config import load_all_configs


def test_precedence_and_validation(monkeypatch, tmp_path):
    (tmp_path / "conf").mkdir()
    (tmp_path / "conf/global.yaml").write_text("seed: 42\n", encoding="utf-8")
    (tmp_path / "conf/pipeline.yaml").write_text(
        "steps:\n  assemble:\n    required: true\n", encoding="utf-8"
    )
    (tmp_path / "conf/research.yaml").write_text(
        "policy:\n  mode: reuse\n", encoding="utf-8"
    )
    (tmp_path / "conf/models.yaml").write_text(
        "ollama:\n  timeout_sec: 30\n", encoding="utf-8"
    )
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        cfg = load_all_configs(profile=None, cli_overrides={"global": {"seed": 7}})
        # Bundle exposes attributes; fallback dict exposes keys
        if hasattr(cfg, "global_"):
            assert cfg.global_.seed == 7
            assert cfg.models.ollama.timeout_sec == 30
            assert "assemble" in cfg.pipeline.steps
        else:
            assert cfg["global"]["seed"] == 7
            assert cfg["models"]["ollama"]["timeout_sec"] == 30
            assert "assemble" in cfg["pipeline"]["steps"]
    finally:
        os.chdir(cwd)
