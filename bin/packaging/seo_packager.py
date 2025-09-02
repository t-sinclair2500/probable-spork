from __future__ import annotations

import argparse
import json
import re
from typing import List, Tuple
from urllib.parse import urlencode

from pathlib import Path

from bin.utils.config import read_or_die


def _load_meta(slug: str) -> dict:
    p = Path("videos") / f"{slug}.metadata.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"slug": slug}


def _load_references(slug: str) -> List[dict]:
    p = Path("data") / slug / "references.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _domain(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.replace("www.", "")


def _human_bullets(scene_map: List[dict], max_items: int = 6) -> str:
    items = []
    for sc in scene_map[:max_items]:
        t = sc.get("title") or (sc.get("summary") or "")
        if t:
            items.append(f"• {t}")
    return "\n".join(items) or ""


def _format_chapters(scene_map: List[dict], ch_cfg: dict) -> List[Tuple[str, str]]:
    def fmt(sec: float) -> str:
        m = int(sec) // 60
        s = int(sec) % 60
        return f"{m:02d}:{s:02d}"

    chapters = []
    t0 = 0.0
    for sc in scene_map:
        start = float(sc.get("start_s", t0))
        if start - t0 < ch_cfg.get("merge_below_s", 6):
            continue
        title = sc.get("title") or (sc.get("summary") or f"Part {len(chapters)+1}")
        chapters.append((fmt(start), title))
        t0 = start
    if chapters and chapters[0][0] > "00:{:02d}".format(
        ch_cfg.get("max_first_chapter_start_s", 5)
    ):
        chapters[0] = ("00:00", chapters[0][1])
    return chapters


def _keywords(meta: dict, brief: dict) -> List[str]:
    out = []
    out += brief.get("keywords", []) or []
    title = (meta.get("title") or "") + " " + (brief.get("title") or "")
    tokens = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in title.split()]
    tokens = [t for t in tokens if len(t) > 2]
    out += tokens
    return list(dict.fromkeys(out))


def _ensure_coverage(text: str, keywords: List[str]) -> str:
    # Ensure top 5 keywords appear at least once; append if missing.
    miss = [k for k in keywords[:5] if k.lower() not in text.lower()]
    if miss:
        text += "\n\nKeywords: " + ", ".join(miss)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    args = ap.parse_args()
    slug = args.slug

    meta = _load_meta(slug)
    brief_path = Path(f"conf/briefs/{slug}.yaml")
    brief = _read_yaml(str(brief_path)) if brief_path.exists() else {}

    seo_cfg = read_or_die(
        "conf/seo.yaml",
        ["templates", "tags", "chapters", "cta", "end_screen"],
        "See conf/seo.yaml.example for required structure",
    )
    monet = (
        _read_yaml("conf/monetization.yaml")
        if Path("conf/monetization.yaml").exists()
        else {}
    )

    # Build pieces
    scene_map = meta.get("scene_map", [])
    hook_line = (
        (meta.get("viral", {}).get("variants", {}).get("hooks", [{}])[0].get("text"))
        or meta.get("title")
        or brief.get("title")
        or slug
    )
    bullets = _human_bullets(scene_map)
    refs = _load_references(slug)
    cites = sorted({_domain(r.get("url", "")) for r in refs if r.get("url")})[:5]
    citations = (
        "\n".join(f"• {d}" for d in cites) or "• (local research / original analysis)"
    )

    cta_text = seo_cfg.get("cta", {}).get("text", "subscribe for weekly breakdowns")
    disclosure = monet.get("disclosure", "This video may contain affiliate links.")

    # Links & UTM
    primary_link = (
        monet.get("primary_link", "https://example.com/")
        + "?"
        + urlencode(
            {"utm_source": "youtube", "utm_medium": "description", "utm_campaign": slug}
        )
    )
    links = "\n".join([primary_link] + monet.get("extra_links", []))

    # Description template
    summary = meta.get("description") or brief.get("summary", "")
    desc_tpl = seo_cfg["templates"]["description"]
    description = desc_tpl.format(
        hook_line=hook_line,
        summary=summary,
        bullets=bullets,
        citations=citations,
        cta=cta_text,
        disclosure=disclosure,
        links=links,
    )

    # Ensure keyword coverage
    keys = _keywords(meta, brief)
    description = _ensure_coverage(description, keys)

    # Tags
    tags = list(
        dict.fromkeys(
            keys
            + seo_cfg.get("tags", {}).get("brand", [])
            + seo_cfg.get("tags", {}).get("extra", [])
        )
    )
    tags = tags[: seo_cfg.get("tags", {}).get("max_tags", 20)]

    # Chapters
    chapters = _format_chapters(scene_map, seo_cfg.get("chapters", {}))

    # Pinned comment
    next_title = (
        seo_cfg.get("cta", {})
        .get("next_video_title", "Next up")
        .format(topic=brief.get("title", slug))
    )
    next_link = (
        seo_cfg.get("cta", {})
        .get("next_video_link", "https://example.com/next")
        .format(slug=slug)
    )
    pinned_tpl = seo_cfg["templates"]["pinned_comment"]
    pinned = pinned_tpl.format(
        cta=cta_text,
        primary_link=primary_link,
        next_video_title=next_title,
        next_video_link=next_link,
        disclosure=disclosure,
    )

    # Persist
    meta.setdefault("seo", {})["description"] = description
    meta["seo"]["tags"] = tags
    meta["seo"]["chapters"] = chapters
    meta["seo"]["pinned_comment"] = pinned
    (Path("videos") / f"{slug}.metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"[seo] description/tags/chapters/pinned updated for {slug}")


if __name__ == "__main__":
    main()
