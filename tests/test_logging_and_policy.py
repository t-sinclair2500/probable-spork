# tests/test_logging_and_policy.py
import json
import os
from pathlib import Path
from types import SimpleNamespace
import shutil

from bin.utils.logs import audit_event
from bin.utils.subproc import run_streamed

def test_audit_event_writes_jsonl(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    logs = tmp_path / "logs" / "subprocess"
    jobs.mkdir(parents=True)
    logs.mkdir(parents=True)

    # monkeypatch CWD so jobs/state.jsonl lands in tmp
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        audit_event("unit_test", "OK", foo="bar", n=1)
        p = Path("jobs/state.jsonl")
        assert p.exists()
        line = p.read_text(encoding="utf-8").strip()
        rec = json.loads(line)
        assert rec["step"] == "unit_test" and rec["status"] == "OK" and rec["foo"] == "bar"
    finally:
        os.chdir(cwd)

def test_run_streamed_logs_and_tail(tmp_path):
    log_path = tmp_path / "logs" / "subprocess" / "echo.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rc = run_streamed(["python", "-c", "print('hello');"], log_path=str(log_path), check=True)
    assert rc == 0 and "hello" in log_path.read_text()

def test_policy_required_vs_optional(tmp_path, monkeypatch):
    # Simulate run_step policy decisions by importing run_pipeline.run_step
    # We need pipeline config to be discovered; point CWD to a temp conf with a failing step
    conf = tmp_path / "conf"
    conf.mkdir()
    (conf / "pipeline.yaml").write_text(
        "steps:\n  must_pass:\n    required: true\n  can_warn:\n    required: false\n    on_fail: warn\n  can_skip:\n    required: false\n    on_fail: skip\n",
        encoding="utf-8",
    )
    # Place jobs/logs dirs for audit
    (tmp_path / "jobs").mkdir()
    (tmp_path / "logs" / "subprocess").mkdir(parents=True)
    # Switch CWD
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        import importlib
        rp = importlib.import_module("bin.run_pipeline")
        # A command that fails
        bad = ["python", "-c", "import sys; print('oops'); sys.exit(2)"]
        # required: should raise
        raised = False
        try:
            rp.pipeline_cfg = rp.load_pipeline_config("conf/pipeline.yaml")  # ensure it picks our temp config
            rp.run_step("must_pass", bad, notes="testing required", pipeline_cfg=rp.pipeline_cfg)
        except Exception:
            raised = True
        assert raised is True

        # warn: should return PARTIAL (no raise)
        st = rp.run_step("can_warn", bad, notes="testing warn", pipeline_cfg=rp.pipeline_cfg)
        assert st == "PARTIAL"

        # skip: should return SKIP (no raise)
        st2 = rp.run_step("can_skip", bad, notes="testing skip", pipeline_cfg=rp.pipeline_cfg)
        assert st2 == "SKIP"

        # verify JSONL entries exist
        j = Path("jobs/state.jsonl").read_text(encoding="utf-8")
        assert "must_pass" in j and "can_warn" in j and "can_skip" in j
    finally:
        os.chdir(cwd)
