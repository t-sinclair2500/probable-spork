from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List, Tuple

from pathlib import Path

# Ensure repository root is on sys.path (needed for `import bin.*`)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bin.utils.assets_guard import ensure_font, ensure_palette
from bin.utils.config import read_or_die

log = logging.getLogger("viral.thumbnails")


def _read_yaml(path: str) -> dict:
    """Read YAML configuration file with validation."""
    required_keys = ["counts", "weights", "heuristics", "patterns", "thumbs"]
    schema_hint = "See conf/viral.yaml.example for required structure"
    return read_or_die(path, required_keys, schema_hint)


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


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


def _fit_text(draw, text: str, font_path: str, box: Tuple[int, int, int, int]):
    """Fit text within box using binary search."""
    try:
        from PIL import ImageFont
    except ImportError:
        # Fallback if PIL not available
        return None, (0, 0)

    x, y, w, h = box
    size = 96
    min_size = 24

    while size > min_size:
        try:
            font = ImageFont.truetype(font_path, size=size)
            bbox = draw.multiline_textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if tw <= w and th <= h:
                return font, (tw, th)
        except Exception:
            pass
        size -= 4

    try:
        font = ImageFont.truetype(font_path, size=min_size)
        bbox = draw.multiline_textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        return font, (tw, th)
    except Exception:
        return None, (0, 0)


def _thumb_base(size=(1280, 720), color=(16, 16, 16)):
    """Create base thumbnail image."""
    try:
        from PIL import Image

        img = Image.new("RGB", size, color)
        return img
    except ImportError:
        return None


def generate_thumbnails(
    slug: str, title_text: str, hook_text: str
) -> List[Dict[str, Any]]:
    """Generate thumbnail variants with brand style enforcement.

    If Pillow is not installed, falls back to copying a few default
    thumbnails from `assets/thumbnails/` into the slug output folder so the
    pipeline continues to function.
    """
    try:
        from PIL import ImageDraw
    except ImportError:
        # Graceful fallback: copy a few stock thumbnails so downstream
        # pipeline steps still have artifacts to work with.
        out_dir = Path("videos") / slug / "thumbs"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Pick a small set of built-in thumbnails that exist in the repo
        stock = [
            Path("assets/thumbnails/test_icon.png"),
            Path("assets/thumbnails/gradient1.png"),
            Path("assets/thumbnails/atomic_starburst.png"),
        ]

        files: List[Dict[str, Any]] = []
        idx = 1
        for src in stock:
            if src.exists():
                dst = out_dir / f"thumb_{idx:02d}.png"
                try:
                    import shutil

                    shutil.copyfile(src, dst)
                    files.append(
                        {"id": f"thumb_{idx}", "file": f"videos/{slug}/thumbs/{dst.name}"}
                    )
                    idx += 1
                except Exception as e:
                    log.warning(f"Could not copy stock thumbnail {src}: {e}")

        if files:
            log.warning(
                "Pillow not available; using stock thumbnails as fallback (%d)",
                len(files),
            )
        else:
            log.warning("Pillow not available and no stock thumbnails found; returning none")
        return files

    cfg = _read_yaml("conf/viral.yaml")

    # Get brand style with asset guard
    palette_path = cfg.get("thumbs", {}).get("palette", "assets/brand/style.yaml")
    style = ensure_palette(palette_path)

    # Ensure font exists with asset guard
    font_path = ensure_font(
        cfg["thumbs"].get("font", "assets/brand/fonts/Inter-Bold.ttf")
    )

    out_dir = Path("videos") / slug / "thumbs"
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_pct = cfg["thumbs"].get("safe_area_pct", 0.9)
    W, H = 1280, 720
    margin = int((1 - safe_pct) / 2 * W)

    # Prepare text variants
    texts = [
        " ".join(hook_text.split()[: cfg["thumbs"].get("text_max_words", 6)]),
        title_text,
        hook_text.upper(),
    ][:3]

    files = []
    for i, txt in enumerate(texts, start=1):
        img = _thumb_base()
        if img is None:
            continue

        draw = ImageDraw.Draw(img)

        # Background bar or gradient block using palette
        bar_h = int(H * 0.36)
        bg_color = _hex_to_rgb(style.get("background_colors", ["#1a1a1a"])[0])
        draw.rectangle([0, H - bar_h, W, H], fill=bg_color)

        # Text box inside safe area
        box = (margin, H - bar_h + 40, W - 2 * margin, bar_h - 80)
        font, (tw, th) = _fit_text(draw, txt, font_path, box)

        if font is None:
            continue

        # Choose text color with contrast check vs bar
        text_colors = style.get("text_colors", ["#ffffff", "#f0f0f0", "#e0e0e0"])
        fg = _hex_to_rgb(text_colors[0])

        # Ensure contrast ratio >= 4.5:1
        if contrast_ratio(fg, bg_color) < 4.5:
            # Try other colors
            for color in text_colors[1:]:
                test_fg = _hex_to_rgb(color)
                if contrast_ratio(test_fg, bg_color) >= 4.5:
                    fg = test_fg
                    break
            else:
                # Fallback to white or black
                fg = (
                    (255, 255, 255)
                    if contrast_ratio((255, 255, 255), bg_color) >= 4.5
                    else (0, 0, 0)
                )

        # Center text in box
        text_x = box[0] + (box[2] - tw) // 2
        text_y = box[1] + (box[3] - th) // 2

        draw.multiline_text((text_x, text_y), txt, font=font, fill=fg, spacing=4)

        fname = f"thumb_{i:02d}.png"
        img.save(out_dir / fname, "PNG")
        files.append({"id": f"thumb_{i}", "file": f"videos/{slug}/thumbs/{fname}"})

    return files
