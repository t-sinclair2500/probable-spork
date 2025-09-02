#!/usr/bin/env python3
"""
Implementation & Consistency Auditor

Scans the repository for inconsistent CLI flags, config access patterns,
logging behaviors, and other implementation issues.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, List

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RPT_DIR = ROOT / "reports" / "audit"
RPT_DIR.mkdir(parents=True, exist_ok=True)

# Expected CLI flags and their properties
EXPECTED_FLAGS = {
    "--slug": {"dest": "slug", "help": "Slug identifier"},
    "--brief": {"dest": "brief", "help": "Brief file path"},
    "--mode": {"choices": ["reuse", "live"], "help": "Mode selection"},
    "--yt-only": {"action": "store_true", "help": "YouTube only mode"},
    "--from-step": {"dest": "from_step", "help": "Start from step"},
    "--seed": {"type": "int", "help": "Seed for deterministic runs"},
    "--enable-viral": {"action": "store_true", "help": "Enable viral lab"},
    "--no-viral": {
        "action": "store_false",
        "dest": "enable_viral",
        "help": "Disable viral lab",
    },
    "--enable-shorts": {"action": "store_true", "help": "Enable shorts generation"},
    "--no-shorts": {
        "action": "store_false",
        "dest": "enable_shorts",
        "help": "Disable shorts generation",
    },
    "--enable-seo": {"action": "store_true", "help": "Enable SEO packaging"},
    "--no-seo": {
        "action": "store_false",
        "dest": "enable_seo",
        "help": "Disable SEO packaging",
    },
}

# Severity levels
SEVERITY_LEVELS = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]


class ConsistencyAuditor:
    def __init__(self):
        self.issues = []
        self.python_files = []

    def scan_python_files(self):
        """Find all Python files in bin/ directory."""
        bin_dir = ROOT / "bin"
        for py_file in bin_dir.rglob("*.py"):
            if py_file.is_file() and not py_file.name.startswith("__"):
                self.python_files.append(py_file)

    def extract_argparse_flags(
        self, py_text: str, file_path: Path
    ) -> Dict[str, Dict[str, Any]]:
        """Extract argparse flags from Python text."""
        flags = {}

        # Find add_argument calls
        pattern = r'add_argument\s*\(\s*[\'"](--[a-z0-9\-]+)[\'"]'
        for match in re.finditer(pattern, py_text):
            flag_name = match.group(1)
            if flag_name not in flags:
                flags[flag_name] = {
                    "file": str(file_path),
                    "line": py_text[: match.start()].count("\n") + 1,
                }

        return flags

    def check_cli_flag_consistency(self):
        """Check CLI flag consistency across scripts."""
        all_flags = {}
        missing_flags = set(EXPECTED_FLAGS.keys())

        for py_file in self.python_files:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                flags = self.extract_argparse_flags(content, py_file)

                for flag_name, flag_info in flags.items():
                    if flag_name not in all_flags:
                        all_flags[flag_name] = []
                    all_flags[flag_name].append(flag_info)

                    if flag_name in missing_flags:
                        missing_flags.remove(flag_name)

            except Exception as e:
                self.add_issue(
                    "cli_flag_parse_error",
                    "MEDIUM",
                    f"Failed to parse CLI flags in {py_file}: {e}",
                    [{"file": str(py_file), "line": 1, "snippet": "parse error"}],
                )

        # Check for missing expected flags in step runners
        step_runners = [
            f
            for f in self.python_files
            if any(
                name in f.name
                for name in [
                    "research",
                    "llm_",
                    "storyboard",
                    "animatics",
                    "assemble",
                    "tts",
                    "viral",
                    "packaging",
                ]
            )
        ]

        for runner in step_runners:
            content = runner.read_text(encoding="utf-8", errors="ignore")
            if "add_argument" in content and "--slug" not in content:
                self.add_issue(
                    "missing_slug_flag",
                    "BLOCKER",
                    f"Step runner {runner.name} missing --slug flag",
                    [{"file": str(runner), "line": 1, "snippet": "missing --slug"}],
                )

        # Check for inconsistent flag definitions
        for flag_name, flag_info in all_flags.items():
            if len(flag_info) > 1:
                # Check for inconsistent help text or types
                help_texts = []
                for info in flag_info:
                    # Extract help text if present
                    file_content = Path(info["file"]).read_text(
                        encoding="utf-8", errors="ignore"
                    )
                    lines = file_content.split("\n")
                    if info["line"] < len(lines):
                        line = lines[info["line"] - 1]
                        help_match = re.search(r'help\s*=\s*[\'"]([^\'"]+)[\'"]', line)
                        if help_match:
                            help_texts.append(help_match.group(1))

                if len(set(help_texts)) > 1:
                    evidence = []
                    for i, info in enumerate(flag_info):
                        if i < len(help_texts):
                            evidence.append(
                                {
                                    "file": info["file"],
                                    "line": info["line"],
                                    "snippet": f"help='{help_texts[i]}'",
                                }
                            )
                        else:
                            evidence.append(
                                {
                                    "file": info["file"],
                                    "line": info["line"],
                                    "snippet": "help text not found",
                                }
                            )

                    self.add_issue(
                        "inconsistent_flag_help",
                        "MEDIUM",
                        f"Flag {flag_name} has inconsistent help text across files",
                        evidence,
                    )

    def check_config_access_patterns(self):
        """Check config access patterns for consistency."""
        for py_file in self.python_files:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")

                # Check for mixed dict access patterns
                dict_access = re.findall(r'(\w+)\[\s*[\'"]([^\'"]+)[\'"]\s*\]', content)
                dot_access = re.findall(r"(\w+)\.(\w+)", content)

                if dict_access and dot_access:
                    # Check if same config object is accessed both ways
                    dict_vars = set(item[0] for item in dict_access)
                    dot_vars = set(item[0] for item in dot_access)
                    mixed_vars = dict_vars & dot_vars

                    for var in mixed_vars:
                        if "config" in var.lower() or "cfg" in var.lower():
                            self.add_issue(
                                "mixed_config_access",
                                "HIGH",
                                f"Mixed config access patterns in {py_file.name}",
                                [
                                    {
                                        "file": str(py_file),
                                        "line": 1,
                                        "snippet": f"mixed access for {var}",
                                    }
                                ],
                            )

                # Check for load_config() calls without proper error handling
                if "load_config()" in content and "try:" not in content:
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if "load_config()" in line and not any(
                            keyword in line
                            for keyword in ["try:", "except:", "if __name__"]
                        ):
                            # Check if this is in a function context
                            context_lines = lines[max(0, i - 5) : i + 5]
                            if not any("def " in l for l in context_lines):
                                self.add_issue(
                                    "unprotected_load_config",
                                    "MEDIUM",
                                    f"load_config() call without error handling in {py_file.name}",
                                    [
                                        {
                                            "file": str(py_file),
                                            "line": i,
                                            "snippet": line.strip(),
                                        }
                                    ],
                                )

            except Exception as e:
                self.add_issue(
                    "config_access_parse_error",
                    "MEDIUM",
                    f"Failed to parse config access in {py_file}: {e}",
                    [{"file": str(py_file), "line": 1, "snippet": "parse error"}],
                )

    def check_slug_safety(self):
        """Check for unsafe slug parsing."""
        unsafe_patterns = [
            r'split\s*\(\s*[\'"]_[\'"]\s*\)\s*\[0\]',  # split('_')[0]
            r'\.replace\s*\(\s*[\'"]_[\'"]\s*,\s*[\'"]-[\'"]\s*\)',  # replace('_', '-')
            r'\.split\s*\(\s*[\'"]_[\'"]\s*\)',  # split('_')
        ]

        for py_file in self.python_files:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    if "slug" in line.lower():
                        for pattern in unsafe_patterns:
                            if re.search(pattern, line):
                                self.add_issue(
                                    "unsafe_slug_parsing",
                                    "BLOCKER",
                                    f"Unsafe slug parsing in {py_file.name}",
                                    [
                                        {
                                            "file": str(py_file),
                                            "line": i,
                                            "snippet": line.strip(),
                                        }
                                    ],
                                )

                # Check if safe_slug_from_script is imported but not used
                if "safe_slug_from_script" in content:
                    if not re.search(r"safe_slug_from_script\s*\(", content):
                        self.add_issue(
                            "unused_safe_slug_import",
                            "LOW",
                            f"safe_slug_from_script imported but not used in {py_file.name}",
                            [
                                {
                                    "file": str(py_file),
                                    "line": 1,
                                    "snippet": "unused import",
                                }
                            ],
                        )

            except Exception as e:
                self.add_issue(
                    "slug_safety_parse_error",
                    "MEDIUM",
                    f"Failed to parse slug safety in {py_file}: {e}",
                    [{"file": str(py_file), "line": 1, "snippet": "parse error"}],
                )

    def check_logging_streaming(self):
        """Check for inappropriate subprocess usage in orchestrator."""
        orchestrator_files = [
            f
            for f in self.python_files
            if any(
                name in f.name
                for name in ["run_pipeline", "orchestrator", "acceptance"]
            )
        ]

        for py_file in orchestrator_files:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    if "subprocess.run" in line and "capture_output=True" in line:
                        # Check if this is in a streaming context
                        context_lines = lines[max(0, i - 10) : i + 10]
                        if not any("run_streamed" in l for l in context_lines):
                            self.add_issue(
                                "capture_output_in_orchestrator",
                                "HIGH",
                                f"subprocess.run with capture_output in orchestrator {py_file.name}",
                                [
                                    {
                                        "file": str(py_file),
                                        "line": i,
                                        "snippet": line.strip(),
                                    }
                                ],
                            )

                # Check for missing run_streamed usage
                if "subprocess.run" in content and "run_streamed" not in content:
                    self.add_issue(
                        "missing_run_streamed",
                        "MEDIUM",
                        f"Orchestrator {py_file.name} uses subprocess.run instead of run_streamed",
                        [
                            {
                                "file": str(py_file),
                                "line": 1,
                                "snippet": "missing run_streamed",
                            }
                        ],
                    )

            except Exception as e:
                self.add_issue(
                    "logging_parse_error",
                    "MEDIUM",
                    f"Failed to parse logging in {py_file}: {e}",
                    [{"file": str(py_file), "line": 1, "snippet": "parse error"}],
                )

    def check_storyboard_animatics_api(self):
        """Check storyboard/animatics API alignment."""
        storyboard_files = [
            f
            for f in self.python_files
            if any(name in f.name for name in ["storyboard", "animatics", "design"])
        ]

        for py_file in storyboard_files:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")

                # Check for palette adapter usage
                if "palette" in content.lower() and "ensure_palette" not in content:
                    self.add_issue(
                        "missing_palette_adapter",
                        "MEDIUM",
                        f"Missing ensure_palette usage in {py_file.name}",
                        [
                            {
                                "file": str(py_file),
                                "line": 1,
                                "snippet": "missing palette adapter",
                            }
                        ],
                    )

                # Check for flattening utility usage
                if "raster" in content.lower() and "flatten" not in content:
                    self.add_issue(
                        "missing_flatten_utility",
                        "MEDIUM",
                        f"Missing flattening utility in {py_file.name}",
                        [
                            {
                                "file": str(py_file),
                                "line": 1,
                                "snippet": "missing flatten utility",
                            }
                        ],
                    )

            except Exception as e:
                self.add_issue(
                    "storyboard_api_parse_error",
                    "MEDIUM",
                    f"Failed to parse storyboard API in {py_file}: {e}",
                    [{"file": str(py_file), "line": 1, "snippet": "parse error"}],
                )

    def check_platform_branching(self):
        """Check for platform-specific code branching."""
        platform_files = [
            f
            for f in self.python_files
            if any(name in f.name for name in ["assemble", "thumbnail", "render"])
        ]

        for py_file in platform_files:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")

                # Check for hardcoded paths
                hardcoded_paths = re.findall(
                    r'[\'"](/[^\'"]+\.(?:mp4|mov|png|jpg|svg))[\'"]', content
                )
                if hardcoded_paths:
                    self.add_issue(
                        "hardcoded_paths",
                        "MEDIUM",
                        f"Hardcoded paths in {py_file.name}",
                        [
                            {
                                "file": str(py_file),
                                "line": 1,
                                "snippet": f"hardcoded: {hardcoded_paths[0]}",
                            }
                        ],
                    )

                # Check for platform-specific codec selection
                if (
                    "videotoolbox" in content.lower()
                    and "platform" not in content.lower()
                ):
                    self.add_issue(
                        "missing_platform_check",
                        "MEDIUM",
                        f"Missing platform check for VideoToolbox in {py_file.name}",
                        [
                            {
                                "file": str(py_file),
                                "line": 1,
                                "snippet": "missing platform check",
                            }
                        ],
                    )

            except Exception as e:
                self.add_issue(
                    "platform_parse_error",
                    "MEDIUM",
                    f"Failed to parse platform branching in {py_file}: {e}",
                    [{"file": str(py_file), "line": 1, "snippet": "parse error"}],
                )

    def check_quality_gates(self):
        """Check for quality gates presence and configuration."""
        qa_dir = ROOT / "bin" / "qa"
        if not qa_dir.exists():
            self.add_issue(
                "missing_qa_directory",
                "BLOCKER",
                "Missing QA directory",
                [{"file": "bin/qa", "line": 1, "snippet": "directory not found"}],
            )
            return

        qa_files = list(qa_dir.glob("*.py"))
        if not qa_files:
            self.add_issue(
                "missing_qa_files",
                "BLOCKER",
                "No QA files found",
                [{"file": "bin/qa", "line": 1, "snippet": "no .py files"}],
            )
            return

        # Check for run_gates.py
        run_gates = qa_dir / "run_gates.py"
        if not run_gates.exists():
            self.add_issue(
                "missing_run_gates",
                "BLOCKER",
                "Missing run_gates.py in QA directory",
                [{"file": "bin/qa", "line": 1, "snippet": "run_gates.py not found"}],
            )
        else:
            # Check for configured thresholds
            try:
                content = run_gates.read_text(encoding="utf-8", errors="ignore")
                required_gates = [
                    "Script",
                    "VO",
                    "Visuals",
                    "Master",
                    "Research",
                    "Monetization",
                ]

                for gate in required_gates:
                    if gate.lower() not in content.lower():
                        self.add_issue(
                            "missing_quality_gate",
                            "HIGH",
                            f"Missing quality gate: {gate}",
                            [
                                {
                                    "file": str(run_gates),
                                    "line": 1,
                                    "snippet": f"missing {gate} gate",
                                }
                            ],
                        )

            except Exception as e:
                self.add_issue(
                    "qa_parse_error",
                    "MEDIUM",
                    f"Failed to parse QA gates: {e}",
                    [{"file": str(run_gates), "line": 1, "snippet": "parse error"}],
                )

    def add_issue(
        self,
        issue_id: str,
        severity: str,
        description: str,
        evidence: List[Dict[str, Any]],
    ):
        """Add an issue to the audit results."""
        if severity not in SEVERITY_LEVELS:
            severity = "MEDIUM"  # Default to medium if invalid severity

        self.issues.append(
            {
                "id": issue_id,
                "severity": severity,
                "status": "FAIL",
                "description": description,
                "evidence": evidence,
                "suggest_fix": self.get_suggested_fix(issue_id),
            }
        )

    def get_suggested_fix(self, issue_id: str) -> str:
        """Get suggested fix for an issue."""
        fixes = {
            "missing_slug_flag": "Add --slug argument to argparse parser",
            "unsafe_slug_parsing": "Use safe_slug_from_script() utility instead of manual parsing",
            "capture_output_in_orchestrator": "Use run_streamed() instead of subprocess.run with capture_output",
            "mixed_config_access": "Use consistent Pydantic-style access (.attribute) throughout",
            "hardcoded_paths": "Use relative paths or configuration-based paths",
            "missing_platform_check": "Add platform.system() check before using platform-specific features",
            "missing_quality_gate": "Add quality gate to run_gates.py with appropriate thresholds",
        }
        return fixes.get(issue_id, "Review and fix according to coding standards")

    def run_audit(self) -> Dict[str, Any]:
        """Run the complete consistency audit."""
        print("🔍 Scanning Python files...")
        self.scan_python_files()

        print("🔍 Checking CLI flag consistency...")
        self.check_cli_flag_consistency()

        print("🔍 Checking config access patterns...")
        self.check_config_access_patterns()

        print("🔍 Checking slug safety...")
        self.check_slug_safety()

        print("🔍 Checking logging and streaming...")
        self.check_logging_streaming()

        print("🔍 Checking storyboard/animatics API...")
        self.check_storyboard_animatics_api()

        print("🔍 Checking platform branching...")
        self.check_platform_branching()

        print("🔍 Checking quality gates...")
        self.check_quality_gates()

        # Calculate summary
        total_issues = len(self.issues)
        blocker_issues = len([i for i in self.issues if i["severity"] == "BLOCKER"])
        high_issues = len([i for i in self.issues if i["severity"] == "HIGH"])
        medium_issues = len([i for i in self.issues if i["severity"] == "MEDIUM"])
        low_issues = len([i for i in self.issues if i["severity"] == "LOW"])
        info_issues = len([i for i in self.issues if i["severity"] == "INFO"])

        overall_status = "FAIL" if (blocker_issues > 0 or high_issues > 0) else "PASS"

        return {
            "audit_info": {
                "timestamp": str(Path(__file__).stat().st_mtime),
                "total_issues": total_issues,
                "blocker": blocker_issues,
                "high": high_issues,
                "medium": medium_issues,
                "low": low_issues,
                "info": info_issues,
                "overall_status": overall_status,
                "files_scanned": len(self.python_files),
            },
            "issues": self.issues,
        }

    def write_reports(self, audit_data: Dict[str, Any]):
        """Write JSON and Markdown reports."""
        # JSON report
        json_path = RPT_DIR / "consistency_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(audit_data, f, indent=2)

        # Markdown report
        md_path = RPT_DIR / "consistency_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Implementation & Consistency Audit Report\n\n")

            info = audit_data["audit_info"]
            f.write(f"**Audit Date:** {info['timestamp']}\n")
            f.write(f"**Overall Status:** {info['overall_status']}\n")
            f.write(f"**Files Scanned:** {info['files_scanned']}\n\n")

            f.write(
                f"**Summary:** {info['blocker']} BLOCKER, {info['high']} HIGH, {info['medium']} MEDIUM, {info['low']} LOW, {info['info']} INFO\n\n"
            )

            # Group issues by severity
            issues_by_severity = {}
            for issue in audit_data["issues"]:
                severity = issue["severity"]
                if severity not in issues_by_severity:
                    issues_by_severity[severity] = []
                issues_by_severity[severity].append(issue)

            # Write issues by severity (highest first)
            for severity in ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]:
                if severity in issues_by_severity:
                    f.write(
                        f"## {severity} Issues ({len(issues_by_severity[severity])})\n\n"
                    )

                    for issue in issues_by_severity[severity]:
                        f.write(f"### {issue['id']}\n\n")
                        f.write(f"**Description:** {issue['description']}\n\n")
                        f.write(f"**Suggested Fix:** {issue['suggest_fix']}\n\n")

                        f.write("**Evidence:**\n")
                        for evidence in issue["evidence"]:
                            f.write(
                                f"- `{evidence['file']}:{evidence['line']}`: {evidence['snippet']}\n"
                            )
                        f.write("\n")

            if not audit_data["issues"]:
                f.write("🎉 No consistency issues found! All checks passed.\n\n")


def main():
    print("🔍 Starting Implementation & Consistency Audit...")

    auditor = ConsistencyAuditor()
    audit_data = auditor.run_audit()

    auditor.write_reports(audit_data)

    info = audit_data["audit_info"]
    print(
        f"📊 Audit Complete: {info['blocker']} BLOCKER, {info['high']} HIGH, {info['medium']} MEDIUM, {info['low']} LOW, {info['info']} INFO"
    )
    print("📄 Reports saved to: reports/audit/consistency_report.json")
    print("📄 Reports saved to: reports/audit/consistency_report.md")

    if info["overall_status"] == "FAIL":
        print("❌ Audit FAILED - check report for critical issues")
        sys.exit(1)
    else:
        print("✅ Audit PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
