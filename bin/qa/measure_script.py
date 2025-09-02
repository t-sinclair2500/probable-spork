import json
import re

from pathlib import Path


def words_per_minute(text: str, audio_seconds: float) -> float:
    """Calculate words per minute from text and audio duration."""
    words = re.findall(r"\b[\w']+\b", text)
    mins = max(audio_seconds / 60.0, 1e-6)
    return len(words) / mins


def has_cta(text: str) -> bool:
    """Detect call-to-action phrases in text."""
    cta_patterns = [
        r"\bsubscribe\b",
        r"\bjoin\b",
        r"\bdownload\b",
        r"\bsign up\b",
        r"\bnewsletter\b",
        r"\bcheck (the )?link\b",
        r"\blike\b",
        r"\bshare\b",
        r"\bcomment\b",
        r"\bfollow\b",
        r"\bvisit\b",
        r"\bclick\b",
    ]
    return any(re.search(p, text, flags=re.I) for p in cta_patterns)


def load_script(slug: str) -> str:
    """Load script text from various possible locations."""
    p1 = Path("scripts") / f"{slug}.txt"
    if p1.exists():
        return p1.read_text(encoding="utf-8")

    # fallback: read from metadata if script embedded
    mp = Path("videos") / f"{slug}.metadata.json"
    if mp.exists():
        try:
            return json.loads(mp.read_text()).get("script", "")
        except Exception:
            return ""
    return ""


def evaluate(slug: str, thresholds: dict, audio_duration_s: float) -> dict:
    """Evaluate script quality metrics."""
    txt = load_script(slug)
    wpm = words_per_minute(txt, audio_duration_s)
    banned = [t for t in thresholds.get("ban_tokens", []) if t in txt]

    return {
        "wpm": wpm,
        "cta_present": has_cta(txt) if thresholds.get("require_cta", True) else True,
        "banned_tokens": banned,
        "script_length_chars": len(txt),
        "script_length_words": len(re.findall(r"\b[\w']+\b", txt)),
    }
