import json

from pathlib import Path


def evaluate(slug: str, thresholds: dict) -> dict:
    """Evaluate research quality and fact-checking compliance."""
    beats_p = Path("data") / slug / "grounded_beats.json"
    facts_unresolved = 0
    min_citations = int(thresholds.get("min_citations_per_beat", 1))
    beats_checked = 0

    if not beats_p.exists():
        return {
            "beats_checked": 0,
            "facts_below_min": 0,
            "fact_guard_status": "clear",
            "error": "grounded_beats.json not found",
        }

    try:
        with beats_p.open("r", encoding="utf-8") as fh:
            beats = json.load(fh)

        for b in beats:
            if not b.get("is_factual", True):
                continue
            beats_checked += 1
            cites = len(b.get("citations", []))
            if cites < min_citations:
                facts_unresolved += 1
    except Exception as e:
        return {
            "beats_checked": 0,
            "facts_below_min": 0,
            "fact_guard_status": "clear",
            "error": f"Failed to parse grounded_beats.json: {str(e)}",
        }

    # Fact guard: consume status file if exists
    guard_p = Path("data") / slug / "fact_guard.json"
    guard_status = "clear"
    if guard_p.exists():
        try:
            guard_status = json.loads(guard_p.read_text()).get("status", "clear")
        except Exception:
            pass

    return {
        "beats_checked": beats_checked,
        "facts_below_min": facts_unresolved,
        "fact_guard_status": guard_status,
    }
