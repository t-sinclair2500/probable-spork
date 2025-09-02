from __future__ import annotations

import json
import tempfile
from unittest.mock import patch

from pathlib import Path

from bin.audit.consistency_auditor import ConsistencyAuditor


def test_consistency_auditor_initialization():
    """Test auditor initialization."""
    auditor = ConsistencyAuditor()
    assert auditor.issues == []
    assert auditor.python_files == []


def test_scan_python_files():
    """Test Python file scanning."""
    auditor = ConsistencyAuditor()
    auditor.scan_python_files()
    assert len(auditor.python_files) > 0
    assert all(f.suffix == ".py" for f in auditor.python_files)
    assert all("__" not in f.name for f in auditor.python_files)


def test_extract_argparse_flags():
    """Test argparse flag extraction."""
    auditor = ConsistencyAuditor()

    test_content = """
    parser.add_argument("--slug", required=True, help="Slug identifier")
    parser.add_argument("--mode", choices=["reuse", "live"], help="Mode selection")
    parser.add_argument("--yt-only", action="store_true", help="YouTube only")
    """

    flags = auditor.extract_argparse_flags(test_content, Path("test.py"))
    assert "--slug" in flags
    assert "--mode" in flags
    assert "--yt-only" in flags
    assert len(flags) == 3


def test_check_cli_flag_consistency():
    """Test CLI flag consistency check."""
    auditor = ConsistencyAuditor()

    # Mock Python files with argparse
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        file1 = temp_path / "test1.py"
        file1.write_text(
            """
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--slug", required=True, help="Slug identifier")
        parser.add_argument("--mode", choices=["reuse", "live"], help="Mode selection")
        """
        )

        file2 = temp_path / "test2.py"
        file2.write_text(
            """
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--slug", help="Different help text")
        """
        )

        auditor.python_files = [file1, file2]
        auditor.check_cli_flag_consistency()

        # Should find inconsistent help text for --slug
        inconsistent_issues = [
            i for i in auditor.issues if i["id"] == "inconsistent_flag_help"
        ]
        assert len(inconsistent_issues) > 0


def test_check_config_access_patterns():
    """Test config access pattern check."""
    auditor = ConsistencyAuditor()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test file with mixed config access
        test_file = temp_path / "test_config.py"
        test_file.write_text(
            """
        config = load_config()
        value1 = config["some_key"]
        value2 = config.other_key
        """
        )

        auditor.python_files = [test_file]
        auditor.check_config_access_patterns()

        # Should find mixed config access
        mixed_access_issues = [
            i for i in auditor.issues if i["id"] == "mixed_config_access"
        ]
        assert len(mixed_access_issues) > 0


def test_check_slug_safety():
    """Test slug safety check."""
    auditor = ConsistencyAuditor()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test file with unsafe slug parsing
        test_file = temp_path / "test_slug.py"
        test_file.write_text(
            """
        slug = filename.split('_')[0]
        slug = slug.replace('_', '-')
        """
        )

        auditor.python_files = [test_file]
        auditor.check_slug_safety()

        # Should find unsafe slug parsing
        unsafe_issues = [i for i in auditor.issues if i["id"] == "unsafe_slug_parsing"]
        assert len(unsafe_issues) > 0


def test_check_logging_streaming():
    """Test logging and streaming check."""
    auditor = ConsistencyAuditor()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test orchestrator file with capture_output
        test_file = temp_path / "run_pipeline.py"
        test_file.write_text(
            """
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True)
        """
        )

        auditor.python_files = [test_file]
        auditor.check_logging_streaming()

        # Should find capture_output in orchestrator
        capture_issues = [
            i for i in auditor.issues if i["id"] == "capture_output_in_orchestrator"
        ]
        assert len(capture_issues) > 0


def test_check_quality_gates():
    """Test quality gates check."""
    auditor = ConsistencyAuditor()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Test case 1: Missing QA directory
        with patch("bin.audit.consistency_auditor.ROOT", temp_path):
            auditor.check_quality_gates()
            missing_dir_issues = [
                i for i in auditor.issues if i["id"] == "missing_qa_directory"
            ]
            assert len(missing_dir_issues) > 0

        # Reset issues for next test
        auditor.issues = []

        # Test case 2: Missing quality gates
        qa_dir = temp_path / "bin" / "qa"
        qa_dir.mkdir(parents=True)
        run_gates = qa_dir / "run_gates.py"
        run_gates.write_text(
            """
        # Quality gates
        from qa import measure_script, measure_audio
        # Missing: measure_visuals, measure_video, measure_research, measure_monetization
        
        def evaluate_all(slug: str, qa_cfg: dict) -> dict:
            # Only script and audio gates
            s_metrics = measure_script.evaluate(slug, th.get("script", {}), duration_s)
            a_metrics = measure_audio.ebur128_metrics(audio_path)
            # Missing: Visuals, Video, Research, Monetization gates
        """
        )

        with patch("bin.audit.consistency_auditor.ROOT", temp_path):
            auditor.check_quality_gates()

            # Should find missing quality gates (VO, Visuals, Master, Research, Monetization)
            missing_gate_issues = [
                i for i in auditor.issues if i["id"] == "missing_quality_gate"
            ]
            assert (
                len(missing_gate_issues) >= 2
            )  # At least 2 missing gates (VO and Master)


def test_add_issue():
    """Test issue addition."""
    auditor = ConsistencyAuditor()

    auditor.add_issue(
        "test_issue",
        "HIGH",
        "Test description",
        [{"file": "test.py", "line": 1, "snippet": "test"}],
    )

    assert len(auditor.issues) == 1
    issue = auditor.issues[0]
    assert issue["id"] == "test_issue"
    assert issue["severity"] == "HIGH"
    assert issue["description"] == "Test description"


def test_get_suggested_fix():
    """Test suggested fix generation."""
    auditor = ConsistencyAuditor()

    fix = auditor.get_suggested_fix("missing_slug_flag")
    assert "Add --slug argument" in fix

    fix = auditor.get_suggested_fix("unsafe_slug_parsing")
    assert "safe_slug_from_script" in fix

    fix = auditor.get_suggested_fix("unknown_issue")
    assert "Review and fix" in fix


def test_run_audit():
    """Test complete audit run."""
    auditor = ConsistencyAuditor()

    # Mock file scanning to avoid scanning entire repo
    with patch.object(auditor, "scan_python_files"):
        auditor.python_files = []
        audit_data = auditor.run_audit()

        assert "audit_info" in audit_data
        assert "issues" in audit_data

        info = audit_data["audit_info"]
        assert "total_issues" in info
        assert "overall_status" in info
        assert "files_scanned" in info


def test_write_reports():
    """Test report writing."""
    auditor = ConsistencyAuditor()

    audit_data = {
        "audit_info": {
            "timestamp": "test",
            "total_issues": 1,
            "blocker": 0,
            "high": 1,
            "medium": 0,
            "low": 0,
            "info": 0,
            "overall_status": "FAIL",
            "files_scanned": 10,
        },
        "issues": [
            {
                "id": "test_issue",
                "severity": "HIGH",
                "status": "FAIL",
                "description": "Test issue",
                "evidence": [{"file": "test.py", "line": 1, "snippet": "test"}],
                "suggest_fix": "Test fix",
            }
        ],
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Mock the RPT_DIR to use temp directory
        with patch("bin.audit.consistency_auditor.RPT_DIR", temp_path):
            auditor.write_reports(audit_data)

            # Check that files were created
            json_file = temp_path / "consistency_report.json"
            md_file = temp_path / "consistency_report.md"

            assert json_file.exists()
            assert md_file.exists()

            # Check JSON content
            with open(json_file, "r") as f:
                json_data = json.load(f)
                assert json_data["audit_info"]["overall_status"] == "FAIL"

            # Check Markdown content
            with open(md_file, "r") as f:
                md_content = f.read()
                assert "Implementation & Consistency Audit Report" in md_content
                assert "test_issue" in md_content
