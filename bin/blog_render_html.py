#!/usr/bin/env python3
import glob
import json
import os
import re
import time

import markdown

from bin.core import sanitize_html, schema_article
from bin.util import BASE, ensure_dirs, load_global_config, log_state, single_lock


def main():
    cfg = load_global_config()
    ensure_dirs(cfg)
    md_path = os.path.join(BASE, "data", "cache", "post.md")
    meta_path = os.path.join(BASE, "data", "cache", "post.meta.json")
    if not (os.path.exists(md_path) and os.path.exists(meta_path)):
        print("No draft to render")
        return
    md = open(md_path, "r", encoding="utf-8").read()
    html = markdown.markdown(md, extensions=["extra", "sane_lists", "toc"])
    meta = json.load(open(meta_path, "r", encoding="utf-8")) if os.path.exists(meta_path) else {}
    # Optional attribution block if licenses require it and assets license file exists
    try:
        cfg = load_global_config()
        need_attr = bool(cfg.get("licenses", {}).get("require_attribution", True))
    except Exception:
        need_attr = True
    attribution_html = ""
    if need_attr and meta.get("slug"):
        # Find latest assets directory matching *_<slug>
        pattern = os.path.join(BASE, "assets", f"*_{meta['slug']}")
        candidates = sorted(glob.glob(pattern), reverse=True)
        if candidates:
            lic_path = os.path.join(candidates[0], "license.json")
            if os.path.exists(lic_path):
                try:
                    lic = json.load(open(lic_path, "r", encoding="utf-8"))
                    items = lic.get("items", [])
                    if items:
                        rows = []
                        for it in items[:20]:
                            prov = it.get("provider", "")
                            url = it.get("url", "")
                            who = it.get("user") or it.get("photographer") or ""
                            rows.append(
                                f'<li>{prov}: <a href="{url}" rel="nofollow">{who or url}</a></li>'
                            )
                        attribution_html = "<h3>Attributions</h3><ul>" + "".join(rows) + "</ul>"
                except Exception:
                    pass
    if attribution_html:
        html = html + "\n" + attribution_html
    # Sanitize HTML output
    html = sanitize_html(html)
    # Schema.org Article JSON-LD
    article_jsonld = schema_article(
        title=meta.get("title", "Post"),
        desc=meta.get("description", ""),
        url="",
        img_url="",
        author_name="Editor",
    )
    # Minimal wrapper with JSON-LD
    full = f"""<!doctype html><html><head>
<meta charset="utf-8">
<title>{meta.get('title','Post')}</title>
<script type="application/ld+json">{article_jsonld}</script>
</head><body>{html}</body></html>"""
    out_html = os.path.join(BASE, "data", "cache", "post.html")
    open(out_html, "w", encoding="utf-8").write(full)
    log_state("blog_render_html", "OK", os.path.basename(out_html))
    print(f"Wrote {out_html} (HTML with schema.org Article + attribution if present).")


if __name__ == "__main__":
    with single_lock():
        main()
