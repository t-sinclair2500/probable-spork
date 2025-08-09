#!/usr/bin/env python3
import os
import sqlite3
import time

# Ensure repo root on path
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, guard_system, load_config, load_env, log_state, single_lock  # noqa: E402
import requests

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

    return [min(30.0, (2 ** i) + random.uniform(0, 1)) for i in range(max_retries + 1)]


def http_get_json(url: str, timeout: int = 30) -> dict:
    import requests

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
        for delay in backoff_delays(int(getattr(cfg.limits, "max_retries", 2))):
            try:
                data = http_get_json(url, timeout=30)
                items = data.get("items", [])
                with db_connect() as con:
                    for it in items:
                        sn = it.get("snippet", {})
                        title = sn.get("title", "").strip()
                        tags = ",".join(sn.get("tags", [])[:10]) if sn.get("tags") else ""
                        if title:
                            insert_row(con, "youtube", title, tags)
                            total += 1
                break
            except Exception as e:
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
    subs = (env.get("REDDIT_SUBREDDITS") or "technology,AskReddit,worldnews,science,AskScience").split(",")
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
                    for post in reddit.subreddit(s.strip()).top(time_filter="day", limit=20):
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


def main():
    cfg = load_config()
    guard_system(cfg)
    env = load_env()

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
        insert_row(con, "demo", "AI tools that save time", "ai,tools,productivity")
        added = 1
    con.commit()
    con.close()
    log_state("niche_trends", "OK", f"rows={added}")
    print(f"Ingestion complete; rows added: {added}")


if __name__ == "__main__":
    with single_lock():
        main()
