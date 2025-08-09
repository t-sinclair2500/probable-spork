#!/usr/bin/env python3
import base64
import json
import os

import requests

# Ensure repo root on path
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, load_env, log_state, single_lock  # noqa: E402

log = get_logger("blog_post_wp")


def load_blog_cfg():
    p = os.path.join(BASE, "conf", "blog.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "blog.example.yaml")
    import yaml

    return yaml.safe_load(open(p, "r", encoding="utf-8"))


def wp_auth(bcfg):
    import requests

    return (
        bcfg["wordpress"]["base_url"].rstrip("/"),
        requests.auth.HTTPBasicAuth(
            bcfg["wordpress"]["api_user"], bcfg["wordpress"]["api_app_password"]
        ),
    )


def ensure_category(base, auth, name):
    import requests

    r = requests.get(f"{base}/wp-json/wp/v2/categories?search={name}", auth=auth, timeout=30)
    if r.ok and r.json():
        return r.json()[0]["id"]
    r = requests.post(
        f"{base}/wp-json/wp/v2/categories", auth=auth, json={"name": name}, timeout=30
    )
    r.raise_for_status()
    return r.json()["id"]


def ensure_tag(base, auth, name):
    import requests

    r = requests.get(f"{base}/wp-json/wp/v2/tags?search={name}", auth=auth, timeout=30)
    if r.ok and r.json():
        return r.json()[0]["id"]
    r = requests.post(f"{base}/wp-json/wp/v2/tags", auth=auth, json={"name": name}, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def recent_posts(base, auth, n=10):
    import requests

    r = requests.get(
        f"{base}/wp-json/wp/v2/posts?per_page={n}&_fields=link,title", auth=auth, timeout=30
    )
    if not r.ok:
        return []
    return r.json()


def find_assets_for_slug(slug: str):
    # Try to locate assets folder named like <date>_<slug>
    import glob

    pattern = os.path.join(BASE, "assets", f"*_{slug}")
    folders = sorted(glob.glob(pattern), reverse=True)
    if not folders:
        return []
    adir = folders[0]
    files = []
    for f in sorted(os.listdir(adir)):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            files.append(os.path.join(adir, f))
    return files


def upload_media(base, auth, file_path):
    import mimetypes

    url = f"{base}/wp-json/wp/v2/media"
    mime = mimetypes.guess_type(file_path)[0] or "image/jpeg"
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, mime)}
        r = requests.post(url, auth=auth, files=files, timeout=120)
    r.raise_for_status()
    return r.json().get("id")


def main():
    cfg = load_config()
    env = load_env()
    bcfg = load_blog_cfg()
    meta = json.load(
        open(os.path.join(BASE, "data", "cache", "post.meta.json"), "r", encoding="utf-8")
    )
    html = open(os.path.join(BASE, "data", "cache", "post.html"), "r", encoding="utf-8").read()
    # Internal links: append a resources block with last posts
    try:
        base, auth = wp_auth(bcfg)
        posts = recent_posts(base, auth)
        if posts:
            links = "".join(
                [f'<li><a href="{p["link"]}">{p["title"]["rendered"]}</a></li>' for p in posts]
            )
            html += f"<h2>Further Reading</h2><ul>{links}</ul>"
    except Exception:
        pass

    payload = {
        "title": meta["title"],
        "status": bcfg["wordpress"]["default_status"],
        "content": html,
        "excerpt": meta.get("description", ""),
        "slug": meta["slug"],
    }
    # Taxonomy sync
    try:
        base, auth = wp_auth(bcfg)
        cat_id = ensure_category(base, auth, bcfg["wordpress"]["default_category"])
        tag_ids = []
        for t in meta.get("tags", []):
            try:
                tag_ids.append(ensure_tag(base, auth, t))
            except Exception:
                pass
        payload["categories"] = [cat_id]
        if tag_ids:
            payload["tags"] = tag_ids
    except Exception:
        pass

    # Attempt to upload a featured image from assets if present
    try:
        base, auth = wp_auth(bcfg)
        assets = find_assets_for_slug(meta.get("slug", ""))
        if assets:
            mid = upload_media(base, auth, assets[0])
            if mid:
                payload["featured_media"] = mid
    except Exception:
        pass

    # SEO lint gate
    from bin.seo_lint import lint as seo_lint

    issues = seo_lint(meta.get("title", ""), meta.get("description", ""))
    if issues:
        log_state("blog_post_wp", "FAIL", "SEO_LINT:" + ";".join(issues))
        raise SystemExit("SEO Lint failed: " + "; ".join(issues))

    # DRY_RUN via env/config
    dry_env = (env.get("BLOG_DRY_RUN") or "").lower() in ("1", "true", "yes")
    dry_cfg = True
    try:
        dry_cfg = True  # default true unless explicitly disabled elsewhere
    except Exception:
        dry_cfg = True
    if dry_env or dry_cfg:
        log_state("blog_post_wp", "DRY_RUN", json.dumps(payload)[:200])
        print("DRY RUN: would post to WordPress:", json.dumps(payload, indent=2)[:200] + "...")
        return

    # Real POST (requires valid base_url, user, app password)
    base = bcfg["wordpress"]["base_url"].rstrip("/")
    user = bcfg["wordpress"]["api_user"]
    app_pw = bcfg["wordpress"]["api_app_password"]
    auth = requests.auth.HTTPBasicAuth(user, app_pw)
    url = f"{base}/wp-json/wp/v2/posts"
    r = requests.post(url, auth=auth, json=payload, timeout=60)
    if r.status_code >= 300:
        log_state("blog_post_wp", "FAIL", r.text[:200])
        raise SystemExit(f"WordPress POST failed: {r.status_code} {r.text[:200]}")
    resp = r.json()
    log_state("blog_post_wp", "OK", f"id={resp.get('id')}")
    print("Posted to WordPress: id", resp.get("id"))


if __name__ == "__main__":
    with single_lock():
        main()
