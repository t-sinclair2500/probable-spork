# One-Pi YouTube Automation Pipeline

Single Raspberry Pi 5 (64-bit) pipeline that discovers topics, generates scripts with a local LLM (Ollama), performs TTS, fetches royalty-free assets, assembles videos (MoviePy + FFmpeg), and stages for upload. Includes local ASR via `whisper.cpp`. Optional cloud fallbacks for TTS/ASR are wired but OFF by default.

## Quick Start

1) **Install system deps**
```bash
sudo apt update && sudo apt install -y python3-full python3-venv python3-pip ffmpeg git jq sqlite3 rclone build-essential cmake
```

2) **Create venv and install Python deps**
```bash
cd ~/youtube_onepi_pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

3) **Install & run Ollama (LLM)**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull phi3:mini
# (Optional) ollama pull llama3.2:3b-instruct
```

4) **Build whisper.cpp (optional for captions)**
```bash
git clone https://github.com/ggerganov/whisper.cpp.git ~/whisper.cpp
cd ~/whisper.cpp && cmake -B build && cmake --build build -j --config Release
bash models/download-ggml-model.sh base.en
```

5) **Copy config and set values**
```bash
cp conf/global.example.yaml conf/global.yaml
cp .env.example .env
# Edit conf/global.yaml to set niches, tone, video length, etc.
# Edit .env (from .env.example) for API keys (assets providers, ingestion, optional fallbacks).
# Note: Paths auto-detect based on your environment (Mac dev vs Pi production)
```

6) **Seed cron (optional)**
See `crontab.seed.txt`. Apply with:
```bash
crontab crontab.seed.txt
```

7) **Run a full cycle manually (first time)**
```bash
source .venv/bin/activate
python bin/niche_trends.py
python bin/llm_cluster.py
python bin/llm_outline.py
python bin/llm_script.py
python bin/fetch_assets.py
python bin/tts_generate.py
python bin/assemble_video.py
python bin/upload_stage.py
```

## Storage Notes

- Use a USB SSD (recommended). Update paths in `conf/global.yaml` if needed.
- This repo uses a single-lane, lock-aware flow to avoid overloading the Pi.

## Safety & Licensing

- Asset fetcher records license info per asset directory. You must respect each source’s license terms.
- Cloud services are optional and OFF by default; enabling them may incur costs.

## Support

This scaffold is a first-pass implementation. Use the Phase 2 onboarding docs and Cursor prompts to finish/extend features.


---

## Blog Lane (Shared Repo)

This repo also includes a **blog lane** that reuses shared artifacts (topics, scripts, assets) to publish posts to WordPress via REST.

### Setup
1) Copy the blog config:
```bash
cp conf/blog.example.yaml conf/blog.yaml
```
2) Edit `conf/blog.yaml` (set WordPress base URL, poster user, and Application Password).
3) Ensure WordPress is installed on the Pi and you created a **non-admin** poster user with an **Application Password**.

### Manual run (first time)
```bash
source .venv/bin/activate
python bin/blog_pick_topics.py
python bin/blog_generate_post.py
python bin/blog_render_html.py
python bin/blog_post_wp.py
python bin/blog_ping_search.py
```

> By default, posting uses a **dry-run** mode (prints JSON) until you toggle `DRY_RUN=False` in `bin/blog_post_wp.py`.
> Prefer setting `BLOG_DRY_RUN=false` in `.env` instead of editing code.


## Cron (Unified Seed)

A unified crontab is provided in `crontab.seed.txt` that schedules shared ingestion, the YouTube lane, the Blog lane, and health checks. Apply it with:

```bash
crontab crontab.seed.txt
```

Each script is lock-aware and exits if another heavy step is in progress.


## Makefile commands
- `make install` — create venv and install deps
- `make check` — validate config and env
- `make run-once` — full YouTube lane once (placeholders where noted)
- `make blog-once` — full Blog lane once (dry-run by default)
- `make cron-install` — install unified cron
- `make backup` — dump WP DB & repo artifacts
- `make health` — start local health server

## Health server
## Configuration reference

- `.env` (copy from `.env.example`)
  - PIXABAY_API_KEY, PEXELS_API_KEY (assets)
  - Optional: UNSPLASH_ACCESS_KEY (only if enabled later)
  - Optional ingestion: YOUTUBE_API_KEY or GOOGLE_API_KEY; REDDIT_CLIENT_ID/SECRET/USER_AGENT
  - Optional fallbacks: OPENAI_API_KEY
  - BLOG_DRY_RUN=true|false

- `conf/global.yaml`
  - `limits.max_retries` controls API backoff retries for providers.
  - `assets.providers` currently supports `pixabay`, `pexels`.
  - To add Unsplash, enable in config and add key to `.env` (code support TBD).

- `conf/sources.yaml` is deprecated; use `.env` for keys.
After running `scripts/install_systemd_and_logrotate.sh`, visit:
```
http://<pi-lan-ip>:8088/health
```
