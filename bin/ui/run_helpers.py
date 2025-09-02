from __future__ import annotations

import os
import subprocess
from typing import Dict, Generator, List

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _exists(p: Path) -> bool:
    return p.exists()


def discover_slugs() -> List[str]:
    cand = set()
    for folder, ext in [
        ("scripts", ".txt"),
        ("videos", ".metadata.json"),
        ("scenescripts", ".json"),
    ]:
        d = ROOT / folder
        if not d.exists():
            continue
        for p in d.glob(f"*{ext}"):
            name = p.stem.replace(".metadata", "")
            cand.add(name)

    # sort by recent video metadata first, then scripts
    def mtime(slug: str) -> float:
        v = ROOT / "videos" / f"{slug}.metadata.json"
        s = ROOT / "scripts" / f"{slug}.txt"
        return max(
            v.stat().st_mtime if v.exists() else 0,
            s.stat().st_mtime if s.exists() else 0,
        )

    return sorted(cand, key=mtime, reverse=True)


def health_check() -> Dict[str, str]:
    info = {"ffmpeg": "missing", "ffprobe": "missing", "videotoolbox": "unknown"}
    try:
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        info["ffmpeg"] = "ok" if out.returncode == 0 else f"rc={out.returncode}"
    except FileNotFoundError:
        pass
    try:
        out = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True)
        info["ffprobe"] = "ok" if out.returncode == 0 else f"rc={out.returncode}"
    except FileNotFoundError:
        pass
    # hwaccels
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-hwaccels"], capture_output=True, text=True
        )
        info["videotoolbox"] = (
            "available" if "videotoolbox" in out.stdout.lower() else "unavailable"
        )
    except Exception:
        pass
    return info


def stream_process(
    cmd: List[str], env: Dict[str, str] | None = None, cwd: str | None = None
) -> Generator[str, None, int]:
    """Yield stdout/stderr lines for Gradio live streaming."""
    proc = subprocess.Popen(
        cmd,
        cwd=cwd or str(ROOT),
        env={**os.environ, **(env or {})},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
    )
    try:
        for line in proc.stdout:
            yield line.rstrip("\n")
        proc.wait()
    finally:
        if proc.stdout:
            proc.stdout.close()
    return proc.returncode


def latest_artifacts(slug: str) -> Dict[str, List[str] | str | None]:
    thumbs_dir = ROOT / "videos" / slug / "thumbs"
    shorts_dir = ROOT / "videos" / slug / "shorts"
    qa_json = ROOT / "reports" / slug / "qa_report.json"
    meta = ROOT / "videos" / f"{slug}.metadata.json"
    thumbs = (
        sorted([str(p) for p in thumbs_dir.glob("*.png")])
        if thumbs_dir.exists()
        else []
    )
    shorts = (
        sorted([str(p) for p in shorts_dir.glob("*.mp4")])
        if shorts_dir.exists()
        else []
    )
    return {
        "thumbs": thumbs,
        "shorts": shorts,
        "qa_report": str(qa_json) if qa_json.exists() else None,
        "metadata": str(meta) if meta.exists() else None,
    }



