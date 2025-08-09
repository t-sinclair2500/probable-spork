#!/usr/bin/env python3
import os
import sys

import requests

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.util import BASE, ensure_dirs, load_global_config, log_state, single_lock


def load_blog_cfg():
    p = os.path.join(BASE, "conf", "blog.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "blog.example.yaml")
    import yaml

    return yaml.safe_load(open(p, "r", encoding="utf-8"))


def main():
    cfg = load_global_config()
    ensure_dirs(cfg)
    bcfg = load_blog_cfg()
    base = bcfg["wordpress"]["base_url"].rstrip("/")
    # Sitemap ping (Google)
    if bcfg.get("sitemaps", {}).get("ping_google", True):
        try:
            url = f"https://www.google.com/ping?sitemap={base}/sitemap.xml"
            r = requests.get(url, timeout=15)
            log_state("blog_ping_search", "OK", f"google:{r.status_code}")
            print("Pinged Google sitemap:", r.status_code)
        except Exception as e:
            log_state("blog_ping_search", "WARN", f"google:{e}")


if __name__ == "__main__":
    with single_lock():
        main()
