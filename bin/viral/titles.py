from __future__ import annotations

import random
import sys
from typing import Any, Dict

from pathlib import Path

# Ensure repository root is on sys.path (needed for `import bin.*`)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _read_yaml(path: str) -> dict:
    """Read YAML configuration file with validation."""
    from bin.utils.config import read_or_die

    required_keys = ["counts", "weights", "heuristics", "patterns", "thumbs"]
    schema_hint = "See conf/viral.yaml.example for required structure"
    return read_or_die(path, required_keys, schema_hint)


def _rng(seed: int) -> random.Random:
    """Create seeded random number generator."""
    return random.Random(seed)


def _fill_title(tpl: str, brief: dict, r: random.Random) -> str:
    """Fill title template with context and random choices."""
    return tpl.format(
        topic=brief.get("title", "topic"),
        benefit=brief.get("benefit", "more results"),
        timeframe=r.choice(
            ["10 minutes", "this week", "2025", "this year", "next month", "today"]
        ),
        adjective=r.choice(
            [
                "definitive",
                "simple",
                "advanced",
                "no-fluff",
                "practical",
                "ultimate",
                "complete",
                "essential",
                "proven",
                "effective",
            ]
        ),
        year=brief.get("year", "2025"),
        n=r.randint(5, 11),
        common_mistake=r.choice(
            [
                "overpaying",
                "guessing",
                "analysis paralysis",
                "wasting time",
                "missing out",
                "doing it wrong",
            ]
        ),
    )


def heuristics_score_title(text: str, brief: dict, cfg: dict) -> float:
    """Score title using heuristics."""
    hw = cfg.get("heuristics", {})
    ideal = (hw.get("ideal_title_min", 45), hw.get("ideal_title_max", 65))
    length = len(text)

    # length band score
    score = (
        max(0, 1.0 - abs((length - sum(ideal) / 2) / (ideal[1] - ideal[0] or 1))) * 0.5
    )

    # power-words
    p = set(w.lower() for w in hw.get("power_words", []))
    score += sum(1 for t in text.lower().split() if t in p) * 0.05

    # number/brackets/question bonuses
    if any(ch.isdigit() for ch in text):
        score += hw.get("number_bonus", 0.2)
    if any(b in text for b in "[]()"):
        score += hw.get("bracket_bonus", 0.1)
    if "?" in text:
        score += hw.get("question_bonus", 0.1)

    return round(min(1.5, score), 4)


def llm_score_title(text: str) -> float:
    """Score title using LLM evaluation."""
    try:
        # Use ModelRunner.for_task for viral-specific configuration
        from bin.model_runner import ModelRunner

        mr = ModelRunner.for_task("viral")

        res = mr.chat(
            [
                {
                    "role": "user",
                    "content": f"Rate 1-10 click-through potential of this YouTube title:\n{text}\nReturn only a number.",
                }
            ]
        )
        raw = str(res.get("message", {}).get("content", "")).strip()

        # Improved number extraction
        import re

        numbers = re.findall(r"\d+(?:\.\d+)?", raw)
        if numbers:
            num = float(numbers[0])
            return max(1.0, min(10.0, num)) / 10.0
        else:
            raise ValueError(f"Could not extract number from response: {raw}")
    except Exception as e:
        # Log warning and fallback to heuristic score
        import logging

        log = logging.getLogger("viral.titles")
        log.warning(f"[viral] LLM unavailable: {e}; using heuristics-only")
        return 0.65


def generate_titles(slug: str, brief: dict, seed: int) -> Dict[str, Any]:
    """Generate title variants and score them."""
    cfg = _read_yaml("conf/viral.yaml")
    r = _rng(seed + 7)  # Different seed for titles
    patterns = cfg.get("patterns", {}).get("titles", [])
    out = []

    for i in range(cfg.get("counts", {}).get("titles", 5)):
        tpl = patterns[i % max(1, len(patterns))]
        t = _fill_title(tpl, brief, r)
        out.append({"id": f"title_{i+1}", "text": t})

    # score
    scored = []
    for item in out:
        heur = heuristics_score_title(item["text"], brief, cfg)
        llm = llm_score_title(item["text"])
        final = (
            cfg["weights"]["titles"]["heuristics"] * heur
            + cfg["weights"]["titles"]["llm"] * llm
        )
        scored.append(
            {**item, "score": {"heur": heur, "llm": llm, "final": round(final, 4)}}
        )

    scored.sort(key=lambda x: x["score"]["final"], reverse=True)
    return {"variants": scored, "selected": scored[0]["id"]}
