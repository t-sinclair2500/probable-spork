#!/usr/bin/env python3
import argparse
import json
import os
import sys
from typing import Tuple

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from urllib.parse import urlencode  # noqa: E402

from bin.core import (  # noqa: E402
    BASE,
    get_logger,
    get_publish_flags,
    load_config,
    load_env,
    log_state,
    single_lock,
)

log = get_logger("youtube_upload")


def load_monetization_config() -> dict:
    """Load monetization configuration"""
    config_path = os.path.join(BASE, "conf", "monetization.yaml")
    if not os.path.exists(config_path):
        log.warning("No monetization.yaml found, using empty config")
        return {}

    try:
        import yaml

        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        log.warning(f"Failed to load monetization config: {e}")
        return {}


def build_utm_url(base_url: str, utm_params: dict) -> str:
    """Build URL with UTM parameters"""
    if not base_url or not utm_params:
        return base_url

    # Filter out None values
    clean_params = {k: v for k, v in utm_params.items() if v is not None}
    if not clean_params:
        return base_url

    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(clean_params)}"


def generate_monetized_description(
    original_desc: str, metadata: dict, monetization_config: dict
) -> str:
    """Generate a monetized YouTube description with CTAs, disclosures, and UTM links"""
    if not monetization_config:
        return original_desc

    youtube_config = monetization_config.get("youtube", {})

    # Start with original description
    sections = [original_desc] if original_desc else []

    # Add chapters if available in metadata
    if metadata.get("chapters"):
        sections.append("\n🕒 CHAPTERS:")
        for i, chapter in enumerate(metadata["chapters"]):
            timestamp = chapter.get("timestamp", f"0:{i*10:02d}")
            title = chapter.get("title", f"Chapter {i+1}")
            sections.append(f"{timestamp} - {title}")

    # Add call-to-action
    cta_text = youtube_config.get("cta_text")
    if cta_text:
        sections.append(f"\n{cta_text}")

    # Add end screen CTA
    end_screen_cta = youtube_config.get("end_screen_cta")
    if end_screen_cta:
        sections.append(f"\n{end_screen_cta}")

    # Add affiliate disclosure
    affiliate_disclosure = youtube_config.get("affiliate_disclosure")
    if affiliate_disclosure:
        sections.append(f"\n⚠️ DISCLOSURE:\n{affiliate_disclosure}")

    # Add hashtags
    hashtags = youtube_config.get("default_hashtags", [])
    if hashtags:
        sections.append(f"\n{' '.join(hashtags)}")

    return "\n".join(sections)


def generate_enhanced_title(original_title: str, metadata: dict) -> str:
    """Generate an enhanced title with engagement hooks"""
    if not original_title:
        return "Untitled Video"

    # Remove file extensions and clean up
    title = original_title.replace(".mp4", "").replace("_", " ").replace("-", " ")

    # Use metadata title if available (more descriptive)
    if metadata.get("title") and len(metadata["title"]) > len(title):
        title = metadata["title"]

    # Ensure title doesn't exceed YouTube's 100 character limit
    if len(title) > 95:  # Leave room for potential additions
        title = title[:92] + "..."

    return title


def load_queue_item() -> dict:
    qpath = os.path.join(BASE, "data", "upload_queue.json")
    if not os.path.exists(qpath):
        return {}
    try:
        arr = json.load(open(qpath, "r", encoding="utf-8"))
    except Exception:
        arr = []
    return arr[-1] if arr else {}


def build_youtube_service(env: dict):
    # Uses OAuth installed app flow; requires a client secrets file.
    # Looks at GOOGLE_CLIENT_SECRETS or ./client_secrets.json by default.
    secrets = env.get("GOOGLE_CLIENT_SECRETS") or os.path.join(
        BASE, "client_secrets.json"
    )
    token_path = os.path.join(BASE, "data", "token_youtube.json")
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]

    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, scopes)
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                from google.auth.transport.requests import Request

                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(secrets, scopes=scopes)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    service = build("youtube", "v3", credentials=creds)
    return service


def upload_video(
    service,
    file_path: str,
    title: str,
    description: str,
    tags: list,
    privacy: str,
    category_id: str = None,
    thumbnail_path: str = None,
) -> Tuple[str, dict]:
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title[:100],  # YouTube limit is 100 characters
            "description": description[:5000],  # YouTube limit is 5000 characters
            "tags": (tags or [])[:10],  # YouTube limit is 10 tags max
        },
        "status": {"privacyStatus": (privacy or "public")},
    }

    # Add category if specified (default is 22 for "People & Society")
    if category_id:
        body["snippet"]["categoryId"] = str(category_id)

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = service.videos().insert(
        part=",".join(body.keys()), body=body, media_body=media
    )

    # Upload with progress reporting
    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                log.info(f"Upload progress: {int(status.progress() * 100)}%")
        except Exception as e:
            log.error(f"Upload chunk failed: {e}")
            raise

    vid = response.get("id")

    # Upload thumbnail if provided
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            thumbnail_media = MediaFileUpload(thumbnail_path)
            service.thumbnails().set(videoId=vid, media_body=thumbnail_media).execute()
            log.info(f"Thumbnail uploaded for video {vid}")
        except Exception as e:
            log.warning(f"Thumbnail upload failed: {e}")

    return vid, response


def load_video_metadata(file_path: str) -> dict:
    """Load metadata for a video from its corresponding .metadata.json file"""
    if not file_path:
        return {}

    # Look for corresponding metadata file
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    metadata_path = os.path.join(BASE, "scripts", f"{base_name}.metadata.json")

    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Failed to load metadata from {metadata_path}: {e}")

    return {}


def find_thumbnail(video_path: str) -> str:
    """Find corresponding thumbnail for a video"""
    if not video_path:
        return None

    base_name = os.path.splitext(os.path.basename(video_path))[0]

    # Look in videos directory for thumbnail
    possible_thumbnails = [
        os.path.join(os.path.dirname(video_path), f"{base_name}.png"),
        os.path.join(os.path.dirname(video_path), f"{base_name}_thumb.png"),
        os.path.join(BASE, "thumbnails", f"{base_name}.png"),
    ]

    for thumb_path in possible_thumbnails:
        if os.path.exists(thumb_path):
            return thumb_path

    return None


def main(brief=None):
    """Main function for YouTube upload staging with optional brief context"""
    parser = argparse.ArgumentParser(description="Upload a staged video to YouTube")
    parser.add_argument("--file", help="Path to video file (.mp4)")
    parser.add_argument("--title", help="Video title")
    parser.add_argument("--desc", help="Video description")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument(
        "--visibility", help="public|unlisted|private", default="public"
    )
    parser.add_argument(
        "--category", help="YouTube category ID (default: 22)", default="22"
    )
    parser.add_argument("--thumbnail", help="Path to thumbnail image")
    parser.add_argument("--dry-run", action="store_true", help="Print payload only")
    parser.add_argument(
        "--auth-only", action="store_true", help="Run OAuth flow and exit (no upload)"
    )
    args = parser.parse_args()

    cfg = load_config()
    env = load_env()

    # Log brief context if available
    if brief:
        brief_title = brief.get("title", "Untitled")
        log_state("youtube_upload", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")
    else:
        log_state("youtube_upload", "START", "brief=none")
        log.info("Running without brief - using default behavior")

    monetization_config = load_monetization_config()

    # Load from upload queue or use CLI args
    item = load_queue_item()
    file_path = args.file or item.get("file")

    # Load metadata if available
    metadata = load_video_metadata(file_path)

    # Build video details with priority: CLI args > metadata > queue item > defaults
    original_title = (
        args.title or metadata.get("title") or item.get("title") or "Untitled"
    )
    original_desc = (
        args.desc or metadata.get("description") or item.get("description") or ""
    )

    # Generate enhanced title and monetized description
    title = generate_enhanced_title(original_title, metadata)
    desc = generate_monetized_description(original_desc, metadata, monetization_config)

    # Handle tags from various sources
    tags = []
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",")]
    elif metadata.get("tags"):
        tags = metadata["tags"]
    elif item.get("tags"):
        tags = item["tags"]

    vis = args.visibility or item.get("visibility") or cfg.upload.visibility or "public"
    category_id = args.category
    thumbnail_path = args.thumbnail or find_thumbnail(file_path)

    # Auth-only mode to prime OAuth tokens without uploading
    if args.auth_only:
        try:
            print("Initializing YouTube OAuth flow...")
            print("This will open a browser window for authentication.")
            print("Grant permissions to upload videos to your YouTube channel.")
            _ = build_youtube_service(env)
            log_state("youtube_upload", "OK", "oauth_ready")
            print("✓ YouTube OAuth completed successfully!")
            print("Token saved to data/token_youtube.json")
            print("You can now upload videos without re-authentication.")
        except Exception as e:
            log_state("youtube_upload", "FAIL", str(e)[:180])
            print(f"✗ OAuth failed: {e}")
            raise
        return

    if not file_path or not os.path.exists(file_path):
        log_state("youtube_upload", "SKIP", "no file")
        print("No video file found to upload")
        if file_path:
            print(f"File does not exist: {file_path}")
        return

    # Build comprehensive payload for display
    payload = {
        "file": file_path,
        "title": title,
        "description": desc[:200] + "..." if len(desc) > 200 else desc,
        "tags": tags,
        "visibility": vis,
        "category_id": category_id,
        "thumbnail": thumbnail_path,
        "file_size_mb": (
            round(os.path.getsize(file_path) / 1024 / 1024, 1)
            if os.path.exists(file_path)
            else 0
        ),
    }

    # Use centralized flag governance
    flags = get_publish_flags(cli_dry_run=args.dry_run, target="youtube")
    dry = flags["youtube_dry_run"]

    if dry:
        log_state("youtube_upload", "DRY_RUN", json.dumps(payload)[:200])
        print("=== DRY RUN MODE ===")
        print("Would upload to YouTube with the following details:")
        print(json.dumps(payload, indent=2))
        print("\nTo perform actual upload:")
        print("1. Set YOUTUBE_UPLOAD_DRY_RUN=false in .env")
        print("2. Or use without --dry-run flag")
        print("3. Ensure OAuth is set up with --auth-only first")
        print("\nCurrent flags controlled by: CLI > ENV > defaults")
        return

    # Real upload
    try:
        print(f"Uploading video: {title}")
        print(f"File: {file_path} ({payload['file_size_mb']} MB)")

        svc = build_youtube_service(env)
        vid, resp = upload_video(
            svc, file_path, title, desc, tags, vis, category_id, thumbnail_path
        )

        log_state("youtube_upload", "OK", f"id={vid}")
        print("✓ Successfully uploaded to YouTube!")
        print(f"Video ID: {vid}")
        print(f"URL: https://youtube.com/watch?v={vid}")

        # Update queue item with video ID if it exists
        if item:
            item["youtube_id"] = vid
            item["uploaded_at"] = json.dumps({"youtube": vid})

    except Exception as e:
        log_state("youtube_upload", "FAIL", str(e)[:180])
        print(f"✗ Upload failed: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube upload")
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
