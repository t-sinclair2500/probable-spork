#!/usr/bin/env python3
import os, requests
from bin.util import single_lock, log_state, load_global_config, BASE, ensure_dirs

def load_blog_cfg():
    p = os.path.join(BASE, "conf", "blog.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "blog.example.yaml")
    import yaml
    return yaml.safe_load(open(p, "r", encoding="utf-8"))

def main():
    cfg = load_global_config(); ensure_dirs(cfg)
    bcfg = load_blog_cfg()
    base = bcfg["wordpress"]["base_url"].rstrip("/")
    # Sitemap ping (Google)
    if bcfg.get("sitemaps",{}).get("ping_google", True):
        try:
            url = f"https://www.google.com/ping?sitemap={base}/sitemap.xml"
            r = requests.get(url, timeout=15)
            log_state("blog_ping_search","OK", f"google:{r.status_code}")
            print("Pinged Google sitemap:", r.status_code)
        except Exception as e:
            log_state("blog_ping_search","WARN", f"google:{e}")

if __name__ == "__main__":
    with single_lock():
        main()
