#!/usr/bin/env python3
"""
Code Quality Suite — Run, autofix, re-run, and prioritize issues

Detects available tools, applies safe autofixes, re-runs analyses, and writes
a prioritized report to the repo root. Gracefully skips unavailable tools.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from typing import Dict, List, Tuple

from pathlib import Path

# Setup paths
ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports" / "code_quality"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Tool definitions: (name, command, is_autofix, description)
TOOLS = [
    # Formatting & Imports (autofix)
    ("isort", ["isort", "."], True, "Import sorting"),
    ("ruff_fix", ["ruff", "check", ".", "--fix"], True, "Ruff linting with autofix"),
    (
        "autoflake",
        ["autoflake", "--in-place", "--remove-all-unused-imports", "-r", "."],
        True,
        "Remove unused imports",
    ),
    ("black", ["black", "."], True, "Code formatting"),
    (
        "pyupgrade",
        ["pyupgrade", "--py311-plus", "-r", "."],
        True,
        "Python version upgrades",
    ),
    # Static & Security (analysis only)
    ("ruff", ["ruff", "check", "."], False, "Ruff linting"),
    ("vulture", ["vulture", "bin", "."], False, "Dead code detection"),
    ("bandit", ["bandit", "-q", "-r", "bin"], False, "Security analysis"),
    # Typing & Tests
    ("mypy", ["mypy", "bin"], False, "Type checking"),
    ("pytest", ["pytest", "-q"], False, "Test execution"),
]


def check_tool_available(tool_name: str, cmd: List[str]) -> bool:
    """Check if a tool is available in PATH."""
    if tool_name == "mypy":
        # Special case: mypy needs mypy.ini to be useful
        return shutil.which(cmd[0]) is not None and (ROOT / "mypy.ini").exists()
    elif tool_name == "pytest":
        # Special case: pytest needs tests/ directory
        return shutil.which(cmd[0]) is not None and (ROOT / "tests").exists()
    else:
        return shutil.which(cmd[0]) is not None


def run_tool(name: str, cmd: List[str], logname: str) -> Tuple[int, str]:
    """Run a tool and capture its output."""
    if not check_tool_available(name, cmd):
        log_content = f"{name}: SKIP - Tool not available or prerequisites not met"
        (REPORTS_DIR / f"{logname}.log").write_text(log_content, encoding="utf-8")
        return 0, log_content

    try:
        # Run the tool
        result = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=300,  # 5 minute timeout
        )

        # Combine stdout and stderr
        output = result.stdout + result.stderr

        # Write log file
        log_content = f"Command: {' '.join(cmd)}\nReturn code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        (REPORTS_DIR / f"{logname}.log").write_text(log_content, encoding="utf-8")

        return result.returncode, output

    except subprocess.TimeoutExpired:
        log_content = f"{name}: TIMEOUT - Tool exceeded 5 minute timeout"
        (REPORTS_DIR / f"{logname}.log").write_text(log_content, encoding="utf-8")
        return 1, log_content
    except Exception as e:
        log_content = f"{name}: ERROR - {str(e)}"
        (REPORTS_DIR / f"{logname}.log").write_text(log_content, encoding="utf-8")
        return 1, log_content


def analyze_results(
    results: Dict[str, Tuple[int, str]],
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Analyze tool results and categorize issues by severity."""
    blockers = []
    high = []
    medium = []
    low = []

    # Test failures are always blockers
    if "pytest" in results and results["pytest"][0] != 0:
        blockers.append("pytest failed - tests are not passing")

    # Syntax errors are blockers
    if "ruff" in results:
        rc, output = results["ruff"]
        if rc != 0 and any(
            error in output.lower()
            for error in ["syntax error", "invalid syntax", "indentation error"]
        ):
            blockers.append("syntax errors detected by ruff")

    # Import errors are blockers
    if "ruff" in results:
        rc, output = results["ruff"]
        if rc != 0 and "import" in output.lower() and "error" in output.lower():
            blockers.append("import errors detected by ruff")

    # Security issues are high priority
    if "bandit" in results:
        rc, output = results["bandit"]
        if rc != 0:
            # Count severity levels
            high_count = output.lower().count("severity: high")
            medium_count = output.lower().count("severity: medium")
            if high_count > 0:
                high.append(f"bandit: {high_count} HIGH severity security issues")
            if medium_count > 0:
                high.append(f"bandit: {medium_count} MEDIUM severity security issues")

    # Type errors are high priority
    if "mypy" in results:
        rc, output = results["mypy"]
        if rc != 0:
            error_count = output.count("error:")
            if error_count > 0:
                high.append(f"mypy: {error_count} type errors")

    # Ruff errors (not autofixed) are high priority
    if "ruff" in results:
        rc, output = results["ruff"]
        if rc != 0:
            # Count different error types
            e_errors = output.count("E")  # Error codes
            f_errors = output.count("F")  # Fatal codes
            if e_errors > 0 or f_errors > 0:
                high.append(f"ruff: {e_errors + f_errors} errors (E/F codes)")

    # Ruff warnings are medium priority
    if "ruff" in results:
        rc, output = results["ruff"]
        if rc != 0:
            w_errors = output.count("W")  # Warning codes
            if w_errors > 0:
                medium.append(f"ruff: {w_errors} warnings (W codes)")

    # Vulture findings are medium priority (if they look real)
    if "vulture" in results:
        rc, output = results["vulture"]
        if rc != 0 and "unused" in output.lower():
            # Count potential dead code findings
            lines = output.split("\n")
            dead_code_count = len(
                [line for line in lines if "unused" in line.lower() and ":" in line]
            )
            if dead_code_count > 0:
                medium.append(
                    f"vulture: {dead_code_count} potential dead code findings"
                )

    # Style issues are low priority
    if "ruff" in results:
        rc, output = results["ruff"]
        if rc != 0:
            # Count style issues
            style_errors = output.count("C")  # Convention codes
            if style_errors > 0:
                low.append(f"ruff: {style_errors} style issues (C codes)")

    return blockers, high, medium, low


def generate_report(
    blockers: List[str],
    high: List[str],
    medium: List[str],
    low: List[str],
    autofix_applied: bool,
    results: Dict[str, Tuple[int, str]],
) -> str:
    """Generate the markdown report."""
    lines = [
        "# Code Quality Report",
        "",
        f"**Generated:** {Path(__file__).stat().st_mtime}",
        f"**Autofixes Applied:** {'Yes' if autofix_applied else 'No'}",
        "",
        "## Summary",
        f"- **Blockers:** {len(blockers)} (must fix)",
        f"- **High:** {len(high)} (should fix)",
        f"- **Medium:** {len(medium)} (consider fixing)",
        f"- **Low:** {len(low)} (nice to have)",
        "",
        "## Issues by Priority",
    ]

    if blockers:
        lines.extend(
            [
                "### 🔴 Blockers (Must Fix)",
            ]
            + [f"- {issue}" for issue in blockers]
            + [""]
        )

    if high:
        lines.extend(
            [
                "### 🟠 High Priority (Should Fix)",
            ]
            + [f"- {issue}" for issue in high]
            + [""]
        )

    if medium:
        lines.extend(
            [
                "### 🟡 Medium Priority (Consider Fixing)",
            ]
            + [f"- {issue}" for issue in medium]
            + [""]
        )

    if low:
        lines.extend(
            [
                "### 🟢 Low Priority (Nice to Have)",
            ]
            + [f"- {issue}" for issue in low]
            + [""]
        )

    if not any([blockers, high, medium, low]):
        lines.extend(
            ["### ✅ All Good!", "No issues found. Code quality is excellent.", ""]
        )

    # Tool status summary
    lines.extend(
        [
            "## Tool Status",
            "| Tool | Status | Description |",
            "|------|--------|-------------|",
        ]
    )

    for name, cmd, is_autofix, description in TOOLS:
        if is_autofix:
            # For autofix tools, check if they were run during autofix phase
            if autofix_applied:
                # Check if there's a log file for this tool
                log_file = REPORTS_DIR / f"{name}.log"
                if log_file.exists():
                    log_content = log_file.read_text(encoding="utf-8")
                    if "SKIP" in log_content:
                        status = "⏭️ SKIP"
                    elif "ERROR" in log_content or "TIMEOUT" in log_content:
                        status = "❌ FAIL"
                    else:
                        status = "✅ PASS"
                else:
                    status = "⏭️ SKIP"
            else:
                status = "⏭️ SKIP (not run)"
        else:
            # For analysis tools
            if name in results:
                rc, output = results[name]
                if rc == 0:
                    status = "✅ PASS"
                else:
                    status = "❌ FAIL"
            else:
                status = "⏭️ SKIP"

        lines.append(f"| {name} | {status} | {description} |")

    lines.extend(
        [
            "",
            "## Next Steps",
            "### Quick Fixes",
            "```bash",
            "# Apply all autofixes",
            "python bin/quality/run_code_quality.py --apply-fixes",
            "",
            "# Run tests",
            "pytest -q",
            "",
            "# Fix remaining lint issues",
            "ruff check . --fix",
            "",
            "# Check security",
            "bandit -q -r bin",
            "",
            "# Check types",
            "mypy bin",
            "```",
            "",
            "### Manual Steps",
        ]
    )

    if blockers:
        lines.append(
            "- **Fix blockers first** - these prevent the codebase from working properly"
        )
    if high:
        lines.append(
            "- **Address high priority issues** - these affect code quality and security"
        )
    if medium:
        lines.append(
            "- **Review medium priority issues** - these may indicate technical debt"
        )
    if low:
        lines.append("- **Consider low priority issues** - these improve code style")

    lines.extend(
        [
            "",
            "## Tool Logs",
            f"Detailed logs are available in `{REPORTS_DIR.relative_to(ROOT)}/`:",
        ]
    )

    for name, cmd, is_autofix, description in TOOLS:
        log_file = REPORTS_DIR / f"{name}.log"
        if log_file.exists():
            lines.append(f"- `{name}.log` - {description}")

    lines.extend(
        [
            "",
            "## Tool Installation",
            "Missing tools can be installed with:",
            "```bash",
            "pip install isort ruff autoflake black pyupgrade bandit vulture mypy",
            "```",
            "",
            "---",
            "*Generated by `bin/quality/run_code_quality.py`*",
        ]
    )

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Code Quality Suite")
    parser.add_argument(
        "--apply-fixes", action="store_true", help="Apply autofixes before analysis"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("🔍 Code Quality Suite")
    print(f"📁 Working directory: {ROOT}")
    print(f"📊 Reports directory: {REPORTS_DIR}")
    print()

    results = {}
    autofix_results = []

    # Step 1: Apply autofixes if requested
    if args.apply_fixes:
        print("🔧 Applying autofixes...")
        for name, cmd, is_autofix, description in TOOLS:
            if is_autofix:
                if args.verbose:
                    print(f"  Running {name}...")
                rc, output = run_tool(name, cmd, name)
                autofix_results.append((name, rc))
                if args.verbose:
                    status = "✅" if rc == 0 else "❌"
                    print(f"    {status} {name} (rc={rc})")
        print()

    # Step 2: Run analysis tools
    print("🔍 Running analysis tools...")
    for name, cmd, is_autofix, description in TOOLS:
        if not is_autofix:  # Only run analysis tools
            if args.verbose:
                print(f"  Running {name}...")
            rc, output = run_tool(name, cmd, name)
            results[name] = (rc, output)
            if args.verbose:
                status = "✅" if rc == 0 else "❌"
                print(f"    {status} {name} (rc={rc})")

    print()

    # Step 3: Analyze results
    print("📊 Analyzing results...")
    blockers, high, medium, low = analyze_results(results)

    # Step 4: Generate report
    print("📝 Generating report...")
    report_content = generate_report(
        blockers, high, medium, low, args.apply_fixes, results
    )

    # Write report to repo root
    report_path = ROOT / "CODE_QUALITY_REPORT.md"
    report_path.write_text(report_content, encoding="utf-8")

    # Print summary
    print()
    print("📋 Summary:")
    print(f"  🔴 Blockers: {len(blockers)}")
    print(f"  🟠 High: {len(high)}")
    print(f"  🟡 Medium: {len(medium)}")
    print(f"  🟢 Low: {len(low)}")
    print()
    print(f"📄 Report saved to: {report_path}")
    print(f"📁 Logs saved to: {REPORTS_DIR}")

    # Exit with appropriate code
    if blockers:
        print("❌ Exiting with code 1 due to blockers")
        sys.exit(1)
    else:
        print("✅ Exiting with code 0")
        sys.exit(0)


if __name__ == "__main__":
    main()
