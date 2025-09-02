from __future__ import annotations

import random
import sys
import time
from typing import Any, Dict, List

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
    r = random.Random(seed)
    return r


def _fill_template(tpl: str, ctx: dict, r: random.Random) -> str:
    """Fill template with context and random choices."""
    # naive fill with context defaults
    return tpl.format(
        topic=ctx.get("topic", ctx.get("slug", "topic")),
        noun=ctx.get("noun", "strategy"),
        adjective=r.choice(
            [
                "uncomfortable",
                "counterintuitive",
                "wild",
                "underrated",
                "surprising",
                "shocking",
                "amazing",
                "incredible",
                "mind-blowing",
                "game-changing",
                "revolutionary",
                "breakthrough",
                "exposed",
                "revealed",
            ]
        ),
        inversion=r.choice(
            [
                "hard truth",
                "dirty secret",
                "myth",
                "lie",
                "scam",
                "trap",
                "mistake",
                "failure",
                "problem",
                "issue",
            ]
        ),
        benefit=ctx.get("benefit", "time"),
        action=ctx.get("action", "buying"),
        n=r.randint(3, 9),
        timeframe=r.choice(
            ["10 minutes", "a week", "2025", "this year", "next month", "today"]
        ),
        year=time.strftime("%Y"),
    )


def heuristics_score_hook(text: str, brief: dict, viral_cfg: dict) -> float:
    """Score hook using heuristics."""
    hw = viral_cfg.get("heuristics", {})
    pwords = set(w.lower() for w in hw.get("power_words", []))
    tokens = [t.lower() for t in text.split()]
    score = 0.0

    # power words
    score += sum(1 for t in tokens if t in pwords) * 0.1

    # numbers
    if any(ch.isdigit() for ch in text):
        score += viral_cfg["heuristics"].get("number_bonus", 0.2)

    # question mark / why/how
    if "?" in text or any(w in tokens for w in ["why", "how"]):
        score += viral_cfg["heuristics"].get("question_bonus", 0.1)

    # novelty vs brief keywords
    k = set(t.lower() for t in brief.get("keywords", []))
    overlap = len(k & set(tokens))
    score += (1.0 - min(1.0, overlap / max(1, len(k)))) * viral_cfg["heuristics"].get(
        "novelty_weight", 0.3
    )

    # length pressure (prefer 8–16 words)
    w = len(tokens)
    score += max(0, 1.0 - abs(w - 12) / 12.0) * 0.3

    return round(score, 4)


def llm_score_hook(text: str) -> float:
    """Score hook using LLM evaluation."""
    try:
        # Use ModelRunner.for_task for viral-specific configuration
        from bin.model_runner import ModelRunner

        mr = ModelRunner.for_task("viral")

        msg = [
            {
                "role": "user",
                "content": f"Rate 1-10 the scroll-stopping power of this YouTube hook (10=max):\n\n{text}\n\nReturn only a number.",
            }
        ]
        res = mr.chat(msg)
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

        log = logging.getLogger("viral.hooks")
        log.warning(f"[viral] LLM unavailable: {e}; using heuristics-only")
        return 0.6  # heuristic fallback


def generate_hooks(
    slug: str, brief: dict, count: int, seed: int
) -> List[Dict[str, Any]]:
    """Generate hook variants using templates."""
    cfg = _read_yaml("conf/viral.yaml")
    r = _rng(seed)
    ctx = {
        "slug": slug,
        "topic": brief.get("title", slug),
        "benefit": "time",
        "action": "buying",
    }
    variants = []

    patterns = cfg.get("patterns", {}).get("hooks", [])
    for tpl in patterns:
        variants.append(_fill_template(tpl, ctx, r))
        if len(variants) >= count:
            break

    # pad with small mutations
    while len(variants) < count:
        base = r.choice(variants)
        # Simple mutations
        mutations = [
            base.replace("the", "The"),
            base.replace("  ", " "),
            base.replace("!", "?"),
            base.replace("?", "!"),
            base + " (shocking)",
            "The " + base.lower().replace("the ", ""),
        ]
        variants.append(r.choice(mutations))

    return [{"id": f"hook_{i+1}", "text": h} for i, h in enumerate(variants)]


def score_and_select_hooks(slug: str, brief: dict, seed: int) -> Dict[str, Any]:
    """Generate, score, and select top hooks."""
    vcfg = _read_yaml("conf/viral.yaml")
    count = vcfg.get("counts", {}).get("hooks", 8)
    hooks = generate_hooks(slug, brief, count, seed)

    results = []
    for h in hooks:
        heur = heuristics_score_hook(h["text"], brief, vcfg)
        llm = llm_score_hook(h["text"])
        final = (
            vcfg["weights"]["hooks"]["heuristics"] * heur
            + vcfg["weights"]["hooks"]["llm"] * llm
        )
        results.append(
            {**h, "score": {"heur": heur, "llm": llm, "final": round(final, 4)}}
        )

    results.sort(key=lambda x: x["score"]["final"], reverse=True)
    top2 = (
        [results[0]["id"], results[1]["id"]]
        if len(results) >= 2
        else [results[0]["id"]]
    )

    return {"variants": results, "selected": top2}
