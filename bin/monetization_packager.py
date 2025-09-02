# bin/monetization_packager.py
from __future__ import annotations

import json
from typing import Any, Dict

from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None


def _load_yaml(path: str) -> Dict[str, Any]:
    if not yaml:
        raise RuntimeError("PyYAML required for monetization packager.")
    p = Path(path)
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _with_utm(url: str, utm: Dict[str, str], slug: str) -> str:
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query))
    q.update(
        {
            "utm_source": utm.get("source", "youtube"),
            "utm_medium": utm.get("medium", "video"),
            "utm_campaign": f"{utm.get('campaign_prefix','vid')}_{slug}",
        }
    )
    new_query = urlencode(q)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )


def build_monetization_pack(slug: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _load_yaml("conf/monetization.yaml")
    utm = cfg.get("utm", {})
    max_links = int(cfg.get("max_affiliate_links", 5))
    links = cfg.get("links", [])
    out_links = []
    for item in links[:max_links]:
        url = _with_utm(item.get("url", ""), utm, slug)
        out_links.append({"label": item.get("label", "link"), "url": url})
    pack = {
        "slug": slug,
        "title": metadata.get("title"),
        "description": metadata.get("description", ""),
        "chapters": metadata.get("chapters", []),
        "hashtags": metadata.get("hashtags", []),
        "disclosure": cfg.get("disclosure", ""),
        "links": out_links,
    }
    return pack


def main(slug: str):
    vmeta = Path("videos") / f"{slug}.metadata.json"
    smeta = Path("scripts") / f"{slug}.metadata.json"
    meta_path = smeta if smeta.exists() else vmeta
    if not meta_path.exists():
        raise SystemExit(f"No metadata for slug: {slug}")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    pack = build_monetization_pack(slug, metadata)
    out = Path("videos") / f"{slug}.monetization.json"
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python bin/monetization_packager.py <slug>")
    main(sys.argv[1])
