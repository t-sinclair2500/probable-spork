from __future__ import annotations

import json
from typing import Tuple

from pathlib import Path

from bin.utils.config import _read_yaml


def _safe_box(w: int, h: int, pct: float) -> Tuple[int, int, int, int]:
    mw = int(w * (1 - pct) / 2)
    mh = int(h * (1 - pct) / 2)
    return mw, mh, w - mw, h - mh


def render_end_screen(slug: str):
    cfg = _read_yaml("conf/seo.yaml")["end_screen"]
    w, h = int(cfg["width"]), int(cfg["height"])
    # For now, create a simple placeholder since we don't have PIL available
    # In production, this would use PIL to create the actual image
    out_dir = Path("assets") / "generated" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_img = out_dir / "end_screen_16x9.png"

    # Create a simple placeholder file
    out_img.write_text("Placeholder end screen image", encoding="utf-8")
    return out_img


def render_cta_overlay_mov(slug: str):
    cfg = _read_yaml("conf/seo.yaml")["end_screen"]
    w, h = int(cfg["width"]), int(cfg["height"])
    overlay_png = render_end_screen(slug)
    # Turn a static PNG into N-second MOV with alpha
    out_dir = Path("assets") / "generated" / slug
    out_mov = out_dir / "cta_16x9.mov"
    sec = int(cfg.get("overlay_seconds", 10))

    # For now, create a placeholder since we need actual image files
    # In production, this would use ffmpeg to create the MOV
    out_mov.write_text("Placeholder CTA overlay MOV", encoding="utf-8")
    return out_mov


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    args = ap.parse_args()
    img = render_end_screen(args.slug)
    mov = render_cta_overlay_mov(args.slug)
    print(
        json.dumps(
            {"end_screen": img.as_posix(), "cta_overlay": mov.as_posix()}, indent=2
        )
    )


if __name__ == "__main__":
    main()
