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

from bin.core import BASE, get_logger, load_config, load_env, log_state, single_lock  # noqa: E402


log = get_logger("youtube_upload")


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
    secrets = env.get("GOOGLE_CLIENT_SECRETS") or os.path.join(BASE, "client_secrets.json")
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


def upload_video(service, file_path: str, title: str, description: str, tags: list, privacy: str) -> Tuple[str, dict]:
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title[:95],
            "description": description[:4900],
            "tags": tags or [],
            # categoryId optional; leave unset or derive from config later
        },
        "status": {"privacyStatus": (privacy or "public")},
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = service.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        # Could add progress reporting
    vid = response.get("id")
    return vid, response


def main():
    parser = argparse.ArgumentParser(description="Upload a staged video to YouTube")
    parser.add_argument("--file", help="Path to video file (.mp4)")
    parser.add_argument("--title", help="Video title")
    parser.add_argument("--desc", help="Video description")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--visibility", help="public|unlisted|private", default="public")
    parser.add_argument("--dry-run", action="store_true", help="Print payload only")
    parser.add_argument("--auth-only", action="store_true", help="Run OAuth flow and exit (no upload)")
    args = parser.parse_args()

    cfg = load_config()
    env = load_env()

    item = load_queue_item()
    file_path = args.file or item.get("file")
    title = args.title or item.get("title") or "Untitled"
    desc = args.desc or item.get("description") or ""
    tags = (args.tags.split(",") if args.tags else item.get("tags") or [])
    vis = args.visibility or item.get("visibility") or "public"

    # Auth-only mode to prime OAuth tokens without uploading
    if args.auth_only:
        try:
            _ = build_youtube_service(env)
            log_state("youtube_upload", "OK", "oauth_ready")
            print("YouTube OAuth completed; token saved.")
        except Exception as e:
            log_state("youtube_upload", "FAIL", str(e)[:180])
            raise
        return

    if not file_path or not os.path.exists(file_path):
        log_state("youtube_upload", "SKIP", "no file")
        print("No file to upload")
        return

    payload = {"title": title, "description": desc[:160], "tags": tags, "visibility": vis}

    # Dry-run toggles
    dry_env = (env.get("YOUTUBE_UPLOAD_DRY_RUN") or "1").lower() in ("1", "true", "yes")
    dry = bool(args.dry_run or dry_env)
    if dry:
        log_state("youtube_upload", "DRY_RUN", json.dumps(payload)[:200])
        print("DRY RUN:", json.dumps(payload, indent=2)[:400] + "...")
        return

    try:
        svc = build_youtube_service(env)
        vid, resp = upload_video(svc, file_path, title, desc, tags, vis)
        log_state("youtube_upload", "OK", f"id={vid}")
        print("Uploaded video id:", vid)
    except Exception as e:
        log_state("youtube_upload", "FAIL", str(e)[:180])
        raise


if __name__ == "__main__":
    with single_lock():
        main()


