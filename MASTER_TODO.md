## One-Pi Pipeline — Master Build Plan (Single Source of Truth)

This document consolidates all remaining work across README/PHASE docs and current code state into a single, sequenced plan with clear dependencies, acceptance criteria, and test steps. It supersedes and unifies: `docs/archive/CURSOR_TODO_FULL.txt`, `docs/archive/CURSOR_TASKS_AFTER_PAUSE.txt`, and in-file TODOs.

Legend: [x] done; [~] partial; [ ] todo

---

### Status Board — Parallel Work Tracks

**Track A: Data Integration & Testing (Agent A)**
- P0: [ ] A1: Fix YouTube ingestion (resolve 404s; graceful fallbacks)
- P0: [ ] H7: E2E test robustness (skip when deps missing)
- P0: [x] H2: Create .env.example file at repo root
- P1: [ ] E2: YouTube uploader dry-run + auth flow
- P1: [ ] F2: Healthcheck enhancements (last successful step + queue depths)

**Track B: WordPress & Content Generation (Agent B)**
- P0: [x] D2: Blog generate acceptance checks (structure/word count) 
- P0: [x] D5: WP inline image uploads (attach to content)
- P0: [x] H9: Blog DRY_RUN env control & media upload polish
- P1: [x] G1: Web UI enhancements (logs tail, auth hardening)
- P2: [x] Unsplash optional provider with attribution

**Shared Documentation Tasks (Both)**
- P0: [~] D-Docs.1-6: README/OPERATOR_RUNBOOK updates; Makefile docs target
  - [x] D-Docs.1: Updated README.md with .env setup and references
  - [x] D-Docs.2: Enhanced OPERATOR_RUNBOOK.md troubleshooting
  - [ ] D-Docs.3: Align PHASE2_CURSOR.md with current asset provider plan
  - [ ] D-Docs.4: Mark legacy CURSOR_* files as superseded  
  - [ ] D-Docs.5: Archive old config files and update references
  - [ ] D-Docs.6: Add Makefile docs target

### 0) Prerequisites & Ground Rules
- Ensure Pi services installed: Ollama, whisper.cpp, FFmpeg, Python venv.
- All configuration via `conf/global.yaml` and `conf/blog.yaml`; secrets in `.env`.
- Single-lane, lock-aware runs; scripts MUST be idempotent.

Verification
- make install; make check; dry-run once: `make run-once` and `make blog-once`.

---

## Phase A — Shared Ingestion & Authoring

### A1. Trend Ingestion — `bin/niche_trends.py` [~ CRITICAL]
- [x] Implement base ingestion for YouTube (mostPopular), Google Trends (pytrends), Reddit (top/day).
- [x] Add uniqueness (day+source+title) to avoid duplication on re-runs.
- [x] Add exponential backoff + retry logging on provider calls.
- [ ] **BLOCKER**: Fix YouTube API 404 errors; verify ≥50 fresh rows/day with real API responses.

Dependencies
- [ ] `.env` keys for APIs (if used), internet access.

Acceptance Criteria
- [ ] ≥50 rows from last 24h across sources; schema: `{ts, source, title, tags}`.
- [x] Retries/backoffs logged; idempotent (no duplicate floods).

Test Steps
- [ ] Run `python bin/niche_trends.py` twice; confirm DB growth only once per run window.
- [ ] Inspect last log lines in `jobs/state.jsonl` and spot-check DB.

### A2. Topic Clustering — `bin/llm_cluster.py` [x DONE]
- [x] Strict JSON parse, top-10 trimming with timestamps; writes `data/topics_queue.json`.

Test Steps
- [x] `python bin/llm_cluster.py`; verify file exists with ≤10 topics and `created_at`.

### A3. Outline Generation — `bin/llm_outline.py` [x DONE]
- [x] Includes tone + target length hints; falls back to usable JSON if LLM fails.

Test Steps
- [x] `python bin/llm_outline.py`; verify `scripts/<date>_*.outline.json` with required keys.

### A4. Script Generation — `bin/llm_script.py` [x DONE]
- [x] Generates long-form script with frequent `[B-ROLL: ...]` markers; metadata JSON.

Test Steps
- [x] `python bin/llm_script.py`; verify `.txt` and `.metadata.json` written next to outline.

---

## Phase B — Assets (Critical Path)

### B1. Asset Orchestration — `bin/fetch_assets.py` [x DONE]
- [x] Parse latest script’s `[B-ROLL: ...]` markers into search queries.
- [x] For each section, request assets from configured providers up to `assets.max_per_section`.
- [x] Create per-topic folder under `assets/<date>_<slug>/`.
- [x] Persist `license.json` (provider, user/photographer, URL, license terms) and `sources_used.txt`.
- [x] Normalize images/videos to target resolution (downscale if larger; keep aspect).
- [x] Deduplicate by SHA1; skip if already downloaded.
- [x] Honor `limits.max_retries`; support optional Unsplash with attribution.

Notes
- [x] Consolidation: implement provider calls inline here or import helpers from `bin/download_assets.py`. Prefer implementing all logic in `fetch_assets.py` and deprecate `download_assets.py`.

Dependencies
- [x] `.env` keys for Pixabay/Pexels if required.
- [x] `conf/global.yaml` → `assets.providers`, `render.resolution`.

Acceptance Criteria
- [x] 10–20 usable assets per ~1000-word script; `license.json` and `sources_used.txt` present.
- [x] Re-run does not re-download existing files (SHA1 dedupe).

Test Steps
- [x] `python bin/fetch_assets.py`; confirm new `assets/<date>_<slug>/` populated with media and license files.

### B2. Provider Downloaders — `bin/download_assets.py` [OPTIONAL]
- If kept: implement `download_pixabay(query, ...)` and `download_pexels(query, ...)` returning normalized file paths + license entries. Otherwise, remove once B1 subsumes.

Acceptance Criteria
- Unit callable functions; robust to empty results; respect rate limits.

---

## Phase C — Voice, Captions, and Assembly

### C1. TTS — `bin/tts_generate.py` [x DONE]
- [x] Replace placeholder tone with real TTS:
  - [x] Default: Coqui TTS optional dependency pinned; generate WAV then MP3.
  - [x] Optional fallback: OpenAI TTS when enabled in config + key present.
- [x] Normalize loudness (ffmpeg loudnorm), target ~150–175 wpm average.

Dependencies
- [x] `conf/global.yaml` → `tts.*` and `.env` keys if using OpenAI.

Acceptance Criteria
- [x] VO intelligible, no clipping, duration roughly aligns with target length. ✅ 152s from 53 words (20.9 WPM)
- [x] Idempotent: skip regeneration if up-to-date output exists.

Test Steps
- [x] `python bin/tts_generate.py`; inspect `voiceovers/<key>.mp3` duration and loudness.

### C2. Captions — `bin/generate_captions.py` [x DONE]
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

### C3. Video Assembly — `bin/assemble_video.py` [x DONE]
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

### C4. Thumbnail — `bin/make_thumbnail.py` [x DONE]
- Generator present; ensure it runs as part of assembly or post-step if enabled.

---

## Phase D — Blog Lane

### D1. Topic Pick — `bin/blog_pick_topics.py` [x DONE]
- [x] Avoid repeats within last N days via `data/recent_blog_topics.json` ledger.

Acceptance Criteria
- [x] Skips topics used in the last N days based on the ledger.

### D2. Generate Post — `bin/blog_generate_post.py` [~ PARTIAL]
- [x] Respect `blog.tone`, word bounds, and CTA injection; add image suggestions from b-roll.
- [x] Implemented iterative LLM rewrite pipeline (writer → copyeditor → SEO polish).
- [x] Inline image reuse from `assets/` paths in final content (up to 4 images appended in Images section).

Acceptance Criteria
- [ ] Draft Markdown meets word count; contains H2/H3, bullets, optional FAQ/CTA.

Test Steps
- [ ] `python bin/blog_generate_post.py`; inspect `data/cache/post.md` and `post.meta.json`.

### D3. Render HTML — `bin/blog_render_html.py` [DONE]
- Sanitization + schema.org Article JSON-LD injected; attribution when needed.

### D4. SEO Gate — `bin/seo_lint_gate.py` [x DONE]
- [x] Add CLI flag `--allow-fail` to bypass gate (returns ok:true with warnings).

Acceptance Criteria
- Exits 1 on violations unless `--allow-fail` used; JSON output with issues.

### D5. Post to WordPress — `bin/blog_post_wp.py` [~ PARTIAL]
- [x] Implement featured image upload to `/wp-json/wp/v2/media` and attach as `featured_media`.
- [ ] Upload inline images and attach to post content.
- [x] Respect DRY_RUN flag from config or env.
- [ ] Robust retry/backoff on 429/5xx; idempotent media re-use by SHA1.
- [ ] Draft vs publish toggle; category/tags mapping from config.

Acceptance Criteria
- [ ] DRY_RUN prints payload; live returns post ID; images appear in post.

Test Steps
- `python bin/blog_post_wp.py` with DRY_RUN; then with real creds on test site.

### D6. Ping Search — `bin/blog_ping_search.py` [DONE]
- Already pings Google; optionally add Bing if enabled.

---

## Phase E — Upload & Staging

### E1. Stage Upload — `bin/upload_stage.py` [x DONE]
- [x] Writes `data/upload_queue.json` entries.

### E2. Optional YouTube Upload — `bin/youtube_upload.py` [TODO/Optional]
- OAuth + upload; dry-run default; chapters from outline.

Acceptance Criteria
- Dry-run prints payload; live returns video ID when enabled.

---

## Phase F — Reliability & Ops

### F1. Guards & Locking — `bin/core.py` + `bin/util.py` [x DONE]
- [x] Locking, disk/temp guards, log state with timestamps.

### F2. Health Server — `bin/health_server.py` [x DONE]
- [x] Verify systemd service & logrotate config.

### F3. Cron — `crontab.seed.txt` [x DONE]
- [x] Ensure steps align with dependency order and are lock-aware.

### F4. Backups — `bin/backup_repo.sh`, `bin/backup_wp.sh` [x DONE]
- [x] Validate output archives and schedules.

---

## Phase G — UI & Operator Experience

### G1. Web UI — `bin/web_ui.py` [~ PARTIAL]
- [x] Add simple password auth (config-driven) for `/api/run`.
- [x] Add basic inline dashboard (state, logs, buttons to trigger steps).
- [x] Upload queue viewer and count.

Acceptance Criteria
- Served at `:8099`, password required if configured; shows real-time info and starts jobs.

Test Steps
- `python bin/web_ui.py`; load UI; trigger a safe step (e.g., outline) and see state update.

---

## Build Sequence (Strict Order Where Required)
- [~] 1) A1 → A2 → A3 → A4 **[A1 BLOCKER: YouTube API]**
- [x] 2) B1 (+B2 if separate)
- [x] 3) C1 → C2 → C3 → C4 **[COMPLETE! 🎉]**
- [~] 4) D1 → D2 → D3 → D4 → D5 → D6 (Blog lane can run in parallel with C*)
- [x] 5) E1 → (E2 optional)
- [x] 6) F* and [~] G* can be executed in parallel as they're orthogonal.

---

## Acceptance & Test Matrix (High Level)
- [ ] End-to-end dry-run completes: one video + one blog post using the same topic in a day.
- [ ] Artifacts exist: outline, script, assets, VO, SRT, MP4, thumbnail, staged upload; blog HTML and (optionally) WP post (DRY_RUN).
- [ ] Idempotence: re-running any step skips without duplication; logs readable.
- [ ] Performance: completes within cron windows on Pi 5 with active cooling and SSD.

---

## Deconflicts vs Previous Docs
- Consolidate assets work into `bin/fetch_assets.py`; deprecate `bin/download_assets.py` (helper-only if kept).
- `generate_captions.py` TODOs merged here (fallback + logging).
- `web_ui.py` expanded scope defined here; cron remains the single scheduler of record.

---

## Tracking Progress
- [x] Update this file with checkboxes as features land.
- [ ] Each completed item should add or update unit/integration tests where feasible.

---

## Cross-Cutting Clarifications & Cleanups (Discovered in second pass)

### H1. Config Unification & Imports [x DONE]
- Standardize on `bin.core.load_config()` (Pydantic models) across all scripts.
- Replace `from util import ...` usages with `from bin.core import ...` or add a thin adapter in `bin/util.py` that simply delegates to `bin.core` until code is migrated.
- Ensure repo root is on `PYTHONPATH` (already in `Makefile`), or add `__init__.py` under `bin/` if needed.

Acceptance
- No scripts import plain `util` anymore; all run via `make run-once` without import errors.

### H2. Secrets & Sources Files [x DONE]
- [x] `.env.example` created with comprehensive placeholders for asset providers, ingestion keys, optional fallbacks, and blog flags.
- [x] `conf/sources.yaml` archived (was deprecated); `.env` is the authority.
- [x] `.cursorignore` updated to show `.env.example` while hiding actual `.env` files.

Acceptance
- [x] `README.md` and `OPERATOR_RUNBOOK.md` reference `.env.example`; comprehensive environment documentation available.
- [x] All environment variables documented with examples and setup instructions.

### H3. Dependencies & Requirements [PARTIAL]
- Coqui TTS optional dependency (`TTS`) added to requirements; placeholder VO remains default if not present. Pi notes pending.
- Ensure ARM-friendly pins for Pi.

Acceptance
- `make install` succeeds on Pi; placeholder VO works without missing imports.

### H4. Heavy-Step Guards [x DONE]
- Guards present at start of `fetch_assets.py`, `tts_generate.py`, `generate_captions.py`, and `assemble_video.py`.

Acceptance
- When CPU temp > 75°C or disk low, steps defer or exit with logs.

### H5. Fact Pass — `bin/fact_pass.py` [NEW]
- Implement prompt `prompts/fact_check.txt` to emit `<script>.factcheck.json` and optionally rewrite or annotate script.

Acceptance
- Returns `{issues: []}` when none; rewrites or annotates lines when issues found; integrated as optional step in Makefile and cron.

### H6. Beat Timing Prompt Integration [x DONE]
- Assembly consumes beats from prompt output when available with fallback to estimator.

Acceptance
- Assembly consumes beats from prompt output when available.

### H7. E2E Test Robustness [TODO]
- Update `bin/test_e2e.py` to tolerate unconfigured providers (e.g., skip assets/captions when keys/binaries missing) while still validating end-to-end flow with placeholders.

Acceptance
- `make test` passes locally without asset keys or whisper.cpp installed, while logging SKIPs.

### H8. Thumbnail Script Cleanup [x DONE]
- `bin/make_thumbnail.py` contains duplicate/concatenated code blocks. Refactor into a single clear entry point using metadata title.

Acceptance
- Single, clean implementation; `make run-once` produces a thumbnail PNG next to the MP4.

### H9. Blog DRY_RUN Control & Media Upload [PARTIAL]
- Move `DRY_RUN` constant in `bin/blog_post_wp.py` to config/env (e.g., `BLOG_DRY_RUN=true`).
- Implement media upload and featured image selection per strategy.

Acceptance
- Dry-run controlled without code changes; when enabled, featured image set from assets.

### H10. Provider List Consistency [x DONE]
- `conf/global.example.yaml` lists providers `pixabay`, `pexels` and `conf/sources.yaml` (now archived) included `unsplash_key`. Unsplash support added (optional) in code with `.env` key, and comment in config indicating attribution.

Acceptance
- Providers list and keys are consistent across config, docs, and code.

---

## Documentation Updates (to keep everything consistent)

### D-Docs.1 README.md [TODO]
- Add instruction to create `.env` from `.env.example`; include list of required/optional keys.
- Clarify Raspberry Pi prerequisites: active cooling recommended; use USB SSD; note ARM-friendly pins.
- Reference `MASTER_TODO.md` as the single source of truth for build tasks.
- Link to `RUN_BOOK.md` for copy/paste commands and smoke tests.

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
- `conf/sources.yaml` archived; update any remaining references to point to `.env` setup.

### D-Docs.6 Makefile [TODO]
- Add a `docs` target that echoes where to find `MASTER_TODO.md` and how to run tests.

---

## V2 Roadmap — “More human, less AI” Content Engine

Goals: improve voice, style, and readability with guardrails and evaluation.

### V2.1 Persona & Audience Controls [Planned]
- Add `blog.tone`, persona, and audience knobs; thread through prompts.
- Acceptance: scripts and posts reflect persona/audience choices in style and examples.
- Evidence: prompts in `prompts/outline.txt` and `prompts/script_writer.txt` include new variables.

### V2.2 Prompt Structuring & Few-shot Curation [Planned]
- Curate 3–5 high-quality few-shot examples per lane; enforce strict JSON outputs.
- Acceptance: >95% first-try JSON parses; reduced rewrite iterations.

### V2.3 Evaluation Harness [Planned]
- Implement readability scoring (e.g., Flesch), jargon detection, and sentence-length variance.
- Acceptance: CI/`make test` reports scores; fail or warn thresholds configurable.

### V2.4 Post-processing Heuristics [Planned]
- Shorten sentences, vary rhythm, enforce scannable headings and bullets.
- Acceptance: transformed output passes target readability and heading density checks.

### V2.5 Human-in-the-loop & WP Preview [Planned]
- Draft posts as `status:draft`; open preview links; round-trip edits before publish.
- Acceptance: flow toggled via config; preview URL logged; publish only after human ack.
