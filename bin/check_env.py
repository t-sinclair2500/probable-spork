#!/usr/bin/env python3
import os, sys, json
from bin.core import load_env, load_config, get_logger

log = get_logger("check_env")

def main():
    cfg = load_config()
    env = load_env()
    issues = []

    # If assets providers enabled, require at least one API key
    if cfg.assets.providers:
        if not (env.get("PIXABAY_API_KEY") or env.get("PEXELS_API_KEY") or env.get("UNSPLASH_ACCESS_KEY")):
            issues.append("No asset provider API keys set (PIXABAY_API_KEY/PEXELS_API_KEY/UNSPLASH_ACCESS_KEY).")

    # If blog lane used later, remind about WP app password
    from pathlib import Path
    blog_cfg = Path(os.path.join(os.path.dirname(__file__),"..","conf","blog.yaml"))
    if blog_cfg.exists():
        pass

    if issues:
        log.error(json.dumps({"issues": issues}))
        sys.exit(2)
    log.info("Environment/config checks passed.")

if __name__ == "__main__":
    main()
