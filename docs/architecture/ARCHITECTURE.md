# ⚠️ SUPERSEDED — CURSOR SHARED CORE PIPELINE

**NOTICE**: This file is superseded by current authoritative documentation. Please refer to:
- **`MASTER_TODO.md`** - Current development tasks and priorities
- **`PHASE2_CURSOR.md`** - Updated implementation guide with current status
- **`OPERATOR_RUNBOOK.md`** - Operational procedures and deployment

This file remains for historical reference only.

---

# CURSOR SHARED CORE PIPELINE — Master Prompt (ARCHIVED)

**Goal:** Implement a **shared, core pipeline** that powers multiple outputs from one Raspberry Pi 5:
- **YouTube lane** (video scripts → VO → assets → render → stage/upload)

- (Future lanes: newsletter, static site, data dashboard, digital products)

**Constraints & Principles**
- **Single device** (Pi 5, 8GB). Heavy tasks are **sequential** (single-lane) with lockfile control.
- **One source of truth** for trends, topics, artifacts, and job state.
- **Local-first** stack: Ollama (phi3:mini), whisper.cpp (ASR), Coqui TTS, FFmpeg, MoviePy, Python.
- **Optional cloud fallbacks** are **OFF by default** and require explicit enabling and keys.
- **Operator simplicity:** all knobs in `conf/global.yaml` (video/tone/length/scheduling).
- **Idempotence:** all scripts safe to re-run; existing outputs short-circuit gracefully.
- **Licensing:** all assets tracked; attributions are inserted when required.

---

## 1) Shared Pipeline Architecture

### 1.1 Directory Map (single source of truth)
```
/home/pi/youtube_onepi_pipeline/            # primary pipeline repo
  ├── conf/
  │   ├── global.yaml                       # operator control (tone, length, cadence, toggles)
  │   ├── [archived: sources.yaml]         # API keys now in .env
  │   └── render.yaml                       # video render defaults
  ├── data/
  │   ├── trending_topics.db                # SQLite: raw trend rows (yt/reddit/trends)
  │   ├── topics_queue.json                 # ranked topics
  │   ├── upload_queue.json                 # items staged for upload (yt)
  │   └── cache/                            # cached fetches, embeddings later
  ├── jobs/                                 # unified job control & audit
  │   ├── todo.jsonl
  │   ├── state.jsonl
  │   └── lock
  ├── prompts/                              # LLM prompt library (JSON-only schemas)
  ├── scripts/                              # long-form scripts (text)
  ├── assets/                               # shared media per topic (with license.json)
  ├── voiceovers/                           # VO audio
  ├── videos/                               # final MP4s
  └── bin/                                  # ALL executables for shared + lanes
```

### 1.2 Shared Services
- **LLM Service:** Ollama (phi3:mini), HTTP endpoint at `127.0.0.1:11434`.
- **ASR:** whisper.cpp binary path (`asr.whisper_cpp_path` in config).
- **TTS:** Coqui TTS local (voice & rate in config).
- **Scheduler:** Cron triggers scripts; each script is lock-aware.
- **State & Telemetry:** `jobs/state.jsonl` (ts, step, elapsed_ms, status, notes).

### 1.3 Inter-lane Contracts (JSON Schemas)

**topics_queue.json**
```json
[
  {
    "topic": "AI tools that save time",
    "score": 0.82,
    "hook": "5 tools to reclaim 10 hours/week",
    "keywords": ["ai","productivity","automation"],
    "source_evidence": [{"src":"youtube","title":"...","tags":"..."}],
    "created_at": "2025-08-09T08:30:00Z"
  }
]
```

**outline JSON (saved as*.outline.json)**
```json
{
  "title_options": ["...","..."],
  "sections": [
    {"id":1,"label":"Hook","beats":["...","..."],"broll":["..."]},
    {"id":2,"label":"Point 1","beats":["..."],"broll":["..."]},
    {"id":3,"label":"Point 2","beats":["..."],"broll":["..."]},
    {"id":4,"label":"Point 3","beats":["..."],"broll":["..."]},
    {"id":5,"label":"Recap","beats":["..."],"broll":["..."]},
    {"id":6,"label":"CTA","beats":["..."],"broll":["..."]}
  ],
  "tags": ["...","..."],
  "tone": "informative",
  "target_len_sec": 420
}
```

**script text (`*.txt`)**
- Plain text, conversational sentences, `[B-ROLL: ...]` markers every 2–3 lines.

**metadata JSON (`*.metadata.json`)**
```json
{
  "title": "Final chosen title",
  "description": "Channel appropriate description.",
  "tags": ["...","..."],
  "slug": "final-chosen-title",
  "chapters": [
    {"t": 0, "label": "Hook"}, {"t": 45, "label": "Point 1"}
  ]
}
```

**assets per topic (`assets/<key>/`)**
```
license.json                 # per-batch license info and queries used
sources_used.txt             # URLs & providers
img001.jpg / clip001.mp4 ... # normalized to target resolution where possible
```

**upload_queue.json** (supports both lanes)
```json
[
  {
    "type": "video",
    "file": "/abs/path/to/output.mp4 or html",
    "title": "Title",
    "description": "Desc",
    "tags": ["a","b"],
    "thumbnail": "/abs/path/to/thumbnail.png",
    "target": "youtube",
    "status": "staged|uploaded|failed",
    "extra": {"yt_id": null}
  }
]
```

---

## 2) Shared Components & Responsibilities

### 2.1 Ingestion (shared)
- `bin/niche_trends.py`: fetch YouTube trending by categories, Google Trends for `niches`, Reddit top posts; write to SQLite and cache.
- `bin/llm_cluster.py`: cluster + score topics (strict JSON). Output `topics_queue.json`.

### 2.2 Authoring (shared → diverges per lane)
- `bin/llm_outline.py`: produce outline JSON with b-roll suggestions and target length from config.
- `bin/llm_script.py`: long-form script with `[B-ROLL]` markers.
- `bin/fact_pass.py` (optional): detect risky claims; rewrite or annotate.

### 2.3 Assets (shared)
- `bin/fetch_assets.py`: Pixabay/Pexels; normalize, store licenses; dedupe near-duplicates.
- **Contract:** assets named predictably so both lanes can reuse.

### 2.4 Lane Outputs
- **YouTube lane:** `bin/tts_generate.py`, `bin/generate_captions.py`, `bin/assemble_video.py`, `bin/make_thumbnail.py`, `bin/upload_stage.py` (and optional `bin/youtube_upload.py`).


### 2.5 Reliability
- `bin/healthcheck.py`: temp, disk, model, last step.
- All heavy steps wrapped with `nice/ionice`. Thermal defer when >75°C.

---

## 3) Work Plan for Cursor Agents

### Roles
- **Agent A (Data/Integrations):** ingestion and asset providers.
- **Agent B (LLM/Authoring):** prompts, clustering, outline, scripts, fact pass, beat timing.
- **Agent C (Media):** TTS, ASR, MoviePy, thumbnails.
- **Agent D (Reliability/Ops):** locks, retries, temp checks, logs, config validation.

### Common Guardrails
- **Config first:** everything read from `conf/global.yaml` and `.env`.
- **Strict JSON:** LLM outputs must be parseable; retry strategy in place.
- **Idempotent & lock-aware:** safe to re-run; respect `jobs/lock`.
- **Licensing:** persist provider, URL, and license terms per asset.

---

## 4) Concrete Tasks & Acceptance Criteria

### A) `bin/niche_trends.py` (shared ingestion)
**Tasks**
- Implement YouTube Data API by configured category IDs and region.
- Implement pytrends queries for `pipeline.niches` daily.
- Implement Reddit top/day for configured subreddits (credentials via `.env`).
- Write rows into `data/trending_topics.db` with timestamp, source, title, tags.

**Acceptance**
- ≥50 fresh rows/day; proper backoffs on 429/5xx.
- No hard-coded data left; useful logs in `jobs/state.jsonl`.

---

### B) `bin/llm_cluster.py` (topic scoring)
**Tasks**
- Use `prompts/cluster_topics.txt`; ensure valid JSON (strip code fences, retry on parse errors).
- Compute **score = frequency × velocity × cross-source overlap**; keep top 10.
- Write `data/topics_queue.json` with `created_at` and `source_evidence` array.

**Acceptance**
- Always valid JSON; robust to malformed inputs; clear logs.

---

### C) `bin/llm_outline.py` and `bin/llm_script.py` (authoring)
**Tasks**
- Include tone (`pipeline.tone`) and `target_len_sec` (derived from `video_length_seconds`) into prompts.
- Outline contains 6 sections with beats and b-roll suggestions.
- Script 900–1200 words (or scaled for target length), with frequent `[B-ROLL]` markers.

**Acceptance**
- Outline JSON schema valid; script passes simple lint (no empty output).

---

### D) `bin/fetch_assets.py` (shared assets)
**Tasks**
- Parse `[B-ROLL]` markers into queries; call Pixabay/Pexels; respect `assets.max_per_section`.
- Save assets and `license.json`, `sources_used.txt` per topic folder.
- Normalize to target resolution where possible; downscale images to ≤1280×720 for video.

**Acceptance**
- 10–20 usable assets per script; license data present and accurate.

---

### E) YouTube lane
**TTS — `bin/tts_generate.py`**
- Coqui TTS (voice in config); normalize loudness; ~150–175 wpm; MP3/WAV.
- Optional OpenAI TTS fallback when enabled.

**ASR — `bin/generate_captions.py`**
- whisper.cpp (path in config) to produce SRT; optional OpenAI fallback.
- Burn-in optional via FFmpeg depending on `pipeline.enable_captions`.

**Assembly — `bin/assemble_video.py`**
- Use `prompts/beat_timing.txt` (or deterministic heuristic) for durations.
- MoviePy/FFmpeg: crossfades, pan/zoom, music ducking, export H.264 yuv420p.
- Thumbnail — `bin/make_thumbnail.py` (Pillow).

**Acceptance**
- Final video ±10% target length, A/V sync ≤100ms; caption SRT present; thumbnail generated.

---



---

### G) Reliability / Ops
**Tasks**
- Wrap FFmpeg/whisper calls with `nice/ionice`.
- Thermal defer when `vcgencmd` > 75°C (sleep & retry).
- Add `elapsed_ms` to every `jobs/state.jsonl` entry.
- Improve `bin/healthcheck.py` to report last successful steps and queue depths.

**Acceptance**
- 3 consecutive unattended daily runs without intervention.

---

## 5) Scheduling (cron): Shared + Lanes
Trigger windows may be adjusted; each script **exits early** if lock present.

```
30 7  * * *  python bin/niche_trends.py
45 8  * * *  python bin/llm_cluster.py

# YouTube lane
30 9  * * *  python bin/llm_outline.py
45 9  * * *  python bin/llm_script.py
0  12 * * *  python bin/fetch_assets.py
30 12 * * *  python bin/tts_generate.py
0  13 * * *  python bin/generate_captions.py
30 13 * * *  python bin/assemble_video.py
0  14 * * *  python bin/upload_stage.py



# Health
0  *  * * *  python bin/healthcheck.py
```

> All commands should be run via the repo’s venv in production crontab; adapt paths accordingly.

---

## 6) Testing & Sign-off

- **Dry-run E2E:** produce one video using the same topic in a day.
- **Validation:** presence of assets, license files, SRT captions, thumbnail, SEO fields, and upload_queue entries.
- **Idempotence:** re-running any step does not duplicate artifacts; instead it skips with “already exists” logs.
- **Performance:** daily completion within allotted windows on Pi 5 with active cooling and SSD swap.


---

## 7) Definition of Done (Shared Core)
- Stable ingestion and clustering with real APIs.
- Authoring produces valid outlines and scripts respecting tone/length.
- Shared assets downloaded with license metadata.
- YouTube lane can independently consume shared artifacts.
- Healthcheck and logs indicate success; 3 days of unattended runs pass.
