#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3

# Ensure repo root on path
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import requests

from bin.core import (  # noqa: E402
    BASE,
    get_logger,
    guard_system,
    load_config,
    load_env,
    log_state,
    single_lock,
)

log = get_logger("niche_trends")


def db_connect() -> sqlite3.Connection:
    db_path = os.path.join(BASE, "data", "trending_topics.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS trends(
        ts TEXT, source TEXT, title TEXT, tags TEXT
    )"""
    )
    # Best-effort de-dup before creating unique index (keep lowest rowid)
    try:
        cur.execute(
            "DELETE FROM trends WHERE rowid NOT IN (SELECT MIN(rowid) FROM trends GROUP BY ts, source, title)"
        )
    except Exception:
        pass
    # Ensure uniqueness per-day by title+source to avoid floods on retries
    try:
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uniq_trend ON trends(ts, source, title)"
        )
    except Exception:
        # If duplicates still exist, ignore index creation; subsequent inserts use OR IGNORE
        pass
    con.commit()
    return con


def insert_row(con: sqlite3.Connection, source: str, title: str, tags: str):
    ts = time.strftime("%Y-%m-%d")
    try:
        con.execute(
            "INSERT OR IGNORE INTO trends(ts, source, title, tags) VALUES (?,?,?,?)",
            (ts, source, title, tags),
        )
    except Exception:
        pass


def backoff_delays(max_retries: int = 2):
    import random

    return [min(30.0, (2**i) + random.uniform(0, 1)) for i in range(max_retries + 1)]


def http_get_json(url: str, timeout: int = 30) -> dict:

    r = requests.get(url, timeout=timeout)
    if r.status_code == 429:
        r.raise_for_status()
    r.raise_for_status()
    return r.json()


def fetch_youtube(env: dict, cfg) -> int:
    key = env.get("YOUTUBE_API_KEY") or env.get("GOOGLE_API_KEY")
    if not key:
        return 0
    # Use mostPopular by category IDs from config
    total = 0
    cats = getattr(cfg.pipeline, "category_ids", [27, 28])
    for cat in cats:
        url = (
            "https://www.googleapis.com/youtube/v3/videos?"
            f"part=snippet&chart=mostPopular&regionCode=US&maxResults=25&videoCategoryId={cat}&key={key}"
        )
        fallback_url = (
            "https://www.googleapis.com/youtube/v3/videos?"
            f"part=snippet&chart=mostPopular&regionCode=US&maxResults=25&key={key}"
        )
        for delay in backoff_delays(int(getattr(cfg.limits, "max_retries", 2))):
            try:
                data = http_get_json(url, timeout=30)
                items = data.get("items", [])
                with db_connect() as con:
                    for it in items:
                        sn = it.get("snippet", {})
                        title = sn.get("title", "").strip()
                        tags = (
                            ",".join(sn.get("tags", [])[:10]) if sn.get("tags") else ""
                        )
                        if title:
                            insert_row(con, "youtube", title, tags)
                            total += 1
                break
            except Exception as e:
                # If category-specific call 404s, try without category as a fallback
                try:
                    import requests as _rq  # local alias to check HTTPError type safely

                    is_http_err = isinstance(e, _rq.exceptions.HTTPError)
                    status = getattr(getattr(e, "response", None), "status_code", None)
                except Exception:
                    is_http_err = False
                    status = None

                if is_http_err and status == 404:
                    try:
                        data = http_get_json(fallback_url, timeout=30)
                        items = data.get("items", [])
                        with db_connect() as con:
                            for it in items:
                                sn = it.get("snippet", {})
                                title = sn.get("title", "").strip()
                                tags = (
                                    ",".join(sn.get("tags", [])[:10])
                                    if sn.get("tags")
                                    else ""
                                )
                                if title:
                                    insert_row(con, "youtube", title, tags)
                                    total += 1
                        log_state(
                            "niche_trends_youtube",
                            "INFO",
                            f"cat={cat};fallback_no_category_used",
                        )
                        break
                    except Exception as fe:
                        log_state(
                            "niche_trends_youtube",
                            "WARN",
                            f"cat={cat};fallback_err:{fe}",
                        )
                        time.sleep(delay)
                        continue
                else:
                    log_state("niche_trends_youtube", "WARN", f"cat={cat};retrying:{e}")
                    time.sleep(delay)
    return total


def fetch_pytrends(cfg) -> int:
    try:
        from pytrends.request import TrendReq  # type: ignore

        pytrends = TrendReq(hl="en-US", tz=360)
        niches = getattr(cfg.pipeline, "niches", ["ai tools"]) or ["ai tools"]
        total = 0
        with db_connect() as con:
            for niche in niches[:5]:
                try:
                    pytrends.build_payload([niche], timeframe="now 7-d", geo="US")
                    related = pytrends.related_queries().get(niche) or {}
                    top = (related.get("top") or [])[:15]
                    # top is a DataFrame; handle robustly
                    if hasattr(top, "iterrows"):
                        for _, row in top.iterrows():
                            title = str(row.get("query", "")).strip()
                            if title:
                                insert_row(con, "gtrends", title, niche)
                                total += 1
                except Exception:
                    continue
        return total
    except Exception:
        return 0


def fetch_reddit(env: dict, cfg) -> int:
    cid = env.get("REDDIT_CLIENT_ID")
    csecret = env.get("REDDIT_CLIENT_SECRET")
    uagent = env.get("REDDIT_USER_AGENT") or "yt-pipeline/0.1 by pi"
    subs = (
        env.get("REDDIT_SUBREDDITS")
        or "technology,AskReddit,worldnews,science,AskScience"
    ).split(",")
    if not (cid and csecret):
        return 0
    try:
        import praw  # type: ignore

        reddit = praw.Reddit(
            client_id=cid,
            client_secret=csecret,
            user_agent=uagent,
        )
        total = 0
        with db_connect() as con:
            for s in subs[:5]:
                try:
                    for post in reddit.subreddit(s.strip()).top(
                        time_filter="day", limit=20
                    ):
                        title = (post.title or "").strip()
                        if title:
                            insert_row(con, "reddit", title, s.strip())
                            total += 1
                    time.sleep(0.5)
                except Exception:
                    continue
        return total
    except Exception:
        return 0


def main(brief=None, models_config=None):
    cfg = load_config()
    guard_system(cfg)
    env = load_env()

    # Log brief context if available
    if brief:
        brief_title = brief.get("title", "Untitled")
        log_state("niche_trends", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")

        # Log brief keywords for transparency
        if brief.get("keywords_include"):
            log.info(f"Brief keywords to include: {brief['keywords_include']}")
        if brief.get("keywords_exclude"):
            log.info(f"Brief keywords to exclude: {brief['keywords_exclude']}")
    else:
        log_state("niche_trends", "START", "brief=none")
        log.info("Running without brief - using default behavior")

    con = db_connect()
    added = 0
    try:
        added += fetch_youtube(env, cfg)
    except Exception:
        pass
    try:
        added += fetch_pytrends(cfg)
    except Exception:
        pass
    try:
        added += fetch_reddit(env, cfg)
    except Exception:
        pass

    # If nothing added, add a single demo row (idempotent-ish; duplicates not harmful for demo)
    if added == 0:
        # Use brief keywords if available, otherwise fall back to defaults
        if brief and brief.get("keywords_include"):
            # Use brief keywords and avoid excluded terms
            include_keywords = brief["keywords_include"][:3]
            exclude_keywords = brief.get("keywords_exclude", [])

            # Filter out any include keywords that are also in exclude
            filtered_keywords = [
                kw
                for kw in include_keywords
                if kw.lower() not in [ex.lower() for ex in exclude_keywords]
            ]

            if filtered_keywords:
                demo_keywords = ",".join(filtered_keywords)
                demo_title = f"{brief.get('title', 'Topic')} that save time"
            else:
                # Fallback if all keywords were excluded
                demo_keywords = "productivity,tips,guide"
                demo_title = f"{brief.get('title', 'Topic')} guide"
        else:
            # No brief - use generic defaults
            demo_keywords = "productivity,tips,guide"
            demo_title = "Productivity tips that save time"

        insert_row(con, "demo", demo_title, demo_keywords)
        added = 1
    con.commit()
    con.close()

    # Include brief context in final log
    if brief:
        brief_title = brief.get("title", "Untitled")
        log_state("niche_trends", "OK", f"rows={added};brief={brief_title}")
    else:
        log_state("niche_trends", "OK", f"rows={added}")

    print(f"Ingestion complete; rows added: {added}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Niche trends ingestion")
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
        main(brief, models_config=None)  # models_config not passed via CLI
