from __future__ import annotations

from pathlib import Path


def segment_srt(srt_path: Path, start_s: float, end_s: float) -> str:
    """Return a temp SRT string for [start_s, end_s], time-shifted to 0."""
    import io
    import re

    if not srt_path.exists():
        return ""
    text = srt_path.read_text(encoding="utf-8", errors="ignore")
    # naive parse; supports HH:MM:SS,mmm
    out, idx = io.StringIO(), 1
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        if len(lines) < 2:
            continue
        tline = lines[1] if "-->" in lines[1] else lines[0]
        m = re.search(r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)", tline)
        if not m:
            continue
        sh = (
            int(m.group(1)) * 3600
            + int(m.group(2)) * 60
            + int(m.group(3))
            + int(m.group(4)) / 1000.0
        )
        eh = (
            int(m.group(5)) * 3600
            + int(m.group(6)) * 60
            + int(m.group(7))
            + int(m.group(8)) / 1000.0
        )
        if eh < start_s or sh > end_s:
            continue
        # clamp and shift
        ns = max(sh, start_s) - start_s
        ne = min(eh, end_s) - start_s

        def fmt(sec: float) -> str:
            ms = int(round((sec - int(sec)) * 1000))
            ss = int(sec) % 60
            mm = (int(sec) // 60) % 60
            hh = int(sec) // 3600
            return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"

        out.write(f"{idx}\n{fmt(ns)} --> {fmt(ne)}\n")
        # payload content is last line(s)
        payload = "\n".join(lines[2:]) if "-->" in lines[1] else "\n".join(lines[1:])
        out.write(payload.strip() + "\n\n")
        idx += 1
    return out.getvalue()


def srt_to_ass(
    srt_text: str,
    font: str,
    font_size_px: int,
    fill_rgba,
    stroke_rgba,
    bottom_margin_px: int,
) -> str:
    """Create an ASS subtitle with styling."""
    # Basic ASS header + single default style
    fill = "&H{b:02X}{g:02X}{r:02X}&".format(
        r=fill_rgba[0], g=fill_rgba[1], b=fill_rgba[2]
    )
    outline = "&H{b:02X}{g:02X}{r:02X}&".format(
        r=stroke_rgba[0], g=stroke_rgba[1], b=stroke_rgba[2]
    )
    hdr = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\n"
        f"Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
        f"Style: Default,{font},{font_size_px},{fill},{outline},1,3,0,2,40,40,{bottom_margin_px}\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Text\n"
    )
    # Convert SRT inline into ASS Events
    import re

    body = []
    for blk in srt_text.strip().split("\n\n"):
        lines = blk.splitlines()
        if len(lines) < 2:
            continue
        tline = next((l for l in lines if "-->" in l), "")
        m = re.search(r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)", tline)
        if not m:
            continue

        def to_ass(hh, mm, ss, ms):
            return f"{int(hh):01d}:{int(mm):02d}:{int(ss):02d}.{int(ms):02d}"

        start = to_ass(m.group(1), m.group(2), m.group(3), int(int(m.group(4)) / 10))
        end = to_ass(m.group(5), m.group(6), m.group(7), int(int(m.group(8)) / 10))
        text = "\\N".join(l for l in lines if l and "-->" not in l and not l.isdigit())
        body.append(f"Dialogue: 0,{start},{end},Default,{text}")
    return hdr + "\n".join(body) + "\n"
