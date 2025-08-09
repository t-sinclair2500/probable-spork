#!/usr/bin/env python3
import json
import os
import sqlite3
import time

from util import BASE, ensure_dirs, load_global_config, log_state, single_lock


def main():
    cfg = load_global_config()
    ensure_dirs(cfg)
    db_path = os.path.join(BASE, "data", "trending_topics.db")
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS trends(
        ts TEXT, source TEXT, title TEXT, tags TEXT
    )"""
    )
    # Placeholder demo rows (replace with real API pulls)
    sample = [
        ("youtube", "How to use AI on Raspberry Pi", "ai,raspberry pi,tools"),
        ("reddit", "TIL about space trivia that...", "space,trivia,science"),
    ]
    ts = time.strftime("%Y-%m-%d")
    for src_title in sample:
        cur.execute(
            "INSERT INTO trends(ts, source, title, tags) VALUES (?,?,?,?)", (ts,) + src_title
        )
    con.commit()
    con.close()
    log_state("niche_trends", "OK", "seeded demo trends")
    print("Seeded demo trend rows. Replace with API pulls in Phase 2.")


if __name__ == "__main__":
    with single_lock():
        main()
