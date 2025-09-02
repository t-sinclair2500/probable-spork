# bin/utils/media.py
from __future__ import annotations

import json
import re
import subprocess
from typing import List, Optional, Sequence, Tuple

from pathlib import Path

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}


def _candidate_score(name: str, slug: str) -> Tuple[int, int]:
    """
    Lower score is better.
    0 = exact stem match (e.g., my-slug.mp3)
    1 = date/prefix/suffix variations (e.g., 2024-08-21_my-slug.mp3, my-slug_v2.wav)
    2 = contains slug tokenized with separators
    3 = other (weak)
    Tiebreak on shorter stem distance.
    """
    stem = Path(name).stem.lower()
    slug_l = slug.lower()
    if stem == slug_l:
        return (0, 0)
    # separators considered
    parts = re.split(r"[-_.\s]+", stem)
    if (
        slug_l in parts
        or stem.startswith(slug_l + "-")
        or stem.endswith("-" + slug_l)
        or f"_{slug_l}_" in f"_{stem}_"
    ):
        # common prefix/suffix or tokenized
        return (1, abs(len(stem) - len(slug_l)))
    if slug_l in stem:
        return (2, abs(len(stem) - len(slug_l)))
    return (3, len(stem))


def find_voiceover_for_slug(
    slug: str, search_dirs: Sequence[str] = ("voiceovers",)
) -> Optional[Path]:
    """
    Search known voiceover dirs for a file that best matches the slug.
    Preference: exact stem match → prefix/suffix tokenized → contains → newest mtime.
    """
    candidates: List[Tuple[Tuple[int, int], float, Path]] = []
    for d in search_dirs:
        p = Path(d)
        if not p.exists():
            continue
        for f in p.iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() not in AUDIO_EXTS:
                continue
            score = _candidate_score(f.name, slug)
            if score[0] <= 2:  # accept reasonably matching names
                try:
                    mtime = f.stat().st_mtime
                except Exception:
                    mtime = 0.0
                candidates.append((score, -mtime, f))
    if not candidates:
        return None
    # sort by score asc, then newest (negative mtime), then path name
    candidates.sort(key=lambda t: (t[0][0], t[0][1], t[1], t[2].name))
    return candidates[0][2]


def resolve_metadata_for_slug(slug: str) -> Optional[Path]:
    """
    Prefer scripts/<slug>.metadata.json, then videos/<slug>.metadata.json, then videos/<slug>/metadata.json
    """
    probes = [
        Path("scripts") / f"{slug}.metadata.json",
        Path("videos") / f"{slug}.metadata.json",
        Path("videos") / slug / "metadata.json",
    ]
    for p in probes:
        if p.exists():
            return p
    return None


def sanitize_text_for_pillow(text: str) -> str:
    """
    Replace Unicode ellipsis with ASCII to avoid missing glyphs in PIL fonts.
    You may extend with smart quotes if needed.
    """
    if text is None:
        return ""
    return str(text).replace("\u2026", "...")


def ffprobe_json(path: Path) -> dict:
    """
    Return ffprobe JSON (streams + format). Requires ffprobe on PATH.
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    # Short-lived; capture_output is acceptable here
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {proc.stderr}")
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {}


def write_media_inspector(slug: str, output_path: Path, encode_args: dict) -> Path:
    """
    Write videos/<slug>.encode.json with ffprobe details + encode args used.
    """
    out_dir = Path("videos")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "slug": slug,
        "output": str(output_path),
        "ffprobe": ffprobe_json(output_path),
        "encode_args": encode_args,
    }
    dest = out_dir / f"{slug}.encode.json"
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return dest
