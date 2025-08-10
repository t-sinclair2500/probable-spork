#!/usr/bin/env python3
import base64
import json
import os
import re
import hashlib

import requests
from bs4 import BeautifulSoup

# Ensure repo root on path
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, get_publish_flags, load_config, load_env, log_state, single_lock  # noqa: E402

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


def get_media_sha1(file_path):
    """Calculate SHA1 hash of media file for deduplication."""
    with open(file_path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def find_existing_media_by_hash(base, auth, file_hash, dry_run=False):
    """Check if media with this hash already exists in WordPress."""
    if dry_run:
        return None
    
    try:
        # Search for media with matching hash in meta field
        url = f"{base}/wp-json/wp/v2/media"
        params = {"per_page": 100, "meta_key": "file_sha1", "meta_value": file_hash}
        r = requests.get(url, auth=auth, params=params, timeout=30)
        if r.ok and r.json():
            return r.json()[0]["id"]
    except Exception:
        pass
    return None


def process_inline_images(html_content, base, auth, dry_run=False):
    """Parse HTML content and upload any local images, replacing paths with WordPress URLs."""
    soup = BeautifulSoup(html_content, 'html.parser')
    img_tags = soup.find_all('img')
    
    uploaded_count = 0
    for img in img_tags:
        src = img.get('src', '')
        
        # Look for local asset paths like "assets/2025-08-09_ai-tools/image.jpg"
        if src.startswith('assets/') and not src.startswith('http'):
            local_path = os.path.join(BASE, src)
            
            if os.path.exists(local_path):
                try:
                    media_id = upload_media(base, auth, local_path, dry_run)
                    if media_id and not dry_run:
                        # Get the WordPress media URL
                        media_url = get_media_url(base, auth, media_id)
                        if media_url:
                            img['src'] = media_url
                            log.info(f"Replaced {src} -> {media_url}")
                            uploaded_count += 1
                    elif dry_run:
                        img['src'] = f"https://wordpress.example.com/wp-content/uploads/dry-run-{media_id}.jpg"
                        log.info(f"DRY_RUN: Would replace {src} -> {img['src']}")
                        uploaded_count += 1
                except Exception as e:
                    log.warning(f"Failed to upload inline image {local_path}: {e}")
            else:
                log.warning(f"Local image not found: {local_path}")
    
    log.info(f"Processed {uploaded_count} inline images")
    return str(soup)


def get_media_url(base, auth, media_id):
    """Get the public URL for a WordPress media item."""
    try:
        url = f"{base}/wp-json/wp/v2/media/{media_id}"
        r = requests.get(url, auth=auth, timeout=30)
        if r.ok:
            return r.json().get("source_url")
    except Exception:
        pass
    return None


def upload_media(base, auth, file_path, dry_run=False):
    import mimetypes
    import time

    # Check for existing media by SHA1 hash first
    file_hash = get_media_sha1(file_path)
    existing_id = find_existing_media_by_hash(base, auth, file_hash, dry_run)
    if existing_id:
        log.info(f"Found existing media with SHA1 {file_hash}, reusing ID {existing_id}")
        return existing_id

    if dry_run:
        # In DRY_RUN mode, simulate upload and return fake ID
        log.info(f"DRY_RUN: Would upload {file_path} to {base}/wp-json/wp/v2/media")
        return f"dry_run_media_{hash(file_path) % 10000}"
    
    url = f"{base}/wp-json/wp/v2/media"
    mime = mimetypes.guess_type(file_path)[0] or "image/jpeg"
    
    # Exponential backoff for robust retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, mime)}
                headers = {"Content-Disposition": f'attachment; filename="{os.path.basename(file_path)}"'}
                r = requests.post(url, auth=auth, files=files, headers=headers, timeout=120)
            
            if r.status_code == 429:  # Rate limited
                wait_time = 2 ** attempt + 1
                log.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
                continue
            
            r.raise_for_status()
            media_id = r.json().get("id")
            
            # Store SHA1 hash as meta for future deduplication
            try:
                meta_url = f"{base}/wp-json/wp/v2/media/{media_id}"
                meta_data = {"meta": {"file_sha1": file_hash}}
                requests.post(meta_url, auth=auth, json=meta_data, timeout=30)
            except Exception:
                pass  # Non-critical if meta storage fails
            
            return media_id
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                log.error(f"Failed to upload {file_path} after {max_retries} attempts: {e}")
                raise
            wait_time = 2 ** attempt + 1
            log.warning(f"Upload attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
            time.sleep(wait_time)


def main(brief_data=None):
    cfg = load_config()
    env = load_env()
    bcfg = load_blog_cfg()
    
    # Log brief context if available
    if brief_data:
        log_state("blog_post_wp", "START", f"brief={brief_data.get('title', 'Untitled')}")
    else:
        log_state("blog_post_wp", "START", "no brief")
    
    # Use centralized flag governance - no CLI dry-run arg passed from blog_post_wp.py directly
    flags = get_publish_flags(cli_dry_run=False, target="blog")
    dry_run = flags["blog_dry_run"]
    
    if not flags["blog_publish_enabled"]:
        log.info("Blog publishing disabled in config (wordpress.publish_enabled=false)")
        log_state("blog_post_wp", "SKIP", "publish_disabled_in_config")
        return
    
    meta = json.load(
        open(os.path.join(BASE, "data", "cache", "post.meta.json"), "r", encoding="utf-8")
    )
    html = open(os.path.join(BASE, "data", "cache", "post.html"), "r", encoding="utf-8").read()
    
    # Apply brief settings to metadata if available
    if brief_data:
        # Enhance tags with brief keywords
        brief_keywords = brief_data.get('keywords_include', [])
        if brief_keywords and 'tags' in meta:
            existing_tags = set(meta['tags'])
            # Add brief keywords as tags if they're not already present
            for keyword in brief_keywords:
                if keyword.lower() not in [tag.lower() for tag in existing_tags]:
                    meta['tags'].append(keyword)
        
        # Enhance description with brief context if available
        brief_description = brief_data.get('description', '')
        if brief_description and 'description' in meta:
            # Combine existing description with brief context
            meta['description'] = f"{meta['description']} {brief_description}".strip()
    
    # Process inline images first - upload to WordPress and replace local paths
    try:
        base, auth = wp_auth(bcfg)
        html = process_inline_images(html, base, auth, dry_run)
    except Exception as e:
        log.warning(f"Failed to process inline images: {e}")
    
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
            mid = upload_media(base, auth, assets[0], dry_run=dry_run)
            if mid:
                payload["featured_media"] = mid
                log.info(f"{'DRY_RUN: Would set' if dry_run else 'Set'} featured image: {assets[0]} -> ID {mid}")
    except Exception as e:
        log.warning(f"Failed to upload featured image: {e}")
        pass

    # SEO lint gate
    from bin.seo_lint import lint as seo_lint

    issues = seo_lint(meta.get("title", ""), meta.get("description", ""))
    if issues:
        log_state("blog_post_wp", "FAIL", "SEO_LINT:" + ";".join(issues))
        raise SystemExit("SEO Lint failed: " + "; ".join(issues))

    if dry_run:
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
    
    # Log final result with brief context
    if brief_data:
        log_state("blog_post_wp", "OK", f"brief={brief_data.get('title', 'Untitled')} -> id={resp.get('id')}")
    else:
        log_state("blog_post_wp", "OK", f"id={resp.get('id')}")
    
    print("Posted to WordPress: id", resp.get("id"))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Post blog to WordPress")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
        except (json.JSONDecodeError, TypeError) as e:
            log.warning(f"Failed to parse brief data: {e}")
            print(f"Failed to parse brief data: {e}")
    
    with single_lock():
        main(brief)
