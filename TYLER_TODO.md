## Tyler TODO — Keys, Where to Put Them, What To Run

Use this as your quick checklist to get the pipeline running end-to-end on your machines and the Pi.

### 1) API keys and secrets
- Assets (required for real downloads)
  - PIXABAY_API_KEY → put in `.env`
  - PEXELS_API_KEY → put in `.env`
  - (Optional) UNSPLASH_ACCESS_KEY → `.env` (only if we add Unsplash later)

- Optional fallbacks (enable only if you want cloud usage)
  - OPENAI_API_KEY → `.env` (used for future TTS/Whisper fallbacks)

- WordPress (blog lane live posting)
  - Keep WordPress credentials in `conf/blog.yaml` (poster user + Application Password)
  - Dry-run is controlled by env `BLOG_DRY_RUN=true` in `.env` (defaults to true)

### 2) Where to plug them in
- Create `.env` at repo root (copy from `.env.example` if present on your machine)
  - PIXABAY_API_KEY=...
  - PEXELS_API_KEY=...
  - OPENAI_API_KEY=... (optional)
  - BLOG_DRY_RUN=true

- Configure blog settings in `conf/blog.yaml` (copied from `conf/blog.example.yaml`)
  - `wordpress.base_url`, `api_user`, `api_app_password`, categories/tags

- Confirm global knobs in `conf/global.yaml`
  - `assets.providers: ["pixabay","pexels"]`
  - `pipeline.tone`, `pipeline.video_length_seconds` etc.

### 3) After keys are in place
- Local smoke
  - `make install` (first time)
  - `make check` (verifies keys and config)
  - `make run-once` (end-to-end with assets, TTS placeholder/Coqui, captions if whisper.cpp installed)

- On the Pi
  - `make pi-deploy` (pulls main, installs deps, runs env check)
  - `make pi-run-once` (single run)
  - Health: `make pi-health` or visit `http://<pi>:8088/health`

### 4) System prerequisites on the Pi
- FFmpeg installed (apt)
- whisper.cpp built if you want captions (skip gracefully if missing)
  - `git clone https://github.com/ggerganov/whisper.cpp.git ~/whisper.cpp && cd ~/whisper.cpp && make -j4`
  - Place model under `~/whisper.cpp/models/` (e.g., `ggml-base.en.bin`)
- Optional Coqui TTS for real local TTS (can run with placeholder tone otherwise)

### 5) Validating the media and assets
- Assets: After `bin/fetch_assets.py`, look in `assets/<date>_<slug>/`
  - Confirm images/videos present; `license.json` and `sources_used.txt` exist
- Video: After `bin/assemble_video.py`, check `videos/<date>_<slug>.mp4`
  - Verify playable, correct length range, audio present
- Captions: `voiceovers/<date>_<slug>.srt` if whisper.cpp available

### 6) Moving beyond dry-run
- Blog live posting
  - Set `BLOG_DRY_RUN=false` in `.env`
  - Ensure `conf/blog.yaml` points to your WP site and poster credentials are correct
  - Run `make blog-once`

### 7) Nice-to-have next keys (for ingestion)
- YouTube Data API v3 key (planned for real trend ingestion)
- Reddit: `client_id`, `client_secret`, `user_agent` (planned)
- Google Trends: no key (uses pytrends)

### 8) Run order reminders
- YouTube lane: outline → script → assets → TTS → captions → assemble → thumbnail → stage
- Blog lane: pick → generate → render → SEO gate → post → ping


