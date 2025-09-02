import json
from typing import Tuple

from pathlib import Path


def _luminance(rgb: Tuple[int, int, int]) -> float:
    """Calculate relative luminance from RGB values."""

    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = map(ch, rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    """Calculate contrast ratio between two colors."""
    L1, L2 = _luminance(c1), _luminance(c2)
    hi, lo = max(L1, L2), min(L1, L2)
    return (hi + 0.05) / (lo + 0.05)


def load_scenescript(slug: str) -> dict:
    """Load scenescript data."""
    p = Path("scenescripts") / f"{slug}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def evaluate_contrast_and_safe_areas(slug: str, thresholds: dict) -> dict:
    """Evaluate text contrast and safe area compliance."""
    ss = load_scenescript(slug)
    issues = []
    min_ratio = float(thresholds.get("contrast_min_ratio", 4.5))
    safe_pct = float(thresholds.get("safe_area_pct", 0.9))
    failures = 0
    checks = 0

    for scene in ss.get("scenes", []):
        for el in scene.get("elements", []):
            if el.get("type") == "text":
                # expects el["color"] = "#RRGGBB" and el["bbox"] = [x,y,w,h] normalized 0..1
                color = el.get("color", "#FFFFFF")
                try:
                    rgb = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
                    bg = (0, 0, 0)  # fallback; improve by sampling frame later
                    ratio = contrast_ratio(rgb, bg)
                    checks += 1
                    if ratio < min_ratio:
                        failures += 1
                        issues.append(
                            f"Low contrast {ratio:.2f} in scene {scene.get('id')}"
                        )

                    # safe area check
                    x, y, w, h = el.get("bbox", [0.1, 0.1, 0.8, 0.2])
                    if (
                        x < (1 - safe_pct) / 2
                        or y < (1 - safe_pct) / 2
                        or (x + w) > (1 + safe_pct) / 2
                        or (y + h) > (1 + safe_pct) / 2
                    ):
                        failures += 1
                        issues.append(
                            f"Text outside safe area in scene {scene.get('id')}"
                        )
                except (ValueError, IndexError):
                    failures += 1
                    issues.append(f"Invalid color format in scene {scene.get('id')}")

    return {"contrast_checks": checks, "contrast_failures": failures, "issues": issues}


def evaluate_scene_durations(slug: str, thresholds: dict) -> dict:
    """Evaluate scene duration compliance with planned timing."""
    meta_p = Path("videos") / f"{slug}.metadata.json"
    if not meta_p.exists():
        return {"checked": False}

    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        tol = float(thresholds.get("scene_duration_tolerance_pct", 3.0))
        failures = 0
        checks = 0

        for sc in meta.get("scene_map", []):
            plan = float(sc.get("planned_duration_s", 0) or 0)
            actual = float(sc.get("actual_duration_s", 0) or 0)
            if plan <= 0 or actual <= 0:
                continue
            pct = abs(actual - plan) / plan * 100.0
            checks += 1
            if pct > tol:
                failures += 1

        return {"duration_checks": checks, "duration_failures": failures}
    except Exception:
        return {"checked": False, "error": "Failed to parse metadata"}
