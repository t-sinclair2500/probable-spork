from __future__ import annotations

import argparse
import json
import logging
import subprocess
import tempfile
from typing import List, Tuple

from pathlib import Path

from bin.utils.assets_guard import ensure_font, ensure_overlay
from bin.utils.captions import segment_srt, srt_to_ass
from bin.utils.config import read_or_die

log = logging.getLogger("viral.shorts")

def _load_meta(slug:str)->dict:
    p = Path("videos")/f"{slug}.metadata.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def _pick_segments(slug:str, cfg:dict)->List[Tuple[float,float,str]]:
    """Return list of (start_s, end_s, rationale). Prefer viral.selected hooks, else early high-curiosity scenes."""
    meta=_load_meta(slug)
    scenes = meta.get("scene_map", [])
    picks: List[Tuple[float,float,str]] = []
    max_clips = int(cfg["counts"]["max_clips"])
    mn, mx = int(cfg["counts"]["min_clip_s"]), int(cfg["counts"]["max_clip_s"])
    # 1) If we have viral.selected.hook_ids map them to scenes (by scene ids or first scenes)
    viral = (meta.get("viral") or {})
    selected_hooks = (viral.get("selected") or {}).get("hook_ids") or []
    used = set()
    for h in selected_hooks:
        # choose earliest scene with speech containing question/number
        for sc in scenes:
            if sc.get("id") in used: continue
            txt = (sc.get("speech","") or "") + " " + (sc.get("on_screen_text","") or "")
            if any(ch.isdigit() for ch in txt) or "?" in txt or "why " in txt.lower() or "how " in txt.lower():
                dur = float(sc.get("actual_duration_s", sc.get("duration_s", 0))) or 0
                if dur < 2: continue
                start = float(sc.get("start_s", 0.0))
                end = start + min(max(dur, mn), mx)
                used.add(sc.get("id"))
                picks.append((start, end, f"hook:{h} scene:{sc.get('id')}"))
                break
        if len(picks) >= max_clips: break
    # 2) Fill with first scenes until target count
    for sc in scenes:
        if len(picks) >= max_clips: break
        if sc.get("id") in used: continue
        dur = float(sc.get("actual_duration_s", sc.get("duration_s", 0))) or 0
        if dur < mn: dur = mn
        if dur > mx: dur = mx
        start = float(sc.get("start_s", 0.0))
        end = start + dur
        picks.append((start, end, f"early_scene:{sc.get('id')}"))
    return picks[:max_clips]

def _compute_crop(w:int, h:int, tw:int, th:int, anchor:str)->Tuple[int,int,int,int]:
    """Return x,y,cw,ch for crop box to fit 9:16; if source is 16:9 (1920x1080), scale and crop center."""
    # scale to height, then crop width
    # ffmpeg will handle scale; here only choose crop window for portrait
    cw, ch = int(h * tw / th), h
    if cw > w: cw = w
    if anchor == "right_rule_of_thirds":
        x = min(w - cw, int(w * (2/3)) - cw//2)
    elif anchor == "left_rule_of_thirds":
        x = max(0, int(w * (1/3)) - cw//2)
    else:
        x = (w - cw)//2
    y = (h - ch)//2
    return x, y, cw, ch

def _ffprobe_wh(path: Path)->Tuple[int,int]:
    out = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","csv=s=x:p=0", str(path)], capture_output=True, text=True, check=True).stdout.strip()
    w,h = out.split("x")
    return int(w), int(h)

def _build_filter_complex(src: Path, ass_path: Path, logo: Path, subscribe: Path, crop_cfg: dict, audio_cfg: dict)->str:
    # Probe source size
    w,h = _ffprobe_wh(src)
    tw,th = int(crop_cfg["target_w"]), int(crop_cfg["target_h"])
    x,y,cw,ch = _compute_crop(w,h,tw,th, crop_cfg.get("anchor","center"))
    # Overlay static positions
    lg_pos = crop_cfg.get("logo_pos", ["right","top"])
    sb_pos = crop_cfg.get("subscribe_pos", ["right","bottom"])
    # margins
    m = 40
    lgx = f"main_w-{m}-overlay_w" if lg_pos[0]=="right" else f"{m}"
    lgy = f"{m}" if lg_pos[1]=="top" else f"main_h-{m}-overlay_h"
    sbx = f"main_w-{m}-overlay_w" if sb_pos[0]=="right" else f"{m}"
    sby = f"main_h-{m}-overlay_h" if sb_pos[1]=="bottom" else f"{m}"
    # filter chain
    vf = (
      f"[0:v]scale={w}:{h},crop={cw}:{ch}:{x}:{y},scale={tw}:{th}:flags=lanczos"
      f"[v0];[v0][2:v]overlay={lgx}:{lgy}[v1];[v1][3:v]overlay={sbx}:{sby}[v2];"
      f"[v2]subtitles='{ass_path.as_posix().replace(':','\\:')}'"
    )
    # Audio normalization
    af = f"loudnorm=I={audio_cfg['lufs_target']}:TP={audio_cfg['truepeak_max_db']}:LRA=11:print_format=summary"
    return vf, af

def _write_meta_stub(out_mp4: Path, slug: str, n: int, rationale: str, brief: dict, keywords: List[str]):
    tags = list({*(brief.get("keywords") or []), *keywords})
    meta = {
        "title": f"{brief.get('title', slug)} — Cut {n}",
        "description": f"Hook cut from {slug}. {rationale}\n\nMore: {brief.get('cta','Subscribe for more insights.')}",
        "tags": tags[:20],
        "hashtags": [f"#{k.replace(' ','')}" for k in tags[:5]],
        "aspect": "9:16",
        "source_slug": slug
    }
    out_json = out_mp4.with_suffix(".meta.json")
    out_json.write_text(json.dumps(meta, indent=2), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    args = ap.parse_args()

    slug = args.slug
    cfg = read_or_die("conf/shorts.yaml", 
                     ["counts", "selection", "crop", "captions", "overlays", "audio", "encoding", "filename"],
                     "See conf/shorts.yaml.example for required structure")
    dst = Path("videos")/slug/"shorts"
    dst.mkdir(parents=True, exist_ok=True)

    src = Path("videos")/f"{slug}_cc.mp4"
    srt = Path("voiceovers")/f"{slug}.srt"
    brief = _read_yaml(f"conf/briefs/{slug}.yaml") if Path(f"conf/briefs/{slug}.yaml").exists() else {}

    picks = _pick_segments(slug, cfg)
    tw,th = cfg["crop"]["target_w"], cfg["crop"]["target_h"]
    font_path = ensure_font(cfg["captions"]["font"])
    # Approx caption font size
    font_px = int(th * (cfg["captions"]["font_size_pct"]/100.0))
    bottom_margin_px = int(th * (cfg["captions"]["bottom_margin_pct"]/100.0))

    logo = Path(ensure_overlay(cfg["overlays"]["logo"]))
    sub  = Path(ensure_overlay(cfg["overlays"]["subscribe"]))

    # derive keywords for filename
    meta = _load_meta(slug)
    base_kw = (meta.get("viral", {}).get("variants", {}).get("titles", [{}])[0].get("text","") + " " + brief.get("title","")).split()
    base_kw = [k.lower().strip(".,!?:;") for k in base_kw if len(k)>3]
    base_kw = list(dict.fromkeys(base_kw))[: cfg["filename"]["max_keywords"]]

    for i,(start,end,why) in enumerate(picks, start=1):
        # prepare captions
        srt_text = segment_srt(srt, start, end)
        with tempfile.NamedTemporaryFile("w+", suffix=".ass", delete=False, encoding="utf-8") as tf:
            ass_text = srt_to_ass(srt_text, font=font_path, font_size_px=font_px,
                                  fill_rgba=cfg["captions"]["fill_rgba"],
                                  stroke_rgba=cfg["captions"]["stroke_rgba"],
                                  bottom_margin_px=bottom_margin_px)
            tf.write(ass_text)
            ass_path = Path(tf.name)

        vf, af = _build_filter_complex(src, ass_path, logo, sub, {**cfg["crop"], **cfg["overlays"]}, cfg["audio"])
        kw_join = "-".join(base_kw) if base_kw else "clip"
        fname = cfg["filename"]["pattern"].format(slug=slug, n=i, keywords=kw_join)
        out = dst / fname

        cmd = [
          "ffmpeg","-y","-hide_banner","-ss", f"{max(0.0, start - cfg['selection']['leadin_s'])}",
          "-to", f"{end + cfg['selection']['leadout_s']}",
          "-i", str(src),
          "-loop","1","-t","0.1","-i", str(logo),
          "-loop","1","-t","0.1","-i", str(sub),
          "-filter_complex", vf,
          "-map","[v2]","-map","0:a:0",
          "-c:v","libx264","-crf", str(cfg["encoding"]["crf"]), "-preset", cfg["encoding"]["preset"], "-pix_fmt", cfg["encoding"]["pix_fmt"],
          "-vf", "fps=30",
          "-c:a","aac","-b:a","320k","-af", af,
          str(out)
        ]
        subprocess.run(cmd, check=True)
        _write_meta_stub(out, slug, i, why, brief, base_kw)

    # write variants index to main metadata
    main_meta_p = Path("videos")/f"{slug}.metadata.json"
    if main_meta_p.exists():
        main_meta = json.loads(main_meta_p.read_text(encoding="utf-8"))
        shorts = [{"file": f"videos/{slug}/shorts/"+x.name} for x in sorted(dst.glob("*.mp4"))]
        main_meta.setdefault("viral", {}).setdefault("variants", {})["shorts"] = shorts
        main_meta_p.write_text(json.dumps(main_meta, indent=2), encoding="utf-8")
    print(f"[shorts] generated {len(list(dst.glob('*.mp4')))} clips for {slug}")

if __name__ == "__main__":
    main()
