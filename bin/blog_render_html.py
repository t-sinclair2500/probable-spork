#!/usr/bin/env python3
import glob
import json
import os
import re
import time

import markdown

import sys
import os

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import sanitize_html, schema_article, get_logger
from bin.util import BASE, ensure_dirs, load_global_config, log_state, single_lock
from bin.seo_enhancer import SEOEnhancer

log = get_logger("blog_render_html")


def load_monetization_config() -> dict:
    """Load monetization configuration"""
    config_path = os.path.join(BASE, "conf", "monetization.yaml")
    if not os.path.exists(config_path):
        return {}
    
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        log.warning(f"Failed to load monetization config: {e}")
        return {}


def ensure_monetization_styles(html_content: str, monetization_config: dict) -> str:
    """Ensure monetization elements have proper styling and are preserved"""
    if not monetization_config:
        return html_content
    
    # Add any additional styling or processing for monetization elements
    # The affiliate disclosure and newsletter signup are already HTML, so markdown conversion preserves them
    
    return html_content


def load_blog_cfg():
    """Load blog configuration with SEO settings."""
    p = os.path.join(BASE, "conf", "blog.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "blog.example.yaml")
    import yaml
    return yaml.safe_load(open(p, "r", encoding="utf-8"))


def main():
    cfg = load_global_config()
    ensure_dirs(cfg)
    blog_cfg = load_blog_cfg()
    monetization_config = load_monetization_config()
    md_path = os.path.join(BASE, "data", "cache", "post.md")
    meta_path = os.path.join(BASE, "data", "cache", "post.meta.json")
    if not (os.path.exists(md_path) and os.path.exists(meta_path)):
        # Skip quietly in automated runs
        return
    md = open(md_path, "r", encoding="utf-8").read()
    html = markdown.markdown(md, extensions=["extra", "sane_lists", "toc"])
    meta = json.load(open(meta_path, "r", encoding="utf-8")) if os.path.exists(meta_path) else {}
    
    # Ensure monetization elements are properly handled
    html = ensure_monetization_styles(html, monetization_config)
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
    
    # Enhanced SEO generation
    try:
        # Initialize SEO enhancer with site configuration from blog config
        seo_config = blog_cfg.get("seo", {})
        if not seo_config:
            # Fallback configuration
            seo_config = {
                "site_name": "AI Content Pipeline",
                "site_url": "https://your-domain.com",
                "twitter_site": "@your_handle",
                "author_name": "AI Editor",
                "organization_name": "AI Content Pipeline"
            }
        
        seo_enhancer = SEOEnhancer(seo_config)
        seo_metadata = seo_enhancer.generate_seo_metadata(md, meta)
        
        # Generate enhanced HTML head
        html_head = seo_enhancer.generate_html_head(seo_metadata)
        schema_markup = seo_enhancer.generate_schema_markup(seo_metadata)
        
        # Create full HTML with enhanced SEO
        full = f"""<!DOCTYPE html>
<html lang="en">
<head>
{html_head}
<script type="application/ld+json">
{schema_markup}
</script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
article {{ margin-bottom: 2rem; }}
.reading-time {{ color: #666; font-size: 0.9em; margin-bottom: 1rem; }}
.breadcrumbs {{ margin-bottom: 1rem; font-size: 0.9em; }}
.breadcrumbs a {{ color: #007bff; text-decoration: none; }}
.breadcrumbs a:hover {{ text-decoration: underline; }}
img {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>
<nav class="breadcrumbs">
<a href="/">Home</a> &gt; <a href="/category/{seo_metadata.category.lower().replace(' ', '-')}">{seo_metadata.category}</a> &gt; {seo_metadata.title}
</nav>
<article>
<div class="reading-time">📖 {seo_metadata.reading_time_minutes} min read • {seo_metadata.word_count} words</div>
{html}
</article>
</body>
</html>"""
        
        # Log SEO enhancement metrics
        log.info(f"SEO enhanced: reading_time={seo_metadata.reading_time_minutes}min, "
                f"keywords={len(seo_metadata.keywords)}, "
                f"quality_score={seo_metadata.content_quality_score:.1f if seo_metadata.content_quality_score else 0}")
        
    except Exception as e:
        log.warning(f"SEO enhancement failed, falling back to basic HTML: {e}")
        # Fallback to original basic generation
        article_jsonld = schema_article(
            title=meta.get("title", "Post"),
            desc=meta.get("description", ""),
            url="",
            img_url="",
            author_name="Editor",
        )
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
