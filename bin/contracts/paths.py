from __future__ import annotations

from typing import Dict

from pathlib import Path


def artifact_paths(slug: str) -> Dict[str, Path]:
    return {
        "research_sources": Path("data") / slug / "collected_sources.json",
        "research_db": Path("data") / "research.db",
        "grounded_beats": Path("data") / slug / "grounded_beats.json",
        "references": Path("data") / slug / "references.json",
        "script_primary": Path("scripts") / f"{slug}.txt",
        # Callers may choose a dated variant; provide a helper default
        "scenescript": Path("scenescripts") / f"{slug}.json",
        "animatics_dir": Path("assets") / f"{slug}_animatics",
        "voiceover_mp3": Path("voiceovers") / f"{slug}.mp3",
        "voiceover_srt": Path("voiceovers") / f"{slug}.srt",
        "video_cc": Path("videos") / f"{slug}_cc.mp4",
        "video_meta": Path("videos") / f"{slug}.metadata.json",
    }


def ensure_dirs_for_slug(slug: str) -> None:
    ap = artifact_paths(slug)
    # Ensure container dirs for artifacts that are directories
    ap["animatics_dir"].mkdir(parents=True, exist_ok=True)
    # Common folders
    Path("logs/subprocess").mkdir(parents=True, exist_ok=True)
    Path("jobs").mkdir(parents=True, exist_ok=True)
    Path("data/analytics").mkdir(parents=True, exist_ok=True)
