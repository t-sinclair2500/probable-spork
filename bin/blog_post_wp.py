#!/usr/bin/env python3
import base64
import json
import os

import requests

from bin.util import BASE, ensure_dirs, load_global_config, log_state, single_lock

# DRY_RUN default True for safety. Set to False when ready to post.
DRY_RUN = True  # set to False to actually post


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


def main():
    cfg = load_global_config()
    ensure_dirs(cfg)
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

    # SEO lint gate
    from bin.seo_lint import lint as seo_lint

    issues = seo_lint(meta.get("title", ""), meta.get("description", ""))
    if issues:
        log_state("blog_post_wp", "FAIL", "SEO_LINT:" + ";".join(issues))
        raise SystemExit("SEO Lint failed: " + "; ".join(issues))

    if DRY_RUN:
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
