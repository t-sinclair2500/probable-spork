## One-Pi Pipeline — Master Build Plan (Single Source of Truth)

This document consolidates all remaining work across README/PHASE docs and current code state into a single, sequenced plan with clear dependencies, acceptance criteria, and test steps. It supersedes and unifies: `CURSOR_TODO_FULL.txt`, `CURSOR_TASKS_AFTER_PAUSE.txt`, and in-file TODOs.

Legend: [DONE] implemented; [PARTIAL] some functionality present; [TODO] not implemented.

---

### 0) Prerequisites & Ground Rules
- Ensure Pi services installed: Ollama, whisper.cpp, FFmpeg, Python venv.
- All configuration via `conf/global.yaml` and `conf/blog.yaml`; secrets in `.env`.
- Single-lane, lock-aware runs; scripts MUST be idempotent.

Verification
- make install; make check; dry-run once: `make run-once` and `make blog-once`.

---

## Phase A — Shared Ingestion & Authoring

### A1. Trend Ingestion — `bin/niche_trends.py` [PARTIAL]
- Implement real ingestion for YouTube, Google Trends (pytrends), Reddit (PRAW).
- Write normalized rows into `data/trending_topics.db` with backoff on 429/5xx.

Dependencies
- `.env` keys for APIs (if used), internet access.

Acceptance Criteria
- ≥50 rows from last 24h across sources; schema: `{ts, source, title, tags}`.
- Retries/backoffs logged; idempotent (no duplicate floods).

Test Steps
- Run `python bin/niche_trends.py` twice; confirm DB growth only once per run window.
- Inspect last log lines in `jobs/state.jsonl` and spot-check DB.

### A2. Topic Clustering — `bin/llm_cluster.py` [DONE]
- Strict JSON parse, top-10 trimming with timestamps; writes `data/topics_queue.json`.

Test Steps
- `python bin/llm_cluster.py`; verify file exists with ≤10 topics and `created_at`.

### A3. Outline Generation — `bin/llm_outline.py` [DONE]
- Includes tone + target length hints; falls back to usable JSON if LLM fails.

Test Steps
- `python bin/llm_outline.py`; verify `scripts/<date>_*.outline.json` with required keys.

### A4. Script Generation — `bin/llm_script.py` [DONE]
- Generates long-form script with frequent `[B-ROLL: ...]` markers; metadata JSON.

Test Steps
- `python bin/llm_script.py`; verify `.txt` and `.metadata.json` written next to outline.

---

## Phase B — Assets (Critical Path)

### B1. Asset Orchestration — `bin/fetch_assets.py` [DONE]
- Parse latest script’s `[B-ROLL: ...]` markers into search queries.
- For each section, request assets from configured providers up to `assets.max_per_section`.
- Create per-topic folder under `assets/<date>_<slug>/`.
- Persist `license.json` (provider, user/photographer, URL, license terms) and `sources_used.txt`.
- Normalize images/videos to target resolution (downscale if larger; keep aspect).
- Deduplicate by SHA1; skip if already downloaded.

Notes
- Consolidation: implement provider calls inline here or import helpers from `bin/download_assets.py`. Prefer implementing all logic in `fetch_assets.py` and deprecate `download_assets.py`.

Dependencies
- `.env` keys for Pixabay/Pexels if required.
- `conf/global.yaml` → `assets.providers`, `render.resolution`.

Acceptance Criteria
- 10–20 usable assets per ~1000-word script; `license.json` and `sources_used.txt` present.
- Re-run does not re-download existing files (SHA1 dedupe).

Test Steps
- `python bin/fetch_assets.py`; confirm new `assets/<date>_<slug>/` populated with media and license files.

### B2. Provider Downloaders — `bin/download_assets.py` [OPTIONAL]
- If kept: implement `download_pixabay(query, ...)` and `download_pexels(query, ...)` returning normalized file paths + license entries. Otherwise, remove once B1 subsumes.

Acceptance Criteria
- Unit callable functions; robust to empty results; respect rate limits.

---

## Phase C — Voice, Captions, and Assembly

### C1. TTS — `bin/tts_generate.py` [PARTIAL]
- Replace placeholder tone with real TTS:
  - Default: Coqui TTS (voice per config), generate WAV then MP3 via FFmpeg.
  - Optional fallback: OpenAI TTS when enabled in config + key present.
- Normalize loudness (ffmpeg loudnorm), target ~150–175 wpm average.

Dependencies
- `conf/global.yaml` → `tts.*` and `.env` keys if using OpenAI.

Acceptance Criteria
- VO intelligible, no clipping, duration roughly aligns with target length.
- Idempotent: skip regeneration if up-to-date output exists.

Test Steps
- `python bin/tts_generate.py`; inspect `voiceovers/<key>.mp3` duration and loudness.

### C2. Captions — `bin/generate_captions.py` [DONE]
- Already supports whisper.cpp; add:
  - loudness pre-normalization of input (if needed).
  - optional OpenAI Whisper fallback when local fails.
  - log duration, WPM estimate, and (if available) confidence.

Dependencies
- `cfg.asr.whisper_cpp_path` binary and model presence.

Acceptance Criteria
- `.srt` generated next to VO when models present; safe SKIP when missing.
- On failure locally, optional cloud fallback succeeds when enabled.

Test Steps
- `python bin/generate_captions.py -i voiceovers/<key>.mp3`; verify `.srt` exists.

### C3. Video Assembly — `bin/assemble_video.py` [DONE]
- Replace black video with real assembly (MoviePy + FFmpeg):
  - Build timeline from beats (from `prompts/beat_timing.txt` via LLM or `bin.core.estimate_beats`).
  - Place assets per beat; add crossfades (`render.xfade_ms`), simple pan/zoom for stills.
  - Mix background music with sidechain ducking under VO.
  - Export H.264 yuv420p at configured fps/resolution/bitrate.

Dependencies
- Outputs of B1, C1; optional SRT for burn-in when enabled.

Acceptance Criteria
- Final length within ±10% of target; A/V sync within 100ms; no crashes on empty assets.

Test Steps
- `python bin/assemble_video.py`; verify `videos/<key>.mp4` properties via `ffprobe` and manual playback.

### C4. Thumbnail — `bin/make_thumbnail.py` [DONE]
- Generator present; ensure it runs as part of assembly or post-step if enabled.

---

## Phase D — Blog Lane

### D1. Topic Pick — `bin/blog_pick_topics.py` [PARTIAL]
- Add avoidance of repeats within last N days (`blog.avoid_repeat_days`).

Acceptance Criteria
- Skips topics used in the last N days based on `jobs/state.jsonl` or a simple ledger.

### D2. Generate Post — `bin/blog_generate_post.py` [PARTIAL]
- Replace placeholder with LLM rewrite:
  - Respect `blog.tone`, `min_words`, `max_words`, `include_faq`, `inject_cta`.
  - Prefer reusing assets for inline images; emit Markdown with image references.

Acceptance Criteria
- Draft Markdown meets word count; contains H2/H3, bullets, optional FAQ/CTA.

Test Steps
- `python bin/blog_generate_post.py`; inspect `data/cache/post.md` and `post.meta.json`.

### D3. Render HTML — `bin/blog_render_html.py` [DONE]
- Sanitization + schema.org Article JSON-LD injected; attribution when needed.

### D4. SEO Gate — `bin/seo_lint_gate.py` [DONE]
- Add CLI flag `--allow-fail` to bypass gate (returns ok:true with warnings).

Acceptance Criteria
- Exits 1 on violations unless `--allow-fail` used; JSON output with issues.

### D5. Post to WordPress — `bin/blog_post_wp.py` [PARTIAL]
- Implement media upload:
  - Upload featured + inline images to `/wp-json/wp/v2/media`.
  - Attach media to post; set featured image per `featured_image_strategy`.
- Respect DRY_RUN flag from config or env.

Acceptance Criteria
- DRY_RUN prints payload; live returns post ID; images appear in post.

Test Steps
- `python bin/blog_post_wp.py` with DRY_RUN; then with real creds on test site.

### D6. Ping Search — `bin/blog_ping_search.py` [DONE]
- Already pings Google; optionally add Bing if enabled.

---

## Phase E — Upload & Staging

### E1. Stage Upload — `bin/upload_stage.py` [DONE]
- Writes `data/upload_queue.json` entries.

### E2. Optional YouTube Upload — `bin/youtube_upload.py` [TODO/Optional]
- OAuth + upload; dry-run default; chapters from outline.

Acceptance Criteria
- Dry-run prints payload; live returns video ID when enabled.

---

## Phase F — Reliability & Ops

### F1. Guards & Locking — `bin/core.py` + `bin/util.py` [DONE]
- Locking, disk/temp guards, log state with timestamps.

### F2. Health Server — `bin/health_server.py` [DONE]
- Verify systemd service & logrotate config.

### F3. Cron — `crontab.seed.txt` [DONE]
- Ensure steps align with dependency order and are lock-aware.

### F4. Backups — `bin/backup_repo.sh`, `bin/backup_wp.sh` [DONE]
- Validate output archives and schedules.

---

## Phase G — UI & Operator Experience

### G1. Web UI — `bin/web_ui.py` [PARTIAL]
- Add simple password auth (config-driven) and basic HTML pages (templates or inline):
  - Dashboard: last state, queue depths, tail logs.
  - Buttons to trigger steps (reuse `/api/run`).

Acceptance Criteria
- Served at `:8099`, password required if configured; shows real-time info and starts jobs.

Test Steps
- `python bin/web_ui.py`; load UI; trigger a safe step (e.g., outline) and see state update.

---

## Build Sequence (Strict Order Where Required)
1) A1 → A2 → A3 → A4
2) B1 (+B2 if separate)
3) C1 → C2 → C3 → C4
4) D1 → D2 → D3 → D4 → D5 → D6 (Blog lane can run in parallel with C*)
5) E1 → (E2 optional)
6) F* and G* can be executed in parallel as they’re orthogonal.

---

## Acceptance & Test Matrix (High Level)
- End-to-end dry-run completes: one video + one blog post using the same topic in a day.
- Artifacts exist: outline, script, assets, VO, SRT, MP4, thumbnail, staged upload; blog HTML and (optionally) WP post (DRY_RUN).
- Idempotence: re-running any step skips without duplication; logs readable.
- Performance: completes within cron windows on Pi 5 with active cooling and SSD.

---

## Deconflicts vs Previous Docs
- Consolidate assets work into `bin/fetch_assets.py`; deprecate `bin/download_assets.py` (helper-only if kept).
- `generate_captions.py` TODOs merged here (fallback + logging).
- `web_ui.py` expanded scope defined here; cron remains the single scheduler of record.

---

## Tracking Progress
- Update this file with [DONE]/[PARTIAL]/[TODO] tags as features land.
- Each completed item should add or update unit/integration tests where feasible.

---

## Cross-Cutting Clarifications & Cleanups (Discovered in second pass)

### H1. Config Unification & Imports [TODO]
- Standardize on `bin.core.load_config()` (Pydantic models) across all scripts.
- Replace `from util import ...` usages with `from bin.core import ...` or add a thin adapter in `bin/util.py` that simply delegates to `bin.core` until code is migrated.
- Ensure repo root is on `PYTHONPATH` (already in `Makefile`), or add `__init__.py` under `bin/` if needed.

Acceptance
- No scripts import plain `util` anymore; all run via `make run-once` without import errors.

### H2. Secrets & Sources Files [TODO]
- Add `.env.example` to repo with placeholders: `PIXABAY_API_KEY`, `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY`, `OPENAI_API_KEY`.
- Clarify whether `conf/sources.yaml` is used; either wire it into `bin/core.load_env` or remove it from docs. Recommendation: prefer `.env` only.

Acceptance
- `README.md` and `OPERATOR_RUNBOOK.md` reference `.env.example`; `bin/check_env.py` validates presence when providers enabled.

### H3. Dependencies & Requirements [TODO]
- Add missing libs used in code:
  - `soundfile` (or switch placeholder VO to use `scipy.io.wavfile`/`pydub` to avoid extra dep).
  - Coqui TTS (if chosen): add `TTS` package and Pi notes (may be heavy; optional).
- Ensure ARM-friendly pins for Pi.

Acceptance
- `make install` succeeds on Pi; placeholder VO works without missing imports.

### H4. Heavy-Step Guards [TODO]
- Call `bin.core.guard_system(cfg)` at the start of heavy scripts: `tts_generate.py`, `generate_captions.py`, `assemble_video.py`, and asset fetcher.

Acceptance
- When CPU temp > 75°C or disk low, steps defer or exit with logs.

### H5. Fact Pass — `bin/fact_pass.py` [NEW]
- Implement prompt `prompts/fact_check.txt` to emit `<script>.factcheck.json` and optionally rewrite or annotate script.

Acceptance
- Returns `{issues: []}` when none; rewrites or annotates lines when issues found; integrated as optional step in Makefile and cron.

### H6. Beat Timing Prompt Integration [TODO]
- Use `prompts/beat_timing.txt` to produce beat JSON; fall back to `bin.core.estimate_beats`.

Acceptance
- Assembly consumes beats from prompt output when available.

### H7. E2E Test Robustness [TODO]
- Update `bin/test_e2e.py` to tolerate unconfigured providers (e.g., skip assets/captions when keys/binaries missing) while still validating end-to-end flow with placeholders.

Acceptance
- `make test` passes locally without asset keys or whisper.cpp installed, while logging SKIPs.

### H8. Thumbnail Script Cleanup [TODO]
- `bin/make_thumbnail.py` contains duplicate/concatenated code blocks. Refactor into a single clear entry point using metadata title.

Acceptance
- Single, clean implementation; `make run-once` produces a thumbnail PNG next to the MP4.

### H9. Blog DRY_RUN Control & Media Upload [TODO]
- Move `DRY_RUN` constant in `bin/blog_post_wp.py` to config/env (e.g., `BLOG_DRY_RUN=true`).
- Implement media upload and featured image selection per strategy.

Acceptance
- Dry-run controlled without code changes; when enabled, featured image set from assets.

### H10. Provider List Consistency [TODO]
- `conf/global.example.yaml` lists providers `pixabay`, `pexels` but `conf/sources.yaml` includes `unsplash_key`. Decide on Unsplash support and update `assets.providers` + code accordingly.

Acceptance
- Providers list and keys are consistent across config, docs, and code.

---

## Documentation Updates (to keep everything consistent)

### D-Docs.1 README.md [TODO]
- Add instruction to create `.env` from `.env.example`; include list of required/optional keys.
- Clarify Raspberry Pi prerequisites: active cooling recommended; use USB SSD; note ARM-friendly pins.
- Reference `MASTER_TODO.md` as the single source of truth for build tasks.

### D-Docs.2 OPERATOR_RUNBOOK.md [TODO]
- After bootstrap, add `make check` step and interpretation of common warnings (e.g., missing API keys => assets skipped).
- Add a note that heavy steps are lock-aware and may SKIP on resource constraints.

### D-Docs.3 PHASE2_CURSOR.md [TODO]
- Align asset provider plan: decide on Unsplash support; update provider list.
- Add acceptance criteria alignment for captions fallback and assembly specifics.

### D-Docs.4 CURSOR_* files [TODO]
- Mark these as superseded by `MASTER_TODO.md` at the top; point readers there.

### D-Docs.5 conf/* examples [TODO]
- Add `.env.example` file to repo (keys per H2).
- If `conf/sources.yaml` is retained, document how it’s loaded; else remove from docs and repo.

### D-Docs.6 Makefile [TODO]
- Add a `docs` target that echoes where to find `MASTER_TODO.md` and how to run tests.
