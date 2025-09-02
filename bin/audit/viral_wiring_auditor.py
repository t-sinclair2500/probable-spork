#!/usr/bin/env python3
"""
Viral Wiring Auditor — Comprehensive integration verification

Checks viral/shorts/seo modules are correctly integrated across:
- Pipeline steps present & ordered
- CLI flags & config gating
- Config files exist & have minimal schema
- LLM hygiene (ModelRunner usage, fallbacks)
- Artifacts & metadata contracts
- Encoder fallback & CTA overlay hooks
- Tooling health (ffmpeg, VideoToolbox)
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RPT_DIR = ROOT / "reports" / "audit"
RPT_DIR.mkdir(parents=True, exist_ok=True)


def _read_yaml(path: Path) -> dict:
    """Read YAML file safely, return empty dict if missing."""
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def check_pipeline_steps() -> Tuple[str, str]:
    """Check viral steps exist and are ordered correctly."""
    txt = (ROOT / "bin" / "run_pipeline.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    order = [
        "assemble",
        "viral_lab",
        "shorts_lab",
        "seo_packaging",
        "end_screens",
        "qa",
    ]
    missing = [s for s in order if s not in txt]
    if missing:
        return ("FAIL", f"Missing steps: {missing}")

    # Look for specific execution patterns in the YouTube lane
    # Find the viral lab execution section
    viral_section = txt.find("=== RUNNING VIRAL LAB ===")
    qa_section = txt.find("=== RUNNING QA GATES ===")

    if viral_section == -1:
        return ("FAIL", "Viral lab execution section not found")

    if qa_section == -1:
        return ("FAIL", "QA gates execution section not found")

    # Check that QA comes after viral lab in execution order
    if qa_section < viral_section:
        return (
            "FAIL",
            f"QA gates({qa_section}) executed before viral lab({viral_section})",
        )

    return ("PASS", "Steps present and ordered correctly")


def check_cli_flags() -> Tuple[str, str]:
    """Check CLI flags exist in run_pipeline.py."""
    txt = (ROOT / "bin" / "run_pipeline.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    need = [
        "--enable-viral",
        "--no-viral",
        "--enable-shorts",
        "--no-shorts",
        "--enable-seo",
        "--no-seo",
        "--yt-only",
        "--from-step",
        "--seed",
    ]
    miss = [n for n in need if n not in txt]
    return (
        ("PASS", "All flags present")
        if not miss
        else ("FAIL", f"Missing argparse flags: {miss}")
    )


def check_configs() -> List[Tuple[str, str, str]]:
    """Check config files exist and have required keys."""
    res = []

    # Check global.yaml viral settings
    g = _read_yaml(ROOT / "conf" / "global.yaml")
    viral_config = g.get("viral", {})
    for key in ["enabled", "shorts_enabled", "seo_enabled"]:
        ok = viral_config.get(key) is not None
        res.append(("global.yaml", "PASS" if ok else "FAIL", f"viral.{key}"))

    # Check viral.yaml required keys
    v = _read_yaml(ROOT / "conf" / "viral.yaml")

    def must(d: dict, keys: List[str]) -> Tuple[str, str]:
        ok = d
        trail = []
        for k in keys:
            trail.append(k)
            ok = ok.get(k, None) if isinstance(ok, dict) else None
            if ok is None:
                return ("FAIL", f"Missing {'.'.join(trail)}")
        return ("PASS", f"has {'.'.join(keys)}")

    viral_checks = [
        ("counts", ["counts"]),
        ("weights", ["weights"]),
        ("heuristics", ["heuristics"]),
        ("patterns", ["patterns"]),
        ("thumbs", ["thumbs"]),
    ]

    for name, keys in viral_checks:
        status, msg = must(v, keys)
        res.append(("viral.yaml", status, msg))

    # Check shorts.yaml required keys
    s = _read_yaml(ROOT / "conf" / "shorts.yaml")
    shorts_checks = [
        ("counts", ["counts"]),
        ("selection", ["selection"]),
        ("crop", ["crop"]),
        ("captions", ["captions"]),
        ("overlays", ["overlays"]),
        ("audio", ["audio"]),
        ("encoding", ["encoding"]),
        ("filename", ["filename"]),
    ]

    for name, keys in shorts_checks:
        status, msg = must(s, keys)
        res.append(("shorts.yaml", status, msg))

    # Check seo.yaml required keys
    seo = _read_yaml(ROOT / "conf" / "seo.yaml")
    seo_checks = [
        ("templates", ["templates"]),
        ("tags", ["tags"]),
        ("chapters", ["chapters"]),
        ("cta", ["cta"]),
        ("end_screen", ["end_screen"]),
    ]

    for name, keys in seo_checks:
        status, msg = must(seo, keys)
        res.append(("seo.yaml", status, msg))

    return res


def check_llm_hygiene() -> Tuple[str, str]:
    """Check LLM configuration and usage."""
    m = _read_yaml(ROOT / "conf" / "models.yaml")
    viral = m.get("models", {}).get("viral", {})
    need = ["chat_model", "timeout_s", "seed"]
    miss = [k for k in need if viral.get(k) is None]
    if miss:
        return ("FAIL", f"models.yaml viral.{miss} missing")

    # Check code usage of ModelRunner.for_task("viral")
    hooks_txt = (ROOT / "bin" / "viral" / "hooks.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    titles_txt = (ROOT / "bin" / "viral" / "titles.py").read_text(
        encoding="utf-8", errors="ignore"
    )

    ok_hooks = 'ModelRunner.for_task("viral")' in hooks_txt
    ok_titles = 'ModelRunner.for_task("viral")' in titles_txt

    if not (ok_hooks and ok_titles):
        missing = []
        if not ok_hooks:
            missing.append("hooks.py")
        if not ok_titles:
            missing.append("titles.py")
        return ("FAIL", f"ModelRunner.for_task('viral') not used in {missing}")

    return ("PASS", "LLM config & usage ok")


def check_encoder_overlay() -> List[Tuple[str, str]]:
    """Check encoder fallback and CTA overlay hooks."""
    res = []
    asm = (ROOT / "bin" / "assemble_video.py").read_text(
        encoding="utf-8", errors="ignore"
    )

    # Check encoder fallback
    has_videotoolbox = "h264_videotoolbox" in asm
    has_libx264 = "libx264" in asm
    if has_videotoolbox and has_libx264:
        res.append(
            ("encoder_fallback", "PASS", "h264_videotoolbox and libx264 both present")
        )
    else:
        res.append(
            (
                "encoder_fallback",
                "FAIL",
                f"Missing: videotoolbox={has_videotoolbox}, libx264={has_libx264}",
            )
        )

    # Check CTA overlay hook
    has_cta = "cta_16x9.mov" in asm
    res.append(
        ("cta_overlay_hook", "PASS" if has_cta else "WARN", "cta_16x9.mov overlay hook")
    )

    return res


def check_tools() -> Tuple[str, str]:
    """Check ffmpeg/ffprobe availability and VideoToolbox."""
    try:
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if out.returncode != 0:
            return ("WARN", "ffmpeg present but non-zero rc")
    except FileNotFoundError:
        return ("FAIL", "ffmpeg missing")

    try:
        out = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True)
        if out.returncode != 0:
            return ("WARN", "ffprobe present but non-zero rc")
    except FileNotFoundError:
        return ("FAIL", "ffprobe missing")

    # Check VideoToolbox on macOS
    mac = platform.system() == "Darwin"
    if mac:
        try:
            vt = subprocess.run(
                ["ffmpeg", "-hide_banner", "-hwaccels"], capture_output=True, text=True
            )
            if "videotoolbox" not in vt.stdout.lower():
                return ("WARN", "videotoolbox not listed on macOS")
        except Exception:
            return ("WARN", "Could not check VideoToolbox availability")

    return ("PASS", "ffmpeg/ffprobe available" + (" + VideoToolbox" if mac else ""))


def check_artifacts(slug: Optional[str] = None) -> List[Tuple[str, str]]:
    """Check artifact contracts if slug provided."""
    res = []

    if not slug:
        res.append(("artifacts", "SKIP", "No slug provided"))
        return res

    # Check metadata.json structure
    meta_path = ROOT / "videos" / f"{slug}.metadata.json"
    if not meta_path.exists():
        res.append(("metadata_exists", "WARN", f"metadata.json not found for {slug}"))
        return res

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        viral_section = meta.get("viral", {})

        # Check viral variants structure
        variants = viral_section.get("variants", {})
        for variant_type in ["hooks", "titles", "thumbs"]:
            if variant_type in variants:
                res.append(
                    (f"viral_variants_{variant_type}", "PASS", f"has {variant_type}")
                )
            else:
                res.append(
                    (
                        f"viral_variants_{variant_type}",
                        "WARN",
                        f"missing {variant_type}",
                    )
                )

        # Check selected viral items
        selected = viral_section.get("selected", {})
        if selected:
            res.append(("viral_selected", "PASS", "has selected viral items"))
        else:
            res.append(("viral_selected", "WARN", "no selected viral items"))

    except Exception as e:
        res.append(("metadata_parse", "FAIL", f"Failed to parse metadata.json: {e}"))

    # Check shorts directory
    shorts_dir = ROOT / "videos" / slug / "shorts"
    if shorts_dir.exists():
        shorts_files = list(shorts_dir.glob("*.mp4"))
        if shorts_files:
            res.append(
                ("shorts_files", "PASS", f"Found {len(shorts_files)} shorts files")
            )
        else:
            res.append(
                ("shorts_files", "WARN", "shorts directory exists but no .mp4 files")
            )
    else:
        res.append(("shorts_files", "WARN", "shorts directory not found"))

    return res


def run_audit(slug: Optional[str] = None) -> Dict[str, Any]:
    """Run complete viral wiring audit."""
    results = []

    # Pipeline steps
    status, msg = check_pipeline_steps()
    results.append(
        {
            "check_id": "pipeline_steps",
            "status": status,
            "details": msg,
            "suggest_fix": (
                "Add missing steps to run_pipeline.py or fix ordering"
                if status == "FAIL"
                else None
            ),
        }
    )

    # CLI flags
    status, msg = check_cli_flags()
    results.append(
        {
            "check_id": "cli_flags",
            "status": status,
            "details": msg,
            "suggest_fix": (
                "Add missing argparse flags to run_pipeline.py"
                if status == "FAIL"
                else None
            ),
        }
    )

    # Config files
    config_results = check_configs()
    for file_name, status, msg in config_results:
        results.append(
            {
                "check_id": f"config_{file_name.replace('.yaml', '')}",
                "status": status,
                "details": msg,
                "suggest_fix": (
                    f"Add missing keys to {file_name}" if status == "FAIL" else None
                ),
            }
        )

    # LLM hygiene
    status, msg = check_llm_hygiene()
    results.append(
        {
            "check_id": "llm_hygiene",
            "status": status,
            "details": msg,
            "suggest_fix": (
                "Add viral config to models.yaml and use ModelRunner.for_task('viral')"
                if status == "FAIL"
                else None
            ),
        }
    )

    # Encoder and overlay
    encoder_results = check_encoder_overlay()
    for check_name, status, msg in encoder_results:
        results.append(
            {
                "check_id": check_name,
                "status": status,
                "details": msg,
                "suggest_fix": (
                    "Add encoder fallback logic or CTA overlay hooks to assemble_video.py"
                    if status == "FAIL"
                    else None
                ),
            }
        )

    # Tools
    status, msg = check_tools()
    results.append(
        {
            "check_id": "tools",
            "status": status,
            "details": msg,
            "suggest_fix": (
                "Install ffmpeg/ffprobe or check VideoToolbox on macOS"
                if status == "FAIL"
                else None
            ),
        }
    )

    # Artifacts (if slug provided)
    artifact_results = check_artifacts(slug)
    for check_name, status, msg in artifact_results:
        results.append(
            {
                "check_id": check_name,
                "status": status,
                "details": msg,
                "suggest_fix": (
                    "Run viral pipeline for slug to generate artifacts"
                    if status == "WARN"
                    else None
                ),
            }
        )

    # Summary
    total_checks = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    warned = sum(1 for r in results if r["status"] == "WARN")
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    return {
        "audit_info": {
            "timestamp": str(Path(__file__).stat().st_mtime),
            "slug": slug,
            "total_checks": total_checks,
            "passed": passed,
            "failed": failed,
            "warned": warned,
            "skipped": skipped,
            "overall_status": "FAIL" if failed > 0 else "PASS",
        },
        "results": results,
    }


def write_reports(audit_data: Dict[str, Any], slug: Optional[str] = None):
    """Write JSON and Markdown reports."""
    # JSON report
    json_path = RPT_DIR / "viral_wiring_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)

    # Markdown report
    md_path = RPT_DIR / "viral_wiring_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Viral Wiring Audit Report\n\n")

        info = audit_data["audit_info"]
        f.write(f"**Audit Date:** {info['timestamp']}\n")
        f.write(f"**Slug:** {slug or 'None'}\n")
        f.write(f"**Overall Status:** {info['overall_status']}\n\n")

        f.write(
            f"**Summary:** {info['passed']} PASS, {info['failed']} FAIL, {info['warned']} WARN, {info['skipped']} SKIP\n\n"
        )

        f.write("## Detailed Results\n\n")
        f.write("| Check | Status | Details | Suggested Fix |\n")
        f.write("|------|--------|---------|----------------|\n")

        for result in audit_data["results"]:
            status_emoji = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⏭️"}.get(
                result["status"], "❓"
            )
            fix = result.get("suggest_fix", "")
            f.write(
                f"| {result['check_id']} | {status_emoji} {result['status']} | {result['details']} | {fix} |\n"
            )

        f.write("\n## Recommendations\n\n")

        failed_checks = [r for r in audit_data["results"] if r["status"] == "FAIL"]
        if failed_checks:
            f.write("### Critical Issues (Must Fix):\n\n")
            for check in failed_checks:
                f.write(f"- **{check['check_id']}**: {check['details']}\n")
                if check.get("suggest_fix"):
                    f.write(f"  - Fix: {check['suggest_fix']}\n")
            f.write("\n")

        warned_checks = [r for r in audit_data["results"] if r["status"] == "WARN"]
        if warned_checks:
            f.write("### Warnings (Should Address):\n\n")
            for check in warned_checks:
                f.write(f"- **{check['check_id']}**: {check['details']}\n")
                if check.get("suggest_fix"):
                    f.write(f"  - Fix: {check['suggest_fix']}\n")
            f.write("\n")

        if not failed_checks and not warned_checks:
            f.write("🎉 All checks passed! Viral wiring is correctly configured.\n\n")


def main():
    parser = argparse.ArgumentParser(description="Viral Wiring Auditor")
    parser.add_argument("--slug", help="Slug to check artifacts for")
    args = parser.parse_args()

    print("🔍 Running Viral Wiring Audit...")
    audit_data = run_audit(args.slug)

    write_reports(audit_data, args.slug)

    info = audit_data["audit_info"]
    print(
        f"📊 Audit Complete: {info['passed']} PASS, {info['failed']} FAIL, {info['warned']} WARN"
    )
    print("📄 Reports saved to: reports/audit/viral_wiring_report.json")
    print("📄 Reports saved to: reports/audit/viral_wiring_report.md")

    if info["overall_status"] == "FAIL":
        print("❌ Audit FAILED - check report for critical issues")
        sys.exit(1)
    else:
        print("✅ Audit PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
