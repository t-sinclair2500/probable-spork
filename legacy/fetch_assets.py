#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import random
import requests
import shutil
from PIL import Image, ImageDraw, ImageFont
import argparse

# Ensure repo root is on sys.path for `import bin.core`
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import (  # noqa: E402
    BASE,
    get_logger,
    guard_system,
    load_config,
    load_env,
    log_state,
    sha1_file,
    single_lock,
    slugify,
)
from bin.asset_quality import AssetQualityAnalyzer, QualityMetrics  # noqa: E402


log = get_logger("fetch_assets")


@dataclass
class ProviderResult:
    provider: str
    url: str
    file_path: str
    license: str
    author: str
    quality_metrics: Optional[QualityMetrics] = None
    provider_metadata: Optional[Dict[str, Any]] = None


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def target_assets_dir(script_base: str) -> str:
    # scripts/2025-08-08_ai-tools.txt -> assets/2025-08-08_ai-tools
    base_name = os.path.basename(script_base).replace(".txt", "")
    return os.path.join(BASE, "assets", base_name)


def latest_script() -> Optional[str]:
    sdir = os.path.join(BASE, "scripts")
    files = [f for f in os.listdir(sdir) if f.endswith(".txt")]
    if not files:
        return None
    files.sort(reverse=True)
    return os.path.join(sdir, files[0])


def read_script(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_broll_queries(script_text: str, brief: dict = None) -> List[str]:
    # Find [B-ROLL: ...] markers
    queries = re.findall(r"\[B-ROLL:\s*([^\]]+)\]", script_text, flags=re.I)
    # Clean and dedupe while preserving order
    seen = set()
    cleaned: List[str] = []
    for q in queries:
        qn = re.sub(r"\s+", " ", q).strip().lower()
        if qn and qn not in seen:
            seen.add(qn)
            cleaned.append(qn)
    
    # Filter queries based on brief if available
    if brief:
        cleaned = filter_queries_by_brief(cleaned, brief)
    
    return cleaned


def filter_queries_by_brief(queries: List[str], brief: dict) -> List[str]:
    """Filter B-roll queries based on brief keywords_include and keywords_exclude"""
    if not brief:
        return queries
    
    include_keywords = brief.get('keywords_include', [])
    exclude_keywords = brief.get('keywords_exclude', [])
    
    filtered_queries = []
    
    for query in queries:
        query_lower = query.lower()
        
        # Check if query contains excluded terms
        if exclude_keywords and any(exclude_term.lower() in query_lower for exclude_term in exclude_keywords):
            log.info(f"Filtered out B-roll query '{query}' due to excluded keywords")
            continue
        
        # If include keywords are specified, prioritize queries that contain them
        if include_keywords:
            # Boost queries that contain include keywords
            if any(include_term.lower() in query_lower for include_term in include_keywords):
                filtered_queries.insert(0, query)  # Add to front for priority
            else:
                filtered_queries.append(query)
        else:
            filtered_queries.append(query)
    
    return filtered_queries


def existing_hashes(dir_path: str) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    if not os.path.exists(dir_path):
        return hashes
    for fn in os.listdir(dir_path):
        fp = os.path.join(dir_path, fn)
        if os.path.isfile(fp):
            try:
                h = sha1_file(fp)
                hashes[h] = fn
            except Exception:
                continue
    return hashes


def downscale_image_inplace(path: str, target_res: str):
    # target_res like "1920x1080"
    try:
        tw, th = [int(x) for x in target_res.lower().split("x")]  # type: ignore
    except Exception:
        return
    try:
        im = Image.open(path)
        w, h = im.size
        if w <= tw and h <= th:
            return
        im.thumbnail((tw, th))
        im.save(path)
    except Exception:
        pass


def normalize_video(src_path: str, dst_path: str, target_res: str, fps: int):
    # Downscale only and re-encode if needed; keep aspect ratio
    # Use ffmpeg scale filter with force_original_aspect_ratio=decrease
    scale = f"scale='min({shlex.quote(str(target_res.split('x')[0]))},iw)':-2:force_original_aspect_ratio=decrease"
    cmd = (
        f"ffmpeg -y -i {shlex.quote(src_path)} -vf {scale},fps={int(fps)} "
        f"-c:v libx264 -preset veryfast -crf 23 -c:a aac {shlex.quote(dst_path)}"
    )
    subprocess.run(cmd, shell=True, check=False)
    if not os.path.exists(dst_path):
        # Fallback: copy if normalization failed
        try:
            import shutil

            shutil.copyfile(src_path, dst_path)
        except Exception:
            pass


def http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> dict:
    r = requests.get(url, headers=headers or {}, timeout=timeout)
    if r.status_code == 429:
        # Rate limited; raise to trigger backoff
        r.raise_for_status()
    r.raise_for_status()
    return r.json()


def http_get_bytes(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 60) -> bytes:
    r = requests.get(url, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r.content


def backoff_attempts(max_retries: int) -> List[float]:
    # Exponential backoff with jitter
    return [min(30.0, (2 ** i) + random.uniform(0, 1)) for i in range(max_retries)]


def download_pixabay(query: str, out_dir: str, per_query_max: int, env: dict) -> List[ProviderResult]:
    api_key = env.get("PIXABAY_API_KEY", "")
    if not api_key:
        return []
    items: List[ProviderResult] = []
    # Images
    base = "https://pixabay.com/api/"
    url = f"{base}?key={api_key}&q={requests.utils.quote(query)}&image_type=photo&per_page={per_query_max}&safesearch=true"
    try:
        data = http_get_json(url)
        for hit in data.get("hits", []):
            src = hit.get("largeImageURL") or hit.get("webformatURL")
            page = hit.get("pageURL") or src
            author = hit.get("user", "")
            if not src:
                continue
            # File path
            ext = os.path.splitext(src)[1] or ".jpg"
            fname = f"pixabay_{slugify(query)}_{hit.get('id', int(time.time()))}{ext}"
            fp = os.path.join(out_dir, fname)
            try:
                content = http_get_bytes(src)
                with open(fp, "wb") as f:
                    f.write(content)
                items.append(
                    ProviderResult(
                        provider="pixabay",
                        url=str(page or src),
                        file_path=fp,
                        license="Pixabay License — Free to use",
                        author=author,
                    )
                )
            except Exception:
                continue
    except Exception:
        pass
    # Videos
    try:
        base_v = "https://pixabay.com/api/videos/"
        url_v = f"{base_v}?key={api_key}&q={requests.utils.quote(query)}&per_page={per_query_max}&safesearch=true"
        data_v = http_get_json(url_v)
        for hit in data_v.get("hits", []):
            vids = hit.get("videos") or {}
            # Prefer medium or small
            src = (vids.get("medium") or vids.get("small") or {}).get("url")
            page = hit.get("pageURL") or src
            if not src:
                continue
            ext = os.path.splitext(src.split("?")[0])[1] or ".mp4"
            fname = f"pixabay_{slugify(query)}_{hit.get('id', int(time.time()))}{ext}"
            fp = os.path.join(out_dir, fname)
            try:
                content = http_get_bytes(src)
                with open(fp, "wb") as f:
                    f.write(content)
                items.append(
                    ProviderResult(
                        provider="pixabay",
                        url=str(page or src),
                        file_path=fp,
                        license="Pixabay License — Free to use",
                        author=hit.get("user", ""),
                    )
                )
            except Exception:
                continue
    except Exception:
        pass
    return items


def download_pexels(query: str, out_dir: str, per_query_max: int, env: dict) -> List[ProviderResult]:
    api_key = env.get("PEXELS_API_KEY", "")
    if not api_key:
        return []
    items: List[ProviderResult] = []
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(query)}&per_page={per_query_max}"
    try:
        data = http_get_json(url, headers=headers)
        for photo in data.get("photos", []):
            src = (photo.get("src") or {}).get("large") or (photo.get("src") or {}).get("original")
            page = photo.get("url") or src
            author = photo.get("photographer", "")
            if not src:
                continue
            ext = os.path.splitext(src.split("?")[0])[1] or ".jpg"
            fname = f"pexels_{slugify(query)}_{photo.get('id', int(time.time()))}{ext}"
            fp = os.path.join(out_dir, fname)
            try:
                content = http_get_bytes(src, headers=headers)
                with open(fp, "wb") as f:
                    f.write(content)
                # Build metadata for quality analysis
                metadata = {
                    "description": photo.get("alt", ""),
                    "tags": [query] + (photo.get("tags", []) if isinstance(photo.get("tags"), list) else []),
                    "width": photo.get("width", 0),
                    "height": photo.get("height", 0),
                    "url": page,
                    "photographer": author
                }
                
                items.append(
                    ProviderResult(
                        provider="pexels",
                        url=str(page or src),
                        file_path=fp,
                        license="Pexels License — Free to use",
                        author=author,
                        provider_metadata=metadata
                    )
                )
            except Exception:
                continue
    except Exception:
        pass
    # Videos
    try:
        urlv = f"https://api.pexels.com/videos/search?query={requests.utils.quote(query)}&per_page={per_query_max}"
        data_v = http_get_json(urlv, headers=headers)
        for video in data_v.get("videos", []):
            vfiles = video.get("video_files") or []
            # choose smallest >= 720p or closest
            src = None
            sel = None
            for vf in sorted(vfiles, key=lambda x: x.get("height") or 0):
                if (vf.get("height") or 0) >= 720:
                    sel = vf
                    break
            sel = sel or (vfiles[0] if vfiles else None)
            if sel:
                src = sel.get("link")
            if not src:
                continue
            page = video.get("url") or src
            ext = os.path.splitext(src.split("?")[0])[1] or ".mp4"
            fname = f"pexels_{slugify(query)}_{video.get('id', int(time.time()))}{ext}"
            fp = os.path.join(out_dir, fname)
            try:
                content = http_get_bytes(src, headers=headers)
                with open(fp, "wb") as f:
                    f.write(content)
                # Build video metadata for quality analysis
                author = video.get("user", {}).get("name", "") if isinstance(video.get("user"), dict) else (video.get("user") or "")
                video_metadata = {
                    "description": "",  # Pexels videos don't have descriptions
                    "tags": [query],
                    "width": sel.get("width", 0),
                    "height": sel.get("height", 0),
                    "duration": video.get("duration", 0),
                    "url": page,
                    "photographer": author
                }
                
                items.append(
                    ProviderResult(
                        provider="pexels",
                        url=str(page or src),
                        file_path=fp,
                        license="Pexels License — Free to use",
                        author=author,
                        provider_metadata=video_metadata
                    )
                )
            except Exception:
                continue
    except Exception:
        pass
    return items


def download_unsplash(query: str, out_dir: str, per_query_max: int, env: dict) -> List[ProviderResult]:
    key = env.get("UNSPLASH_ACCESS_KEY", "")
    if not key:
        return []
    items: List[ProviderResult] = []
    headers = {"Authorization": f"Client-ID {key}"}
    url = f"https://api.unsplash.com/search/photos?query={requests.utils.quote(query)}&per_page={per_query_max}"
    try:
        data = http_get_json(url, headers=headers)
        for photo in data.get("results", []) or []:
            src = (photo.get("urls") or {}).get("regular") or (photo.get("urls") or {}).get("full")
            page = photo.get("links", {}).get("html") or src
            author = (photo.get("user") or {}).get("name", "")
            if not src:
                continue
            ext = os.path.splitext((src.split("?")[0]) or "")[1] or ".jpg"
            fname = f"unsplash_{slugify(query)}_{photo.get('id', int(time.time()))}{ext}"
            fp = os.path.join(out_dir, fname)
            try:
                content = http_get_bytes(src, headers=headers)
                with open(fp, "wb") as f:
                    f.write(content)
                items.append(
                    ProviderResult(
                        provider="unsplash",
                        url=str(page or src),
                        file_path=fp,
                        license="Unsplash License — Free to use (Attribution required)",
                        author=author,
                    )
                )
            except Exception:
                continue
    except Exception:
        pass
    return items

def load_outline_for_slug(slug: str) -> Optional[dict]:
    sdir = os.path.join(BASE, "scripts")
    # Find matching outline file by slug prefix
    pattern = f"_{slug}.outline.json"
    for fn in sorted(os.listdir(sdir), reverse=True):
        if fn.endswith(".outline.json") and pattern in fn:
            try:
                return json.load(open(os.path.join(sdir, fn), "r", encoding="utf-8"))
            except Exception:
                return None
    return None


def main_reuse_mode(cfg, env, brief: dict = None):
    """Asset fetching in reuse mode - use fixtures, no network calls"""
    log.info("Running in REUSE mode - using fixtures, no network calls")
    
    spath = latest_script()
    if not spath:
        log_state("fetch_assets", "SKIP", "no scripts")
        log.info("No scripts found; nothing to fetch.")
        return

    script_text = read_script(spath)
    script_base = os.path.basename(spath)
    base_no_ext = script_base.replace(".txt", "")
    parts = base_no_ext.split("_", 1)
    date_tag = parts[0] if parts else time.strftime("%Y-%m-%d")
    slug = parts[1] if len(parts) > 1 else slugify(base_no_ext)

    out_dir = target_assets_dir(spath)
    ensure_dir(out_dir)

    # Check if assets already exist
    current_assets = [f for f in os.listdir(out_dir) 
                     if os.path.isfile(os.path.join(out_dir, f)) 
                     and not f.endswith(".json") and not f.endswith(".txt")]
    
    max_per_section = int(getattr(cfg.assets, "max_per_section", 3))
    sections = 6
    desired_total = max_per_section * sections
    
    if len(current_assets) >= desired_total:
        log_state("fetch_assets", "OK", f"exists:{len(current_assets)}")
        log.info("Assets already present; skipping fixture copy.")
        return

    # Try to copy from fixtures
    testing_cfg = getattr(cfg, "testing", {})
    fixture_dir = testing_cfg.get("fixture_dir", "assets/fixtures")
    
    # First try slug-specific fixtures
    slug_fixture_dir = os.path.join(BASE, fixture_dir, slug)
    generic_fixture_dir = os.path.join(BASE, fixture_dir, "_generic")
    
    copied = 0
    if os.path.exists(slug_fixture_dir):
        copied = copy_fixtures(slug_fixture_dir, out_dir, desired_total)
        log.info(f"Copied {copied} assets from slug-specific fixtures")
    
    if copied < desired_total and os.path.exists(generic_fixture_dir):
        remaining = desired_total - copied
        additional = copy_fixtures(generic_fixture_dir, out_dir, remaining)
        copied += additional
        log.info(f"Copied {additional} additional assets from generic fixtures")
    
    # Generate synthetic assets if still not enough
    if copied < desired_total:
        remaining = desired_total - copied
        synthetic = generate_synthetic_assets(out_dir, remaining, slug)
        copied += synthetic
        log.info(f"Generated {synthetic} synthetic assets")
    
    # Create fixture license
    create_fixture_license(out_dir, slug, copied)
    
    log_state("fetch_assets", "OK", f"fixtures:{copied}")
    log.info(f"Asset reuse complete: {copied} assets in {out_dir}")


def copy_fixtures(src_dir: str, dest_dir: str, max_count: int) -> int:
    """Copy assets from fixture directory to destination, respecting max count"""
    copied = 0
    existing_files = set(os.listdir(dest_dir))
    
    for filename in sorted(os.listdir(src_dir)):
        if filename in ["license.json", "sources_used.txt"]:
            continue
            
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi')):
            continue
            
        if filename in existing_files:
            continue
            
        if copied >= max_count:
            break
            
        src_path = os.path.join(src_dir, filename)
        dest_path = os.path.join(dest_dir, filename)
        
        try:
            shutil.copy2(src_path, dest_path)
            copied += 1
        except Exception as e:
            log.warning(f"Failed to copy {filename}: {e}")
    
    return copied


def generate_synthetic_assets(out_dir: str, count: int, slug: str) -> int:
    """Generate synthetic test assets when fixtures are insufficient"""
    generated = 0
    
    for i in range(count):
        # Create a simple colored image with text
        width, height = 1920, 1080
        colors = [(52, 152, 219), (46, 204, 113), (155, 89, 182), (241, 196, 15)]
        color = colors[i % len(colors)]
        
        img = Image.new("RGB", (width, height), color)
        draw = ImageDraw.Draw(img)
        
        # Add text overlay
        text = f"SYNTHETIC ASSET\n{slug}\n#{i+1}"
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 48)
        except (OSError, IOError):
            font = ImageFont.load_default()
        
        # Center the text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # Draw with outline
        for adj in range(-1, 2):
            for adj2 in range(-1, 2):
                draw.text((x+adj, y+adj2), text, font=font, fill=(0, 0, 0))
        draw.text((x, y), text, font=font, fill=(255, 255, 255))
        
        filename = f"synthetic_{slug}_{i+1:03d}.jpg"
        filepath = os.path.join(out_dir, filename)
        img.save(filepath, "JPEG", quality=85)
        generated += 1
    
    return generated


def create_fixture_license(out_dir: str, slug: str, asset_count: int):
    """Create license.json for fixture-based assets"""
    license_data = {
        "source": "fixtures",
        "topic_slug": slug,
        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "asset_count": asset_count,
        "mode": "reuse",
        "items": []
    }
    
    # Add entries for each asset file
    for filename in os.listdir(out_dir):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi')):
            license_data["items"].append({
                "filename": filename,
                "source": "fixtures" if not filename.startswith("synthetic_") else "synthetic",
                "license": "test_usage",
                "attribution_required": False
            })
    
    license_path = os.path.join(out_dir, "license.json")
    with open(license_path, 'w') as f:
        json.dump(license_data, f, indent=2)
    
    # Create sources_used.txt
    sources_path = os.path.join(out_dir, "sources_used.txt")
    with open(sources_path, 'w') as f:
        f.write("# Asset sources (REUSE mode)\n")
        f.write("fixtures://test_fixtures\n")


def main_live_mode(cfg, env, brief: dict = None):
    """Asset fetching in live mode - download from providers"""
    log.info("Running in LIVE mode - downloading from providers")
    
    spath = latest_script()
    if not spath:
        log_state("fetch_assets", "SKIP", "no scripts")
        log.info("No scripts found; nothing to fetch.")
        return

    script_text = read_script(spath)
    script_base = os.path.basename(spath)
    base_no_ext = script_base.replace(".txt", "")
    parts = base_no_ext.split("_", 1)
    date_tag = parts[0] if parts else time.strftime("%Y-%m-%d")
    slug = parts[1] if len(parts) > 1 else slugify(base_no_ext)

    out_dir = target_assets_dir(spath)
    ensure_dir(out_dir)

    # Check if assets already exist
    current_assets = [f for f in os.listdir(out_dir) 
                     if os.path.isfile(os.path.join(out_dir, f)) 
                     and not f.endswith(".json") and not f.endswith(".txt")]
    
    max_per_section = int(getattr(cfg.assets, "max_per_section", 3))
    sections = 6
    desired_total = max_per_section * sections
    
    if len(current_assets) >= desired_total:
        log_state("fetch_assets", "OK", f"exists:{len(current_assets)}")
        log.info("Assets already present; skipping downloads.")
        return

    queries = extract_broll_queries(script_text, brief)
    if not queries:
        # Fallback: attempt from outline broll suggestions
        outline = load_outline_for_slug(slug)
        if outline:
            broll = []
            for sec in outline.get("sections", []):
                for q in sec.get("broll", []) or []:
                    if isinstance(q, str):
                        broll.append(q)
            queries = list(dict.fromkeys([re.sub(r"\s+", " ", q).strip().lower() for q in broll if q]))
    if not queries:
        # Hard fallback - use brief keywords if available, otherwise generic
        if brief and brief.get('keywords_include'):
            # Use brief keywords for fallback queries
            include_keywords = brief['keywords_include'][:3]
            exclude_keywords = brief.get('keywords_exclude', [])
            # Filter out any include keywords that are also in exclude
            filtered_keywords = [kw for kw in include_keywords if kw.lower() not in [ex.lower() for ex in exclude_keywords]]
            if filtered_keywords:
                queries = [f"{kw} workspace" for kw in filtered_keywords]
            else:
                queries = ["typing on keyboard", "computer desk", "writing notes", "city skyline", "people working"]
        else:
            queries = ["typing on keyboard", "computer desk", "writing notes", "city skyline", "people working"]

    # Cap total queries to not exceed desired_total
    queries = queries[: max(desired_total, 1)]

    # Prepare license ledger
    license_path = os.path.join(out_dir, "license.json")
    sources_path = os.path.join(out_dir, "sources_used.txt")
    ledger = {"topic_slug": slug, "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items": []}

    # Build existing hashes for dedupe
    hashes = existing_hashes(out_dir)

    # Initialize quality analyzer
    quality_analyzer = AssetQualityAnalyzer()
    
    # Track quality metrics for all downloaded assets
    all_quality_metrics = []

    providers = [p.lower() for p in getattr(cfg.assets, "providers", ["pixabay", "pexels"])]
    per_query_max = 3  # Fetch more assets for quality selection

    for q in queries:
        fetched: List[ProviderResult] = []
        for p in providers:
            # Check budget before making any API calls
            try:
                enforce_live_budget(budget, rate_limit)
            except Exception as e:
                log.error(f"Budget enforcement failed: {e}")
                break
                
            # Retry/backoff per provider
            for delay in backoff_attempts(int(getattr(cfg.limits, "max_retries", 2)) + 1):
                try:
                    if p == "pixabay":
                        fetched = download_pixabay(q, out_dir, per_query_max, env)
                    elif p == "pexels":
                        fetched = download_pexels(q, out_dir, per_query_max, env)
                    elif p == "unsplash":
                        fetched = download_unsplash(q, out_dir, per_query_max, env)
                    else:
                        fetched = []
                    break
                except Exception as e:
                    log.info(f"Provider {p} error: {e}; retrying in {delay}s")
                    time.sleep(delay)
            # Pace calls across queries to respect provider rate limits
            time.sleep(random.uniform(0.2, 0.6))
            if fetched:
                break
        # Analyze quality for all fetched assets
        quality_assessed_assets = []
        for it in fetched:
            try:
                h = sha1_file(it.file_path)
                if h in hashes:
                    # Duplicate: remove downloaded duplicate and continue
                    try:
                        os.remove(it.file_path)
                    except Exception:
                        pass
                    continue
                
                # Analyze quality before normalization
                log.info(f"Analyzing quality for {os.path.basename(it.file_path)}")
                quality_metrics = quality_analyzer.analyze_asset(
                    it.file_path, q, it.provider_metadata or {}
                )
                it.quality_metrics = quality_metrics
                quality_assessed_assets.append(it)
                
            except Exception as e:
                log.warning(f"Quality analysis failed for {it.file_path}: {e}")
                continue
        
        # Rank assets by quality and select the best one for this query
        if quality_assessed_assets:
            ranked_assets = quality_analyzer.rank_assets(
                [asset.quality_metrics for asset in quality_assessed_assets], 
                max_count=1  # Select only the best asset per query
            )
            
            # Select the best asset and normalize it
            if ranked_assets:
                best_asset = quality_assessed_assets[ranked_assets[0].index]
                try:
                    # Normalize the asset
                    normalized_path = normalize_asset(best_asset.file_path, out_dir, cfg)
                    if normalized_path:
                        # Update the asset path to the normalized version
                        best_asset.file_path = normalized_path
                        # Add to ledger
                        ledger["items"].append({
                            "provider": best_asset.provider,
                            "url": best_asset.url,
                            "file": os.path.basename(normalized_path),
                            "license": best_asset.license,
                            "author": best_asset.author,
                            "query": q,
                            "quality_score": best_asset.quality_metrics.overall_score if best_asset.quality_metrics else None
                        })
                        log.info(f"Selected and normalized asset for query '{q}': {os.path.basename(normalized_path)}")
                    else:
                        log.warning(f"Failed to normalize asset for query '{q}'")
                except Exception as e:
                    log.error(f"Error processing best asset for query '{q}': {e}")
            else:
                log.warning(f"No quality-ranked assets for query '{q}'")
        else:
            log.warning(f"No quality-assessed assets for query '{q}'")
    
    # Write sources_used.txt
    try:
        with open(sources_path, "a", encoding="utf-8") as f:
            for it in ledger["items"]:
                f.write(f"{it['provider']}: {it['url']}\n")
    except Exception:
        pass

    # Merge license ledger if exists
    try:
        if os.path.exists(license_path):
            old = json.load(open(license_path, "r", encoding="utf-8"))
            old_items = old.get("items", [])
            # Avoid duplicates by (provider,url,file)
            seen = {(x.get("provider"), x.get("url"), x.get("file")) for x in old_items}
            for it in ledger["items"]:
                key = (it.get("provider"), it.get("url"), it.get("file"))
                if key not in seen:
                    old_items.append(it)
            old["items"] = old_items
            ledger = old
    except Exception:
        pass

    # Write license.json
    try:
        with open(license_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)
    except Exception:
        pass

    final_assets = [f for f in os.listdir(out_dir) if os.path.isfile(os.path.join(out_dir, f)) and not f.endswith(".json") and not f.endswith(".txt")]
    
    # Log quality analytics
    if all_quality_metrics:
        avg_overall_score = sum(m.overall_score for m in all_quality_metrics) / len(all_quality_metrics)
        avg_relevance_score = sum(m.relevance_score for m in all_quality_metrics) / len(all_quality_metrics)
        
        quality_issues_count = sum(len(m.quality_issues) for m in all_quality_metrics)
        
        log.info(f"Quality Analytics: {len(all_quality_metrics)} assets analyzed, "
                f"avg_overall={avg_overall_score:.1f}, avg_relevance={avg_relevance_score:.1f}, "
                f"total_issues={quality_issues_count}")
        
        log_state("fetch_assets", "OK", 
                 f"count={len(final_assets)},avg_quality={avg_overall_score:.1f}")
    else:
        log_state("fetch_assets", "OK", f"count={len(final_assets)}")
    
    log.info(f"Fetched/normalized assets: {len(final_assets)} -> {out_dir}")


def main_live_mode_with_budget(cfg, env, brief: dict = None):
    """Asset fetching in live mode - actual API calls with budget control"""
    log.info("Running in LIVE mode - making actual API calls with budget controls")
    
    testing_cfg = getattr(cfg, "testing", {})
    live_budget = int(env.get("ASSET_LIVE_BUDGET", testing_cfg.get("live_budget_per_run", 5)))
    rate_limit = testing_cfg.get("live_rate_limit_per_min", 10)
    fail_without_keys = testing_cfg.get("fail_on_live_without_keys", True)
    
    # Check API keys if required
    providers = [p.lower() for p in getattr(cfg.assets, "providers", ["pixabay", "pexels"])]
    missing_keys = []
    if "pixabay" in providers and not env.get("PIXABAY_API_KEY"):
        missing_keys.append("PIXABAY_API_KEY")
    if "pexels" in providers and not env.get("PEXELS_API_KEY"):
        missing_keys.append("PEXELS_API_KEY")
    if "unsplash" in providers and not env.get("UNSPLASH_ACCESS_KEY"):
        missing_keys.append("UNSPLASH_ACCESS_KEY")
    
    if missing_keys and fail_without_keys:
        log.error(f"Live mode requires API keys: {missing_keys}")
        log_state("fetch_assets", "ERROR", f"missing_keys={missing_keys}")
        return
    
    # Initialize budget tracker
    global live_fetch_count
    live_fetch_count = 0
    
    log.info(f"Live mode budget: {live_budget} fetches, rate limit: {rate_limit}/min")
    
    # Call main live mode with budget enforcement
    return main_live_mode_with_budget_impl(cfg, env, live_budget, rate_limit, brief)


# Global counter for live fetches
live_fetch_count = 0
last_fetch_times = []


def enforce_live_budget(budget: int, rate_limit: int):
    """Check and enforce live fetch budget and rate limits"""
    global live_fetch_count, last_fetch_times
    
    if live_fetch_count >= budget:
        raise Exception(f"Live fetch budget exceeded: {live_fetch_count}/{budget}")
    
    # Rate limiting - remove fetches older than 1 minute
    now = time.time()
    last_fetch_times = [t for t in last_fetch_times if now - t < 60]
    
    if len(last_fetch_times) >= rate_limit:
        sleep_time = 60 - (now - last_fetch_times[0])
        if sleep_time > 0:
            log.info(f"Rate limit reached, sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
    
    # Record this fetch
    live_fetch_count += 1
    last_fetch_times.append(now)
    
    log.info(f"LIVE_FETCH #{live_fetch_count} - budget: {live_fetch_count}/{budget}")


def normalize_asset(asset_path: str, out_dir: str, cfg) -> str:
    """Normalize an asset to the target resolution and format"""
    try:
        lower = asset_path.lower()
        if lower.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            # Normalize image
            downscale_image_inplace(asset_path, cfg.render.resolution)
            return asset_path
        elif lower.endswith(('.mp4', '.mov', '.mkv', '.webm')):
            # Normalize video
            norm_out = os.path.join(out_dir, os.path.splitext(os.path.basename(asset_path))[0] + "_norm.mp4")
            normalize_video(asset_path, norm_out, cfg.render.resolution, int(cfg.render.fps))
            if os.path.exists(norm_out):
                try:
                    os.remove(asset_path)
                except Exception:
                    pass
                return norm_out
            else:
                return asset_path
        else:
            return asset_path
    except Exception as e:
        log.warning(f"Failed to normalize asset {asset_path}: {e}")
        return asset_path


def main_live_mode_with_budget_impl(cfg, env, budget: int, rate_limit: int, brief: dict = None):
    """Main live mode implementation with budget enforcement"""
    return main_live_mode(cfg, env, brief)


def main(brief=None):
    """Main function for asset fetching with optional brief context"""
    cfg = load_config()
    guard_system(cfg)
    env = load_env()
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("fetch_assets", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")
    else:
        log_state("fetch_assets", "START", "brief=none")
        log.info("Running without brief - using default behavior")
    
    # Check if animatics_only mode is enabled
    animatics_only = cfg.get("animatics", {}).get("animatics_only", False)
    if animatics_only:
        log.info("Animatics-only mode enabled - skipping stock asset downloads")
        log_state("fetch_assets", "SKIP", "animatics_only_mode")
        return True
    
    # Determine asset testing mode
    testing_cfg = getattr(cfg, "testing", {})
    asset_mode = env.get("TEST_ASSET_MODE", testing_cfg.get("asset_mode", "reuse"))
    
    if asset_mode == "reuse":
        return main_reuse_mode(cfg, env, brief)
    elif asset_mode == "live":
        return main_live_mode_with_budget(cfg, env, brief)
    else:
        log.error(f"Invalid asset_mode: {asset_mode}. Must be 'reuse' or 'live'")
        log_state("fetch_assets", "ERROR", f"invalid_mode={asset_mode}")
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Asset fetching and processing")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
            log.info(f"Loaded brief: {brief.get('title', 'Untitled')}")
        except (json.JSONDecodeError, TypeError) as e:
            log.warning(f"Failed to parse brief data: {e}")
    
    with single_lock():
        main(brief)


