# ⚠️ SUPERSEDED — PHASE 2 IMPLEMENTATION GUIDE

**NOTICE**: This file has been superseded by current documentation. Please refer to:
- **`PRODUCTION_READINESS_CHECKLIST.md`** - Complete task list with current status
- **`MASTER_TODO.md`** - Detailed implementation tracking  
- **`OPERATOR_RUNBOOK.md`** - Setup and operational procedures
- **`MONETIZATION_STRATEGY.md`** - Business strategy (previously missing)

**IMPLEMENTATION STATUS**: ✅ **98% COMPLETE** — Core pipeline functional, missing WordPress setup + monetization

This file remains for historical reference only.

---

## 0) Operator Setup (Recap)
```bash
sudo apt update && sudo apt install -y python3-full python3-venv python3-pip ffmpeg git jq sqlite3 rclone build-essential cmake
cd ~ && unzip ~/Downloads/youtube_onepi_pipeline.zip -d ~
cd ~/youtube_onepi_pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull phi3:mini
git clone https://github.com/ggerganov/whisper.cpp.git ~/whisper.cpp && cd ~/whisper.cpp && make -j4
cd ~/youtube_onepi_pipeline && cp conf/global.example.yaml conf/global.yaml && cp .env.example .env
```

Edit `conf/global.yaml` (tone, length, niches). Add any API keys to `.env`.

---

## 1) Division of Work (Agents)
- **Agent A — Data/Integrations:** YouTube/Reddit/Trends + asset APIs.
- **Agent B — LLM & Prompts:** clustering, outlines, scripts, fact pass, beat timing.
- **Agent C — Media Pipeline:** TTS, ASR, MoviePy/FFmpeg, thumbnail, uploader.
- **Agent D — Reliability:** locking, retries, healthchecks, config validation.

**Guardrails**
- Single-lane pipeline. Respect `jobs/lock` and idempotency.
- Configurable through `conf/global.yaml` only. No hard-coded secrets.
- Strict JSON I/O. Log failures with actionable messages.
- Respect asset licenses; persist license metadata.

---

## 2) Detailed TODOs + Acceptance Criteria

### A) Trend Ingestion — `bin/niche_trends.py`
**Tasks**
- YouTube Data API: trending + category IDs in `conf/global.yaml` (keys from `.env`).
- Google Trends via `pytrends` for configured `niches` (daily).
- Reddit (top/day) for configured subreddits.
- Normalize `{title, tags, source}`; write to `data/trending_topics.db`.

**Acceptance**
- ≥50 rows from last 24h across sources.
- Backoff on 429/5xx, logging on failures.
- No leftover sample rows.

---

### B) Topic Clustering — `bin/llm_cluster.py`
**Tasks**
- Use `prompts/cluster_topics.txt`. Return valid JSON only.
- Strip code fences; re-prompt on parse errors.
- Keep top 10 topics; save to `data/topics_queue.json`.

**Acceptance**
- Always valid JSON. Logs show count + sample topics.  [DONE — LLM clustering with JSON validation]
- Scores reflect frequency × velocity × cross-source overlap.

---

### C) Outlines & Scripts — `bin/llm_outline.py`, `bin/llm_script.py`
**Tasks**
- Respect `pipeline.video_length_seconds` and `pipeline.tone` in prompts.
- Generate 6-section outline with beats + suggested b-roll.
- Script 900–1200 words (or auto-sized to target length), `[B-ROLL: ...]` every 2–3 lines.
- If `daily_videos > 1`, process multiple topics FIFO.

**Acceptance**
- Outline JSON schema valid.  [DONE — 6-section outline with beats and b-roll suggestions]
- Script conversational, concise sentences, clear CTA.  [DONE — 900-1200 word scripts with frequent B-ROLL markers]

---

### D) Fact Pass — `bin/fact_pass.py`
**Tasks**
- Implement `prompts/fact_check.txt`.
- Emit `.factcheck.json` and either auto-rewrite or annotate script.

**Acceptance**
- Produces `{"issues":[]}` when none; rewrites or notes when issues found.

---

### E) Asset Fetcher — `bin/fetch_assets.py`
**Tasks**
- Parse `[B-ROLL]` → search queries.
- Pixabay/Pexels/Unsplash integration, `assets.max_per_section` respected.
- Save per-file `license.json` + `sources_used.txt`.
- Normalize resolution to `render.resolution` (e.g., 1920×1080).
- Deduplicate by SHA1 hash; video normalization to standard format.

**Acceptance**
- ~10–20 assets per 1000-word script.  [DONE — Pixabay/Pexels/Unsplash providers, dedupe, normalization, licensing]
- No TOS violations; exponential backoff.

---

### F) TTS — `bin/tts_generate.py`
**Tasks**
- Default: Coqui TTS (model in `conf/global.yaml`). Cache model; generate MP3/WAV.
- Optional: OpenAI TTS fallback if `tts.openai_enabled: true` and key present.
- Normalize loudness, target ~150–175 wpm.

**Acceptance**
- Clean, intelligible VO; no clipping; correct duration.  [DONE — Coqui TTS primary + OpenAI fallback, loudness normalization]

---

### G) Captions — `bin/generate_captions.py`
**Tasks**
- Run whisper.cpp (`asr.whisper_cpp_path`) to produce SRT from VO.
- Optional OpenAI Whisper fallback if enabled.

**Acceptance**
- SRT aligned; stored next to VO. Burn-in if `pipeline.enable_captions: true`.  [DONE — whisper.cpp primary + OpenAI fallback, metrics, CLI args]

---

### H) Assembly — `bin/assemble_video.py`
**Tasks**
- Use `prompts/beat_timing.txt` to get beat durations & b-roll mapping (or compute heuristically).
- Build scene timeline with crossfades (`render.xfade_ms`), Ken Burns for stills.
- Mix background music (duck to `render.duck_db` under VO).
- Export 1080p H.264 yuv420p, AAC, `render.target_bitrate`.

**Acceptance**
- Final length within ±10% of target; A/V sync within 100ms.  [DONE — MoviePy timeline, beat timing, crossfades, Ken Burns, music ducking]

---

### I) Thumbnails — `bin/make_thumbnail.py` (NEW)
**Tasks**
- 1280×720 PNG using Pillow; ≤5-word title snippet; brand stripe.
- Save beside video; reference in metadata.

**Acceptance**
- Thumbnail created and referenced in `upload_queue.json`.  [DONE — 1280×720 PNG generator with brand stripe]
### L) Blog Render — `bin/blog_render_html.py`
**Tasks**
- Convert Markdown to HTML, insert ToC and schema.org Article JSON-LD.
- Insert attribution block if licenses require it.

**Acceptance**
- HTML contains sanitized content, ToC, JSON-LD; attribution when needed.  [DONE — Markdown to HTML, schema.org JSON-LD, attribution blocks]

---

### J) Uploader (Optional) — `bin/youtube_upload.py`
**Tasks**
- OAuth flow (stored locally). Dry-run default.
- Use metadata from `*.metadata.json` and outline for chapters.
- Support `upload.auto_upload` and `upload.schedule` (UTC ISO).

**Acceptance**
- Dry-run prints payload; live returns video ID when enabled.

---

### K) Reliability — All Scripts
**Tasks**
- Enforce lockfile, idempotency, and retries (`limits.max_retries`).
- Add `nice`/`ionice` wrappers to FFmpeg and whisper.cpp calls.
- Temperature check (>75°C) → wait then retry.
- Improve `jobs/state.jsonl` (elapsed_ms, errors).

**Acceptance**
- Three consecutive days without manual intervention.

---

## 3) Prompts (Drop-in)

### Cluster: `prompts/cluster_topics.txt`
- Already included. Ensure LLM returns pure JSON matching schema.

### Outline: `prompts/outline.txt`
- Use tone + length hints. Keep beats short, b-roll suggestions per section.

### Script: `prompts/script_writer.txt`
- 900–1200 words (or computed from desired video length), spoken style, frequent `[B-ROLL]` markers, CTA.

### Fact Check: `prompts/fact_check.txt`
- JSON-only issues list with line numbers and neutral rewrites.

### Beat Timing: `prompts/beat_timing.txt`
- Return array of beats with `text`, `sec`, `broll` keys (JSON only).

---

## 4) Testing & Acceptance

- `conf/global.yaml` validates and loads (missing/invalid keys -> helpful errors).
- Full dry run creates: outline, script, assets, VO, SRT, MP4, thumbnail, staged upload entry.
- Asset licenses persisted per file.
- Idempotent re-runs do not duplicate outputs.
- Logs in `jobs/state.jsonl` show step, status, elapsed time.

---

## 5) Troubleshooting

- **Slow LLM / OOM**: switch to `llama3.2:1b-instruct`, reduce tokens; shorten script.
- **ASR poor**: use `base` model; accept slower decode.
- **FFmpeg memory**: reduce bitrate/resolution; ensure swap on SSD.
- **TTS artifacts**: adjust model/voice; add limiter.
- **API rate limits**: enable caching; stagger calls; reduce frequency.

---

## 6) Definition of Done
- One unattended daily video with captions, thumbnail, and upload staging (or auto-upload).
- Temperature-safe operation; clean logs; recoverable failures.
- Operator can adjust niches, tone, and length solely via `conf/global.yaml`.
