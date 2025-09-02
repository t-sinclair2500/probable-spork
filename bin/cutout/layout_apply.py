#!/usr/bin/env python3
"""
Layout Engine Integration Helper

Shared module for applying layout engine logic to scenes during both
storyboard generation and rendering phases.
"""

import logging

from .layout_engine import (
    apply_constraints,
    pack_text_blocks,
    poisson_points,
    thirds_grid,
)
from .sdk import SAFE_MARGINS_PX, VIDEO_H, VIDEO_W

log = logging.getLogger(__name__)


def auto_layout_scene(scene: dict, cfg: dict, seed: int) -> dict:
    """
    Auto-layout scene elements using layout engine.

    Args:
        scene: Scene dictionary with elements
        cfg: Configuration with procedural settings
        seed: Random seed for deterministic layout

    Returns:
        Scene with auto-positioned elements
    """
    W, H = VIDEO_W, VIDEO_H
    thirds = thirds_grid(W, H)

    # Split elements by type
    text_elems = [
        e
        for e in scene["elements"]
        if e["type"] in ("text", "list_step", "lower_third")
    ]
    prop_elems = [
        e
        for e in scene["elements"]
        if e["type"] in ("prop", "character", "shape", "counter")
    ]

    log.debug(
        f"[layout] Scene {scene.get('id', 'unknown')}: {len(text_elems)} text, {len(prop_elems)} props"
    )

    # 1) TEXT: find blocks lacking x,y and pack
    blocks = []
    for e in text_elems:
        if "x" not in e or "y" not in e:
            # approximate text box size if missing (use kind to size)
            w = e.get("box_w", int(W * 0.6))
            h = e.get("box_h", 160)
            blocks.append(
                {"w": w, "h": h, "id": e.get("id", e.get("text", "txt")[:12])}
            )

    if blocks:
        try:
            placed = pack_text_blocks(blocks, container=(W, H), margin=SAFE_MARGINS_PX)
            by_id = {p["id"]: p for p in placed}

            for e in text_elems:
                if "x" not in e or "y" not in e:
                    pid = e.get("id", e.get("text", "txt")[:12])
                    if pid in by_id:
                        p = by_id[pid]
                        e["x"], e["y"] = p["x"], p["y"]
                        log.debug(
                            f"[layout] id={e.get('id')} type={e['type']} pos=({e['x']},{e['y']}) method=text-pack"
                        )
        except Exception as e:
            log.warning(
                f"[layout] Text packing failed: {e}, falling back to center placement"
            )
            for e in text_elems:
                if "x" not in e or "y" not in e:
                    e["x"], e["y"] = W // 2, H // 2

    # 2) PROPS/CHARACTERS: use poisson with min spacing
    unpos = [e for e in prop_elems if "x" not in e or "y" not in e]
    if unpos:
        try:
            min_spacing = (
                cfg.get("procedural", {}).get("placement", {}).get("min_spacing_px", 64)
            )
            r = int(min_spacing)

            # Generate points in safe area
            pts = poisson_points(
                W - 2 * SAFE_MARGINS_PX, H - 2 * SAFE_MARGINS_PX, r=r, seed=seed
            )

            # Shift back into safe area
            pts = [(x + SAFE_MARGINS_PX, y + SAFE_MARGINS_PX) for (x, y) in pts]

            for e, (x, y) in zip(unpos, pts[: len(unpos)]):
                e["x"], e["y"] = int(x), int(y)
                log.debug(
                    f"[layout] id={e.get('id')} type={e['type']} pos=({e['x']},{e['y']}) method=poisson"
                )
        except Exception as e:
            log.warning(
                f"[layout] Poisson placement failed: {e}, falling back to grid placement"
            )
            # Fallback: simple grid placement
            cols = int(W // 200)
            for i, e in enumerate(unpos):
                row = i // cols
                col = i % cols
                e["x"] = SAFE_MARGINS_PX + col * 200
                e["y"] = SAFE_MARGINS_PX + row * 200

    # 3) Apply constraints (align to thirds for titles, keep inside etc.)
    items = []
    for e in scene["elements"]:
        if "x" in e and "y" in e:
            bb_w = e.get("box_w", 240)
            bb_h = e.get("box_h", 120)
            items.append(
                {
                    "id": e.get("id", "elem"),
                    "x": e["x"],
                    "y": e["y"],
                    "w": bb_w,
                    "h": bb_h,
                }
            )

    if items:
        constraints = [{"type": "keep_inside", "margin": SAFE_MARGINS_PX}]

        # Align first text or title to T1 if prefer_thirds is enabled
        layout_cfg = cfg.get("procedural", {}).get("layout", {})
        if layout_cfg.get("prefer_thirds", True) and text_elems:
            first_text = text_elems[0]
            if first_text.get("id"):
                constraints.append(
                    {"type": "align", "target": "T1", "ids": [first_text["id"]]}
                )

        try:
            items2 = apply_constraints(items, constraints)

            # Write back any adjusted positions
            for it in items2:
                for e in scene["elements"]:
                    if e.get("id") == it["id"]:
                        e["x"], e["y"] = it["x"], it["y"]
                        break
        except Exception as e:
            log.warning(f"[layout] Constraint application failed: {e}")

    return scene


def check_scene_layout_validity(scene: dict) -> bool:
    """
    Quick validation that scene layout respects safe margins.

    Args:
        scene: Scene dictionary with positioned elements

    Returns:
        True if layout is valid, False otherwise
    """
    for e in scene.get("elements", []):
        if "x" in e and "y" in e:
            x, y = e["x"], e["y"]
            w = e.get("box_w", 240)
            h = e.get("box_h", 120)

            # Check safe margins
            if (
                x < SAFE_MARGINS_PX
                or y < SAFE_MARGINS_PX
                or x + w > VIDEO_W - SAFE_MARGINS_PX
                or y + h > VIDEO_H - SAFE_MARGINS_PX
            ):
                log.warning(
                    f"[layout] Element {e.get('id')} outside safe margins: ({x},{y}) {w}x{h}"
                )
                return False

    return True
