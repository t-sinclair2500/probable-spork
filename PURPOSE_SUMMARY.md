## Purpose Summary — One-Pi Shared Content Pipeline (YouTube + Blog)

**Problem**
- Automate daily content production on a single Raspberry Pi 5 using a local-first toolchain, with optional cloud fallbacks. Produce both a YouTube video and a WordPress blog post from a shared source of truth.

**Primary Users**
- Solo operator/creator running the stack headlessly on a Pi; develops on macOS and deploys to the Pi.

**Inputs**
- Operator configuration in `conf/global.yaml` and `conf/blog.yaml`; secrets in `.env`.
- LLM service (Ollama) for clustering, outlines, scripts; prompts in `prompts/`.
- Trend ingestion (YouTube/Google Trends/Reddit) populating shared data.

**Outputs**
- Video artifacts: outline (`*.outline.json`), script (`*.txt`), voiceover (`voiceovers/*.mp3`), optional captions (`*.srt`), assembled video (`videos/*.mp4`), thumbnail (`*.png`).
- Blog artifacts: Markdown/HTML render, optional live WordPress post via REST, and sitemap ping.
- Operational telemetry: `jobs/state.jsonl`, upload staging entries in `data/upload_queue.json`.

**How to Run (macOS)**
- Prereqs: Python 3.9+, FFmpeg installed, Ollama running locally for development.
- Commands:
  - `make install`
  - `make check`
  - `make run-once` (YouTube lane)
  - `make blog-once` (Blog lane; dry-run by default)

**How to Run (Raspberry Pi 5, Debian-based)**
- Prereqs: `apt install -y python3-full python3-venv python3-pip ffmpeg git jq sqlite3 rclone build-essential cmake`; install Ollama; build `whisper.cpp` if captions desired.
- Commands:
  - `make pi-deploy` (pull main, install deps, validate)
  - `make pi-run-once` (YouTube lane once)
  - `make pi-blog-once` (Blog lane once)
  - Optional: `make cron-install` for scheduled runs and `make pi-health` for health endpoint.

**Success Criteria (v1)**
- End-to-end dry-run completes on macOS and Pi: produces one playable MP4 and a rendered blog post (dry-run payload for WP).
- Idempotent, lock-aware, and license-aware; re-runs do not duplicate work.

**Current Maturity Snapshot**
- YouTube lane: TTS, captions, assembly, thumbnail, and staging are implemented and produce artifacts. See `videos/` and `voiceovers/`.
- Blog lane: pick, generate, render, SEO gate done; WordPress post supports DRY_RUN and featured image upload; inline image upload pending.
- Ops: locks, guards, health server, cron, and backups are present.

**Key Sources**
- Run and setup: `README.md` lines 5–26, 50–61, 117–125.
- Architecture/contracts: `CURSOR_SHARED_PIPELINE.md` sections 1.1–2.5 and 4–7.
- Canonical tasks: `MASTER_TODO.md` entire file; phases and acceptance criteria.
- Blog/WordPress specifics: `conf/blog.example.yaml`, `bin/blog_post_wp.py` functions and DRY_RUN control.


