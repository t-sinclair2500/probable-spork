from __future__ import annotations

import json
import tempfile
from unittest.mock import patch

from pathlib import Path

from bin.audit.viral_wiring_auditor import (
    check_artifacts,
    check_cli_flags,
    check_configs,
    check_encoder_overlay,
    check_llm_hygiene,
    check_pipeline_steps,
    check_tools,
    run_audit,
    write_reports,
)


def test_check_pipeline_steps():
    """Test pipeline steps check."""
    status, msg = check_pipeline_steps()
    assert status in ["PASS", "FAIL", "WARN"]
    assert isinstance(msg, str)


def test_check_cli_flags():
    """Test CLI flags check."""
    status, msg = check_cli_flags()
    assert status in ["PASS", "FAIL", "WARN"]
    assert isinstance(msg, str)


def test_check_configs():
    """Test config files check."""
    results = check_configs()
    assert isinstance(results, list)
    for file_name, status, msg in results:
        assert status in ["PASS", "FAIL", "WARN"]
        assert isinstance(msg, str)


def test_check_llm_hygiene():
    """Test LLM hygiene check."""
    status, msg = check_llm_hygiene()
    assert status in ["PASS", "FAIL", "WARN"]
    assert isinstance(msg, str)


def test_check_encoder_overlay():
    """Test encoder and overlay check."""
    results = check_encoder_overlay()
    assert isinstance(results, list)
    for check_name, status, msg in results:
        assert status in ["PASS", "FAIL", "WARN"]
        assert isinstance(msg, str)


@patch("subprocess.run")
def test_check_tools(mock_run):
    """Test tools check with mocked subprocess."""
    # Mock successful ffmpeg and ffprobe
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "videotoolbox"

    status, msg = check_tools()
    assert status in ["PASS", "FAIL", "WARN"]
    assert isinstance(msg, str)


def test_check_artifacts_no_slug():
    """Test artifacts check without slug."""
    results = check_artifacts()
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0][0] == "artifacts"
    assert results[0][1] == "SKIP"


def test_run_audit():
    """Test complete audit run."""
    audit_data = run_audit()
    assert isinstance(audit_data, dict)
    assert "audit_info" in audit_data
    assert "results" in audit_data

    info = audit_data["audit_info"]
    assert "total_checks" in info
    assert "passed" in info
    assert "failed" in info
    assert "overall_status" in info


def test_write_reports():
    """Test report writing."""
    audit_data = {
        "audit_info": {
            "timestamp": "test",
            "total_checks": 1,
            "passed": 1,
            "failed": 0,
            "warned": 0,
            "skipped": 0,
            "overall_status": "PASS",
        },
        "results": [
            {
                "check_id": "test_check",
                "status": "PASS",
                "details": "Test details",
                "suggest_fix": None,
            }
        ],
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Mock the RPT_DIR to use temp directory
        with patch("bin.audit.viral_wiring_auditor.RPT_DIR", temp_path):
            write_reports(audit_data)

            # Check that files were created
            json_file = temp_path / "viral_wiring_report.json"
            md_file = temp_path / "viral_wiring_report.md"

            assert json_file.exists()
            assert md_file.exists()

            # Check JSON content
            with open(json_file, "r") as f:
                json_data = json.load(f)
                assert json_data["audit_info"]["overall_status"] == "PASS"

            # Check Markdown content
            with open(md_file, "r") as f:
                md_content = f.read()
                assert "Viral Wiring Audit Report" in md_content
                assert "test_check" in md_content



