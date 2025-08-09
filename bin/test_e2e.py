#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time


def run(cmd):
    print("RUN:", cmd)
    r = subprocess.run(cmd, shell=True)
    if r.returncode != 0:
        print("FAILED:", cmd)
        sys.exit(r.returncode)


def main():
    # Minimal end-to-end with placeholders
    run("python bin/niche_trends.py")
    run("python bin/llm_cluster.py")
    run("python bin/llm_outline.py")
    run("python bin/llm_script.py")
    run("python bin/fetch_assets.py")
    run("python bin/tts_generate.py")
    run("python bin/generate_captions.py")
    run("python bin/assemble_video.py")
    run("python bin/upload_stage.py")
    # Blog lane
    run("python bin/blog_pick_topics.py")
    run("python bin/blog_generate_post.py")
    run("python bin/blog_render_html.py")
    run("python bin/blog_post_wp.py")
    run("python bin/blog_ping_search.py")
    print("E2E smoke complete.")


if __name__ == "__main__":
    main()
