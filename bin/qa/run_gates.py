from __future__ import annotations

import argparse
import json
import subprocess
import sys

from pathlib import Path

# Add the bin directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qa import (
    measure_audio,
    measure_monetization,
    measure_research,
    measure_script,
    measure_video,
    measure_visuals,
)
from qa.gates import GateResult, pass_fail


def _ensure_dir(p: Path) -> None:
    """Ensure directory exists."""
    p.parent.mkdir(parents=True, exist_ok=True)


def _read_yaml(path: str) -> dict:
    """Read YAML configuration file."""
    try:
        import yaml

        with open(path, "r") as f:
            return yaml.safe_load(f)
    except ImportError:
        # Fallback to basic JSON-like parsing for simple YAML
        with open(path, "r") as f:
            content = f.read()
        # Simple YAML to dict conversion for our use case
        result = {}
        current_section = None
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line and not line.startswith(" "):
                current_section = line.split(":")[0].strip()
                result[current_section] = {}
            elif current_section and ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value.startswith("[") and value.endswith("]"):
                    # Parse list
                    items = value[1:-1].split(",")
                    result[current_section][key] = [
                        item.strip().strip("\"'") for item in items if item.strip()
                    ]
                elif value.lower() in ("true", "false"):
                    result[current_section][key] = value.lower() == "true"
                elif value.replace(".", "").replace("-", "").isdigit():
                    result[current_section][key] = float(value)
                else:
                    result[current_section][key] = value.strip("\"'")
        return result


def evaluate_all(slug: str, qa_cfg: dict) -> dict:
    """Evaluate all quality gates for a given slug."""
    th = qa_cfg.get("thresholds", {})

    # Audio/video durations
    vpath = Path("videos") / f"{slug}_cc.mp4"
    apath = Path("voiceovers") / f"{slug}.mp3"
    duration_s = 0.0

    try:
        # Try to get duration from audio first, then video
        if apath.exists():
            duration_s = float(
                subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=nw=1:nk=1",
                        str(apath),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            )
        elif vpath.exists():
            duration_s = float(
                subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=nw=1:nk=1",
                        str(vpath),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            )
    except Exception:
        duration_s = 0.0

    results = []

    # Script gate
    s_metrics = measure_script.evaluate(slug, th.get("script", {}), duration_s)
    s_ok = (
        (th["script"]["wpm_min"] <= s_metrics["wpm"] <= th["script"]["wpm_max"])
        and s_metrics["cta_present"]
        and (len(s_metrics["banned_tokens"]) == 0)
    )
    results.append(
        GateResult(
            "script", pass_fail(s_ok), s_metrics, th.get("script", {}), []
        ).__dict__
    )

    # Audio gate
    audio_path = str(apath if apath.exists() else vpath)
    a_lufs = measure_audio.ebur128_metrics(audio_path)
    tp = measure_audio.true_peak_db(audio_path)
    sil = measure_audio.silence_percentage(audio_path) if apath.exists() else 0.0
    sib = measure_audio.sibilance_proxy_db(audio_path)
    a_thr = th.get("audio", {})

    lufs_ok = (
        a_lufs["lufs"] is not None
        and abs(a_lufs["lufs"] - a_thr["lufs_target"]) <= a_thr["lufs_tolerance"]
    )
    tp_ok = tp is not None and tp <= a_thr["truepeak_max_db"]
    lra_ok = a_lufs["lra"] is not None and a_lufs["lra"] <= a_thr["lra_max"]
    sil_ok = sil <= a_thr["silence_max_pct"]
    sib_ok = True if sib is None else (sib <= a_thr["sibilance_max_db"])
    a_ok = all([lufs_ok, tp_ok, lra_ok, sil_ok, sib_ok])

    results.append(
        GateResult(
            "audio",
            pass_fail(a_ok),
            {
                "lufs": a_lufs,
                "truepeak_db": tp,
                "silence_pct": sil,
                "sibilance_db": sib,
            },
            a_thr,
            [],
        ).__dict__
    )

    # Visuals gate
    v_thr = th.get("visuals", {})
    vis1 = measure_visuals.evaluate_contrast_and_safe_areas(slug, v_thr)
    vis2 = measure_visuals.evaluate_scene_durations(slug, v_thr)
    vis_ok = (vis1["contrast_failures"] == 0) and (
        vis2.get("duration_failures", 0) == 0
    )
    results.append(
        GateResult(
            "visuals",
            pass_fail(vis_ok, warn=True),
            {"contrast": vis1, "durations": vis2},
            v_thr,
            vis1["issues"],
        ).__dict__
    )

    # Video Master gate
    vm_thr = th.get("video_master", {})
    if vpath.exists():
        streams = measure_video.ffprobe_streams(str(vpath))
        prof_ok, notes = measure_video.delivery_profile_ok(streams, vm_thr)
        results.append(
            GateResult(
                "video_master", pass_fail(prof_ok), {"streams": streams}, vm_thr, notes
            ).__dict__
        )
    else:
        results.append(
            GateResult(
                "video_master",
                "FAIL",
                {"error": "Video file not found"},
                vm_thr,
                ["Video file not found"],
            ).__dict__
        )

    # Research/claims gate
    r_thr = th.get("research", {})
    r_metrics = measure_research.evaluate(slug, r_thr)
    r_ok = r_metrics["facts_below_min"] == 0 and (
        r_thr.get("fact_guard", "block") != "block"
        or r_metrics.get("fact_guard_status", "clear") == "clear"
    )
    results.append(
        GateResult("research", pass_fail(r_ok), r_metrics, r_thr, []).__dict__
    )

    # Monetization gate
    m_thr = th.get("monetization", {})
    m_metrics = measure_monetization.evaluate(slug, m_thr)
    m_ok = (
        m_metrics.get("disclosure_ok", False)
        and m_metrics.get("utm_ok", False)
        and m_metrics.get("link_count_ok", True)
    )
    results.append(
        GateResult("monetization", pass_fail(m_ok), m_metrics, m_thr, []).__dict__
    )

    return {"slug": slug, "results": results}


def main() -> int:
    """Main CLI entry point."""
    ap = argparse.ArgumentParser(description="Run quality gates for content")
    ap.add_argument("--slug", required=True, help="Content slug to evaluate")
    ap.add_argument("--strict", action="store_true", help="Treat WARN as blocking")
    args = ap.parse_args()

    # Load QA configuration
    qa_cfg = _read_yaml("conf/qa.yaml")
    report = evaluate_all(args.slug, qa_cfg)

    # Determine policy
    required = set(qa_cfg.get("policy", {}).get("required_gates", []))
    block_on_warn = qa_cfg.get("policy", {}).get("block_on_warn", False) or args.strict

    # Analyze results
    statuses = {r["gate"]: r["status"] for r in report["results"]}
    fail_block = any(statuses[g] == "FAIL" for g in required if g in statuses)
    warn_block = block_on_warn and any(
        statuses[g] == "WARN" for g in required if g in statuses
    )

    # Write reports
    out_json = Path("reports") / args.slug / "qa_report.json"
    out_txt = Path("reports") / args.slug / "qa_report.txt"
    _ensure_dir(out_json)

    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Generate human-readable report
    txt_lines = [f"QA Report for {args.slug}", "=" * 40, ""]
    for r in report["results"]:
        status_icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[r["status"]]
        txt_lines.append(f"{status_icon} {r['gate']}: {r['status']}")
        if r.get("notes"):
            for note in r["notes"]:
                txt_lines.append(f"  - {note}")
    txt_lines.append("")

    if fail_block:
        txt_lines.append("❌ BLOCKING FAILURES DETECTED")
    elif warn_block:
        txt_lines.append("⚠ WARNINGS BLOCKING (strict mode)")
    else:
        txt_lines.append("✅ ALL GATES PASSED")

    out_txt.write_text("\n".join(txt_lines), encoding="utf-8")

    # Set exit code
    if fail_block:
        return 1
    if warn_block:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
