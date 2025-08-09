#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import random
import requests
from PIL import Image

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


log = get_logger("fetch_assets")


@dataclass
class ProviderResult:
    provider: str
    url: str
    file_path: str
    license: str
    author: str


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


def extract_broll_queries(script_text: str) -> List[str]:
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
    return cleaned


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
                items.append(
                    ProviderResult(
                        provider="pexels",
                        url=str(page or src),
                        file_path=fp,
                        license="Pexels License — Free to use",
                        author=author,
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
                items.append(
                    ProviderResult(
                        provider="pexels",
                        url=str(page or src),
                        file_path=fp,
                        license="Pexels License — Free to use",
                        author=video.get("user", {}).get("name", "") if isinstance(video.get("user"), dict) else (video.get("user") or ""),
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


def main():
    cfg = load_config()
    guard_system(cfg)
    env = load_env()

    spath = latest_script()
    if not spath:
        log_state("fetch_assets", "SKIP", "no scripts")
        log.info("No scripts found; nothing to fetch.")
        return

    script_text = read_script(spath)
    script_base = os.path.basename(spath)
    base_no_ext = script_base.replace(".txt", "")
    # Expect name like 2025-08-08_ai-tools
    parts = base_no_ext.split("_", 1)
    date_tag = parts[0] if parts else time.strftime("%Y-%m-%d")
    slug = parts[1] if len(parts) > 1 else slugify(base_no_ext)

    out_dir = target_assets_dir(spath)
    ensure_dir(out_dir)

    # Determine desired total number of assets
    max_per_section = int(getattr(cfg.assets, "max_per_section", 3))
    sections = 6
    desired_total = max_per_section * sections

    # Short-circuit if already have enough assets
    current_assets = [f for f in os.listdir(out_dir) if os.path.isfile(os.path.join(out_dir, f)) and not f.endswith(".json") and not f.endswith(".txt")]
    if len(current_assets) >= desired_total:
        log_state("fetch_assets", "OK", f"exists:{len(current_assets)}")
        log.info("Assets already present; skipping downloads.")
        return

    queries = extract_broll_queries(script_text)
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
        # Hard fallback
        queries = ["typing on keyboard", "computer desk", "writing notes", "city skyline", "people working"]

    # Cap total queries to not exceed desired_total
    queries = queries[: max(desired_total, 1)]

    # Prepare license ledger
    license_path = os.path.join(out_dir, "license.json")
    sources_path = os.path.join(out_dir, "sources_used.txt")
    ledger = {"topic_slug": slug, "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items": []}

    # Build existing hashes for dedupe
    hashes = existing_hashes(out_dir)

    providers = [p.lower() for p in getattr(cfg.assets, "providers", ["pixabay", "pexels"])]
    per_query_max = 1  # fetch one asset per query to diversify

    for q in queries:
        fetched: List[ProviderResult] = []
        for p in providers:
            # Retry/backoff per provider
            for delay in backoff_attempts(int(getattr(cfg.limits, "max_retries", 2)) + 1):
                try:
                    if p == "pixabay":
                        fetched = download_pixabay(q, out_dir, per_query_max, env)
                    elif p == "pexels":
                        fetched = download_pexels(q, out_dir, per_query_max, env)
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
        # Dedupe and normalize
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
                hashes[h] = os.path.basename(it.file_path)
                # Normalize image/video
                lower = it.file_path.lower()
                if lower.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    downscale_image_inplace(it.file_path, cfg.render.resolution)
                elif lower.endswith(('.mp4', '.mov', '.mkv', '.webm')):
                    norm_out = os.path.splitext(it.file_path)[0] + "_norm.mp4"
                    normalize_video(it.file_path, norm_out, cfg.render.resolution, int(cfg.render.fps))
                    if os.path.exists(norm_out):
                        try:
                            os.remove(it.file_path)
                        except Exception:
                            pass
                        it.file_path = norm_out
                # Record license entry
                ledger["items"].append(
                    {
                        "provider": it.provider,
                        "url": it.url,
                        "file": os.path.basename(it.file_path),
                        "license": it.license,
                        "user": it.author,
                    }
                )
            except Exception:
                continue

        # Stop if we have enough assets
        current_assets = [f for f in os.listdir(out_dir) if os.path.isfile(os.path.join(out_dir, f)) and not f.endswith(".json") and not f.endswith(".txt")]
        if len(current_assets) >= desired_total:
            break

    # Append to sources_used.txt
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
    log_state("fetch_assets", "OK", f"count={len(final_assets)}")
    log.info(f"Fetched/normalized assets: {len(final_assets)} -> {out_dir}")


if __name__ == "__main__":
    with single_lock():
        main()


