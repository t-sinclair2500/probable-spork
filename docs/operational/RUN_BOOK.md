## Run Book — Bootstrap, Smoke Test, and Deploy (macOS + Raspberry Pi)

This run book provides exact, copy/paste commands to bootstrap the environment and run a minimal end-to-end smoke on macOS and Raspberry Pi. The source of truth for tasks is `MASTER_TODO.md`.

Prerequisites
- Python 3.9+; FFmpeg installed; Git; curl; jq.
- For captions: `whisper.cpp` built; otherwise captions step will skip.
- For LLM: Ollama installed and serving locally.

macOS — First-time setup
```bash
cd /Users/tylersinclair/Documents/GitHub/probable-spork
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
cp conf/global.example.yaml conf/global.yaml
cp conf/blog.example.yaml conf/blog.yaml
cp .env.example .env  # then edit .env with your keys; BLOG_DRY_RUN=true by default
```

Start Ollama (developer machine)
```bash
ollama serve &
ollama pull phi3:mini || true
```

Smoke test — YouTube lane (macOS)
```bash
. .venv/bin/activate
make check
make run-once
ls -la videos/ voiceovers/
```

Smoke test — Blog lane (macOS, dry-run)
```bash
. .venv/bin/activate
make blog-once
tail -n 50 jobs/state.jsonl | grep -E "blog_post_wp|blog_ping_search" | cat
```

Raspberry Pi (Debian-based) — First-time setup
```bash
sudo apt update && sudo apt install -y python3-full python3-venv python3-pip ffmpeg git jq sqlite3 rclone build-essential cmake
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull phi3:mini || true
git clone <your-fork-or-repo-url> ~/youtube_onepi_pipeline || true
cd ~/youtube_onepi_pipeline
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
cp conf/global.example.yaml conf/global.yaml
cp conf/blog.example.yaml conf/blog.yaml
cp .env.example .env  # edit with keys; BLOG_DRY_RUN=true until ready
```

Optional: build whisper.cpp on Pi
```bash
git clone https://github.com/ggerganov/whisper.cpp.git ~/whisper.cpp
cd ~/whisper.cpp && cmake -B build && cmake --build build -j --config Release
bash models/download-ggml-model.sh base.en
```

Run once on Pi
```bash
. .venv/bin/activate
make run-once
make blog-once
```

Health and logs
```bash
. .venv/bin/activate
python bin/health_server.py &
curl -s http://127.0.0.1:8088/health | python -m json.tool || true
tail -n 100 jobs/state.jsonl | cat
```

Systemd and cron (optional)
- Use `ops/crontab.seed.txt` for scheduling. Apply with: `crontab ops/crontab.seed.txt`.
- Service units available in `services/` for Ollama and health server.

GitHub-centered workflow
- Develop and test on macOS; commit and push to GitHub.
- On the Pi: `make pi-deploy` to pull main, install deps, and validate. Then run `make pi-run-once` or `make pi-blog-once`.

Expected outputs (smoke)
- New files in `scripts/`, assets in `assets/<date>_<slug>/` (with `license.json` and `sources_used.txt`).
- `voiceovers/<date>_<slug>.mp3`, optional `*.srt` if whisper.cpp present.
- `videos/<date>_<slug>.mp4` and a thumbnail PNG.
- Blog lane DRY_RUN payload in logs and `blog_ping_search` OK.

Troubleshooting
- If ingestion fails (YouTube API 404), proceed with existing `data/topics_queue.json` and continue the pipeline; investigate keys/quotas.
- If assembly OOMs on Pi, reduce `render.target_bitrate` or resolution in `conf/global.yaml`.
- Missing captions binary: ensure `asr.whisper_cpp_path` auto-detects; otherwise set explicit path in config.


