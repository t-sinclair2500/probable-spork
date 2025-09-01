# Codex Greenlight Plan — Probable Spork (Local-First Video Pipeline)

This document is a comprehensive, pragmatic plan to take the current repository to a greenlit 10/10, Mac‑first, local‑only, one‑command video pipeline—with a clear path to **11/10 monetizable quality**—that: researches (or ingests research), writes an outline and script, grounds/fact‑checks, plans a storyboard with an MCM design language, renders animatics, generates & mixes audio, assembles a full video with captions and thumbnail, and stages/publishes to YouTube when enabled.

It is intentionally opinionated and action‑oriented. It assumes primary development/operation on a Mac M2 8GB laptop, with Raspberry Pi 5 support retained as a secondary profile.

---

## Vision & Success Criteria

- Simple operator experience: one command to go from topic to finished video.
- Deterministic, idempotent runs: re‑runs with same seed produce same outputs.
- Local‑first: no external SaaS required; optional live research and YouTube publish are explicit toggles.
- Cohesive design language: distinctive MCM/studio look with legibility and accessibility baked in.
- Healthy performance on M2 8GB: sequential by default, bounded resource usage, HW accel for encode.
- Observability: clear logs, artifacts, and QA checks at every stage.
- Monetization-ready quality gates: explicit PASS thresholds for audio (-14 ±0.5 LUFS, ≤ -1.5 dBTP, LRA ≤ 11), visual legibility (WCAG AA ≥ 4.5:1, text inside title/action safe), and claims (fact-guard = block on unresolved).
- Premium voice lane: toggleable local vs premium TTS (SSML-style prosody tags, post-TTS dynamics chain) for publish runs.

---

## Target Platform & Profiles

- Primary: macOS (Apple Silicon M2 8GB)
  - Video encode: `h264_videotoolbox` (hardware acceleration)
  - LLM: Ollama (`llama3.2:3b` minimum)
  - Speech: Piper by default; Whisper for captions (local)
- Secondary: Raspberry Pi 5 (8GB)
  - Keep sequential execution and low‑footprint defaults.

Action: keep `conf/m2_8gb_optimized.yaml` as primary (Mac M2 8GB); add `conf/pi_8gb.yaml` as secondary; update README with Mac-first guidance, enable modest concurrency (e.g., `max_concurrent_renders: 2`) and reduce `pacing_cooldown_seconds` to 10–20s on Mac.

---

## Operator Experience (Golden Path)

- CLI: `./venv/bin/python bin/run_pipeline.py --brief conf/brief.yaml --yt-only`
- Acceptance gate: `make accept` (or UI button) runs the acceptance harness and must PASS before staging/publish.
- Minimal inputs: topic or brief; optional research mode (reuse/live) and assets seed.
- Outputs: `videos/<slug>_cc.mp4`, `videos/<slug>.metadata.json`, `assets/<slug>_animatics/*.mp4`, `voiceovers/<slug>.mp3/.srt`, `scenescripts/<slug>.json`.
- Optional: `bin/youtube_upload.py` to publish (off by default).

---

## Current State — High-Level Findings

- Orchestrator: robust skeleton, but brittle slug/brief handling and lane‑flag semantics; ingestion always tried unless `from-step` set.
- Config fragmentation: research policy split between `research.yaml` and `models.yaml`; mixed pydantic vs dict access.
- LLM client duplication (`model_runner.py` vs `llm_client.py`); per‑request timeouts missing.
- Research: reuse mode stubs return zero sources; live providers disabled by default.
- Storyboard/animatics: palette API mismatch; rasterization callers sometimes pass Scenes.
- Audio/video: VO discovery brittle; good HW accel path on macOS; music integration present but optional.
- Docs/branding still Pi‑first in places.

---

## Critical Issues & Concrete Fixes

### 1) Orchestrator Fragility (High Priority)

**Issues:**
- Brittle slug parsing assumes underscore in script filenames, causing "list index out of range" errors
- `--yt-only` still triggers shared ingestion unless `--from-step` is used
- Brief loading warning "list has no attribute strip" when lists contain non-strings

**Evidence:**
- `bin/run_pipeline.py:595`, `bin/run_pipeline.py:635` (slug extraction)
- `bin/run_pipeline.py:694` (ingestion gating with `--yt-only`)
- `bin/brief_loader.py:106` (list element normalization)

**Fixes:**
- Add `safe_slug_from_script(path)` helper that returns `Path(path).stem` when no `_` is present
- Honor `--yt-only` by skipping ingestion entirely unless `--from-step` specified
- Coerce list items to strings during normalization; filter out non-stringy values

### 1b) Additional Orchestrator Bugs (New)

**Issues:**
- Shared ingestion incorrectly runs on `--yt-only` unless `--from-step` is set (should not run at all)
- Subprocess steps hide live output via `capture_output=True`

**Evidence:**
- `bin/run_pipeline.py:694` (gating logic)
- `bin/run_pipeline.py:196`, `bin/run_pipeline.py:542` (capture_output)

**Fixes:**
- Change gating to only run shared ingestion when `not args.yt_only`
- Stream subprocess stdout/stderr to console and log file; print last N lines on failure
- Add FFmpeg encoder fallback: try `h264_videotoolbox`, then fallback to `libx264` automatically on failure.

### 2) Configuration Fragmentation/Inconsistency

**Issues:**
- Research config pulled from different sources by different components (drift risk)
- Mixed pydantic vs dict access patterns causing runtime AttributeErrors

**Evidence:**
- Collector: `bin/research_collect.py` loads `conf/research.yaml` (correct)
- Grounder: `bin/research_ground.py:54` loads research settings from `conf/models.yaml` (inconsistent)

**Fixes:**
- Make `conf/research.yaml` the single source of truth for research/grounding policy
- Keep only model names in `conf/models.yaml`
- Standardize on pydantic-style access for `load_config()` objects

### 3) LLM Client Hygiene & API Usage

**Issues:**
- Using `/api/pull` as a way to "load" (pull downloads, not runtime load)
- Request timeouts not passed per-call; `requests.Session` has no global timeout
- Two overlapping client layers (`model_runner.py` and `llm_client.py`)
- Forced CPU-only (`num_gpu: 0`) and hardcoded M2 params

**Evidence:**
- `bin/model_runner.py:251` (pull misuse)
- `bin/model_runner.py:308`, `bin/model_runner.py:376` (no `timeout=...`)
- `bin/model_runner.py:240` (hardcoded M2 params)

**Fixes:**
- Use `ensure_model()` (via tags listing + pull if missing) once, rely on `/api/chat`/`/api/generate` to implicitly load
- Pass `timeout=` on each HTTP call, sourced from config
- Consolidate on one client (prefer `model_runner`)
- Make device/params configurable in `conf/models.yaml` with sensible defaults

### 4) Research Pipeline Limitations

**Issues:**
- Reuse mode yields zero sources; `_collect_from_search` is a stub
- Rate limiting ignores provider-specific settings
- Grounder domain scoring mixed between code and config

**Evidence:**
- `bin/research_collect.py:482`, `bin/research_collect.py:512` (stub implementation)
- `bin/research_collect.py:349` (simple `sleep(2)`)
- `bin/research_ground.py:271` (hardcoded domain scores)

**Fixes:**
- Implement minimal offline search fallback (local fixtures) or provide curated sources in `data/fixtures/`
- Use `conf/research.yaml` rate limits (per provider) with jitter and per-host buckets
- Move domain reputation maps into `conf/research.yaml` and reference consistently

### 5) Storyboard/Animatics Integration

**Issues:**
- Palette API mismatch; expecting `.colors` attribute but may get a dict
- Rasterization relies on flat list of elements; callers sometimes pass `Scene` objects

**Evidence:**
- Warning at `bin/animatics_generate.py:547`
- Attribute errors during batch rasterization

**Fixes:**
- Standardize `load_palette()` return type (object with `.colors`) or wrap returned dict into adapter
- Enforce single flattening utility (collect elements across scenes) and use it everywhere

### 6) Video Assembly & Audio UX

**Issues:**
- VO discovery is brittle; requires exact basename match
- Platform-specific encoder selection
- No `--slug` support in thumbnail CLI; always uses newest metadata
- Unicode ellipsis can trigger PIL font issues

**Evidence:**
- `bin/assemble_video.py:392` (VO selection)
- `bin/make_thumbnail.py:152` (no `--slug`)

**Fixes:**
- Implement tolerant discovery (prefer exact slug, fallback to most recent matching prefix/suffix)
- Detect platform and choose codec: `h264_videotoolbox` on macOS, `libx264` on Linux/ARM
- Add `--slug` support to thumbnail CLI; resolve `scripts/<slug>.metadata.json` first
- Use ASCII `...` or ensure bundled font with coverage

## Export & Mastering (Quality for Monetization)

- **Intermediate master (internal):** ProRes 422 (preferred on Mac) or lossless H.264 (CRF 14–16) to avoid generational loss.
- **Delivery (YouTube 1080p):** H.264 High, CRF 18–20, yuv420p; audio AAC 320 kbps @ 48 kHz; peak video 12–16 Mbps (via maxrate/bufsize); encoder: `h264_videotoolbox` with automatic fallback to `libx264`.
- **Monetization packager:** compose title, 1-paragraph hook, chapters, hashtags, affiliate/newsletter links with unique UTM and FTC disclosure from `conf/monetization.yaml`.

Acceptance:
- Media inspector JSON attached to run; codec profile and CRF/bitrate match target; chapters present; disclosure and links validated.

### 7) Error Handling & Logging

**Issues:**
- Subprocess steps use `capture_output=True`, hiding live progress
- Optional/required semantics inconsistent
- JSON-in-string logs reduce parseability

**Evidence:**
- `bin/run_pipeline.py:166` (capture_output usage)
- Some optional steps still abort on error
- `log_state` with serialized dicts

**Fixes:**
- Stream stdout/stderr with line buffering or tee to logs; retain tail on failure
- Centralize required/optional policy in config and ensure `run_step()` adheres uniformly
- Use structured logger or write JSON to separate audit files per step

---

## Additional Critical Issues (New)

- `bin/research_ground.py:345`: Undefined `topic` in prompt template; use slug or `brief['title']`.
- `bin/brief_loader.py:166`: Non-string list items cause `.strip()` AttributeErrors; coerce to strings and guard None.
- `bin/run_pipeline.py:694`: `--yt-only` gating incorrect; shared ingestion should not run.
- `bin/model_runner.py:169`: `requests.Session` has no global timeout; pass `timeout=` per call.
- `bin/model_runner.py:240-246`: `/api/pull` used as loader; remove and rely on chat/generate to load.
- `bin/animatics_generate.py:555`: Palette dict treated as object with `.colors`; use adapter or dict access.

---

## Platform Target Update (Pi 5 → Mac M2 8GB)

### A) Pi‑Specific Leftovers

- README branding: Mentions Pi 5 as the primary platform; should reflect Mac‑first
- Thermal guard for Pi: Uses `vcgencmd` to read CPU temp and defer heavy work on high temps (Pi‑only tool)
- Pipeline memory label: Explicit "Raspberry Pi 5 constraint" comment in pipeline config
- Local speech defaults tuned for Pi: ASR: `whisper_cpp` with auto‑paths; TTS: Piper by default
- Topical defaults include "raspberry pi tips" in niches (minor branding leftover)
- Docs still include Pi optimization notes

### B) Constraints From Pi Planning (Now Over‑Conservative on M2)

- Single‑lane everywhere: `max_concurrent_renders: 1`, single lock, and Ollama forced single‑model
- Pacing cooldown: `pacing_cooldown_seconds: 60` sleeps between heavy steps
- Small LLM footprint: Single 3B model for all tasks; low `num_predict` caps
- Memory/time guards: Disk‑free guard (<5GB) and Pi thermal defer
- Offline defaults: Research reuse‑mode with APIs disabled; ASR/TTS fully local

### C) Mac M2 (8GB) Recommendations

- Update docs/branding: State "Mac M2 8GB (local‑first) primary; Pi 5 supported secondary"
- Guard behavior: Keep disk‑free guard; make thermal guard platform‑aware (skip on macOS)
- Concurrency and pacing: Consider `max_concurrent_renders: 2` and reduce `pacing_cooldown_seconds` (10–20s) on M2
- LLM utilization: Keep `llama3.2:3b` for reliability; optionally allow larger quantized model (7B/8B) for scriptwriting
- Research flow: Enable select live providers or bundle small offline fixture set
- Speech/ASR: Keep Piper/whisper.cpp as defaults; document optional macOS alternatives
- Encoding: Keep VideoToolbox detection for macOS; choose `libx264` on Linux/ARM automatically

Acceptance:
- Mac profile (`conf/m2_8gb_optimized.yaml`) reduces cooldowns and allows modest concurrency without OOM; Pi profile remains conservative

---

## Architecture (Desired)

- Config first: `conf/global.yaml` for operator controls; `conf/pipeline.yaml` for step graph and quality gates; `conf/research.yaml` sole source for research policy; `conf/models.yaml` for model names/LLM options only.
- Orchestrator: sequential state machine with clear lane selection; step subprocess wrapper with uniform logging, timeouts, and required/optional semantics.
- LLM: single client layer with model session lifecycle, per‑request timeouts, and deterministic seeds.
- Design system: brand style + palette + texture engine + QA gates as first‑class modules.
- Rendering: scenescript → animatics (MoviePy) with HW acceleration; deterministic seeds; idempotent reruns.
- Audio: TTS → normalize → optional music ducking; SRT captions (synthetic or Whisper) aligned to VO.
- Publishing: stage locally; optional YouTube upload behind a flag.

---

## Execution Contracts (Make It Unambiguous)

### Config Layering & Precedence

Order of precedence (lowest → highest):
1) Defaults baked into Pydantic models
2) `conf/*.yaml` (base): `global.yaml`, `pipeline.yaml`, `research.yaml`, `models.yaml`
3) Profile overlay (optional): `conf/m2_8gb_optimized.yaml`, `conf/pi_8gb.yaml`
4) Environment variables (e.g., `OLLAMA_*`, `SHORT_RUN_SECS`)
5) CLI flags (e.g., `--yt-only`, `--from-step`, `--brief`, `--mode`)

Validation: Each config file should validate against a schema at load. Fail fast with actionable messages.

### CLI Contract (All steps)

Required where applicable: `--slug`. Optional: `--brief`, `--brief-data`, `--mode {reuse,live}`, `--dry-run`, `--force`, `--from-step`.

Exit codes: 0 OK, 1 FAIL, 2 PARTIAL/SKIP (optional step failed), 130 INTERRUPTED.

### Artifact Contract (Inputs/Outputs)

- Research: `data/<slug>/collected_sources.json` (list[dict]), `data/research.db` (tables: `sources`, `chunks`, `research_cache`).
- Grounding: `data/<slug>/grounded_beats.json`, `data/<slug>/references.json`.
- Script: `scripts/<date>_<slug>.txt` (fallback `scripts/<slug>.txt`); safe slug fallback required.
- Storyboard: `scenescripts/<slug>.json` (validated by `schema/scenescript.json`).
- Animatics: `assets/<slug>_animatics/scene_XXX.mp4` (±3% timing tolerance).
- Audio: `voiceovers/<slug>.mp3` (−16 LUFS target), `voiceovers/<slug>.srt`.
- Video: `videos/<slug>_cc.mp4`, `videos/<slug>.metadata.json` (scene_map, durations, coverage).

### Logs & Events

Append JSONL to `jobs/state.jsonl` with fields: `ts`, `step`, `status` in {OK, FAIL, PARTIAL, TIMEOUT, SKIP}, `notes` (key=value …). Stream subprocess output to console and file; on failure print last 200 lines.

Acceptance:
- All steps emit structured logs; tail-on-fail implemented; `analytics_collector` aggregates recent metrics into `data/analytics/`

---

## Cleanup & Consolidation (Foundational Tasks)

1) Orchestrator hardening
- Safe slug helper; stop assuming underscores in filenames.
- Honor `--yt-only` (skip shared ingestion unless `--from-step` specified).
- Brief normalization: coerce list elements to strings; tolerate missing/partial fields.
- Stream step output (or tee) for operator visibility; keep last N lines on failure.

2) Config unification
- Make `conf/research.yaml` authoritative for research/grounding policies; keep only model names in `conf/models.yaml`.
- Standardize pydantic access; add small helpers for reading optional dict blocks safely.
- Document precedence and profile overrides in README.

3) LLM client consolidation
- Fold `llm_client.py` into `model_runner.py` (or vice‑versa) to a single client.
- Replace `/api/pull` as a loader; use `ensure_model()` once and rely on `/api/chat`/`/api/generate` to implicitly load.
- Add per‑request timeouts; retry with backoff for transient failures.

4) Research local usability
- Implement an offline fixture path for reuse mode (e.g., `data/fixtures/<topic>.json`); minimal search fallback to avoid zero‑source runs.
- Provider‑aware rate limits from `conf/research.yaml`; apply jitter/backoff.
- Grounder to use unified domain scoring from config (no hardcoded domain sets).

5) Storyboard/animatics API alignment
- Standardize palette interface (object with `.colors`); add adapter for dict returns.
- Always flatten scene elements before rasterization; one utility function reused.

6) Audio/video UX
- VO discovery tolerant of date‑prefixed filenames; prefer exact slug match, fallback to latest reasonable.
- Thumbnail tool accepts `--slug`; default to newest otherwise; avoid Unicode ellipsis.
- Platform‑aware encoder: `h264_videotoolbox` on macOS; `libx264` on Linux/ARM.

7) Platform update (Pi → Mac)
- Update README and comments to reflect Mac M2 8GB as primary; move Pi into alternate profile.
- Keep disk space guard; make thermal guard platform‑aware (no error on macOS).
- Reduce `pacing_cooldown_seconds` (e.g., 10–20s) in Mac profile; consider `max_concurrent_renders: 2` when stable.

---

## Quality Gates (Acceptance Harness)

- **Script:** WPM 145–175; CTA present; no `[CITATION NEEDED]`.
- **VO/audio:** -14 ±0.5 LUFS; TP ≤ -1.5 dBTP; LRA ≤ 11; sibilance under threshold; silence ≤ 4%; music ducking applied.
- **Visuals:** contrast ≥ 4.5:1; text inside safe areas; SSIM ≥ 0.93 post-texture; per-scene duration within ±3% of plan.
- **Video master:** ProRes 422 internal or CRF 18–20 delivery; AAC 320 kbps 48 kHz; codec fallback verified.
- **Research/claims:** min citations per factual beat; fact-guard policy = **block** on unresolved.
- **Monetization:** disclosure + UTM links present; link count within configured max.

Gate behavior: all gates must PASS for GREEN; WARN gates log but block only if configured.

## Viral Growth Engine (Best-in-Class Additions)

Aim: systematic virality levers with measurable retention and conversion outcomes.

1) Hook Engine and Variants
- Generate 5–10 hook variants per topic (pattern library: curiosity gap, inversion, number-led, contrarian)
- Score with local heuristics + LLM evaluator; select top 2 for A/B
- Bake chosen hook into script cold-open and first visual (title card or kinetic type)

2) Title/Thumbnail Lab
- Produce 5 titles and 3 thumbnails per slug; enforce style system; auto-save to `videos/<slug>/thumbs/`
- Heuristic title score (keyword novelty, power words, length, CTR proxies)
- CLI/UI to pick winner; record decision in metadata

3) Shorts/Cutdowns
- Auto-generate 1–3 vertical clips (9:16) from the most “hookable” segments; add captions and branding
- Export to `videos/<slug>/shorts/` with social-optimized filename and metadata stubs

4) SEO + Packaging
- Draft YouTube description, tags, chapters, and a pinned comment; ensure keyword coverage from brief and research
- Generate end screens and CTA overlays (subscribe, next video) using design system assets

5) Retention & Pacing Heuristics
- Per-beat interest scoring; enforce curiosity bridges every N seconds in first minute
- Music beat-aligned transitions; micro-animations density caps to avoid fatigue

6) Experimentation & Feedback Loop
- Log selections and outcomes locally; optional YouTube Analytics pull to correlate titles/thumbs to performance (off by default)
- Maintain `results/experiments/<slug>.json` for chosen variants and reasons

Acceptance:
- For a demo slug, artifacts exist for: hooks (N>5), titles (N>=5), thumbnails (N>=3), shorts (N>=1)
- Metadata JSON documents chosen variants and rationale
- Chapters auto-generated; end screens present; captions burned and SRT exported

---

## Static Analysis & Dead Code Cleanup (from recent audits)

Tools (Vulture and manual review) flagged unused imports/variables across 60+ files (≈156 instances). We will apply a focused, low‑risk cleanup to working modules first, then address experimental modules.

Priority edits (working modules)
- `bin/assemble_video.py`: remove `from moviepy.video.fx import all as vfx` if unused.
- `bin/cutout/texture_engine.py`: drop `opensimplex`, `skimage`, `filters` imports unless used; keep optional deps behind feature flags only.
- `bin/cutout/sdk.py`: add `# noqa: F841` where Pydantic validator `cls` is intentionally unused (or migrate to v2 `@field_validator`).
- `bin/model_runner.py`: `__exit__(self, exc_type, exc_val, exc_tb)` – mark unused params with `# noqa: F841` (or rename to `_` variants).
- `bin/asset_manifest.py`: remove or implement the unused `filter_palette_only` parameter in `rebuild_manifest()`.

Experimental/legacy modules
- `bin/cutout/svg_geom.py`, `bin/cutout/svg_path_ops.py`: trim unused imports (e.g., `Arc`, `QuadraticBezier`, `SVGElementPath`, `Point`, `LineString`). Keep only what is used by current features and tests.
- `fastapi_app/routes.py`: verify endpoints are actually used via HTTP; do not treat as dead code purely by static analysis.

Process & guardrails
- Incremental changes + tests after each edit (unit + integration smoke).
- Prefer removing unused imports over adding `noqa`, unless intentionally reserved for near‑term features.
- Document "experimental" status in module headers where applicable.

Success metrics
- Zero unused imports in working modules; no functionality change.
- Tests green; pipeline e2e passes.
- Follow‑up: address experimental modules next, with documentation updates.

---

## Research & Grounding Plan

- Modes: `reuse` (default) uses fixtures/cache; `live` enables selected providers.
- Policy: `conf/research.yaml` defines allow/deny lists, scoring weights, min citations, coverage thresholds.
- Collector: implements search/provider ingestion with rate limits; stores in SQLite (`data/research.db`) with chunking and dedupe.
- Grounder: pulls relevant chunks, scores by config weights, injects citations with explicit formatting, outputs `data/<slug>/grounded_beats.json` + `references.json`.
- Fact guard: runs LLM pass on script; gating configurable (`off/warn/block`).

Acceptance:
- Non‑zero sources in reuse mode via fixtures; live mode respects API toggles and rate limits.
- Grounding quality passes configured thresholds (coverage %, avg citations/beat) for happy‑path fixtures.

---

## Immediate Cleanup Actions (3‑day sprint)

Day 1 — High‑impact, low‑risk
- Remove unused imports in working modules: `texture_engine.py`, `assemble_video.py`.
- Add `noqa` for intentionally unused validator params (SDK) and context exit args (model_runner).
- Remove/implement unused parameter `filter_palette_only` (asset_manifest).

Day 2 — Experimental modules and docs
- Trim unused imports in `svg_geom.py` and `svg_path_ops.py` (keep only used symbols).
- Add module docstrings clarifying implemented vs planned features; mark experimental modules.

Day 3 — Tests & validation
- Run unit tests and integration pipeline tests (`bin/test_e2e.py`, `bin/test_integration.py`).
- Verify import loading for active modules (smoke import checks).

Expected outcomes
- Reduced memory/import overhead; improved clarity for developers.
- No behavior change in the working pipeline.

---

## Design System & Storyboarding

- Brand style: `assets/brand/style.yaml` + `design/design_language.*` define palette, typography, motion primitives.
- Legibility defaults: enforce backgrounds and text colors; WCAG checks.
- Texture engine & micro‑animations: opt‑in; QA gates ensure contrast/readability.
- Scenescript schema: validated JSON; determinism via seed.

Acceptance:
- Scene durations meet target tolerance (±3%); truncation policy applied; legibility QA passes.
- Contrast ≥ 4.5:1; all text within title/action safe (90%/95%).
- SSIM (post-texture vs pre-texture) ≥ 0.93 to prevent over-graining.

---

## Audio & Captions (Monetization-Grade)

- **TTS lanes:** Local default (e.g., Piper/XTTS) with an opt-in **premium lane** (e.g., ElevenLabs/PlayHT/Azure) controlled via `voice.profile = local|premium` in `conf/global.yaml`.
- **Prosody control:** Extend script emitter with SSML-style tags for pauses/emphasis/rate.
- **Post-TTS chain:** two-pass `loudnorm` to **-14 LUFS integrated** (±0.5), **true peak ≤ -1.5 dBTP**, **LRA ≤ 11**; add de-esser, gentle compressor (≈2:1), brickwall limiter (-1.5 dBTP).
- **Music ducking:** side-chain duck VO by 10–12 dB with ~300–500 ms release.
- **Captions:** synthetic SRT aligned to VO; Whisper local when enabled.

Acceptance:
- VO meets **-14 ±0.5 LUFS**, **TP ≤ -1.5 dBTP**, **LRA ≤ 11**; speech rate 145–175 wpm; non-intentional silence ≤ 4% total.
- Sibilance score (energy >5.5 kHz / fullband) under configured threshold; captions synchronized.

---

## Assembly & Publishing

- Animatics‑first assembly; scene map & coverage metrics written to metadata.
- **Intermediate master:** ProRes 422 or lossless H.264 (CRF 14–16).
- **Delivery (YouTube):** H.264 High, CRF 18–20, yuv420p; AAC 320 kbps @ 48 kHz.
- Platform‑aware hardware encoding; automatic fallback to `libx264` on failure.
- Upload stage: local staging; YouTube upload behind explicit flag and creds.

Acceptance:
- `videos/<slug>_cc.mp4` produced; metadata contains durations, scene map, coverage stats; encode inspector confirms profile/CRF/bitrate/audio targets.
- Chapters and monetization pack present (UTMs unique, disclosure present).

---

## Operator Experience & UI

- Gradio console: brief compiler, job launch, gate approvals, and variant selection (title/thumb/hook)
- FastAPI: endpoints for variant generation/selection; authenticated local-only by default
- Creator profile: minimal config to bias tone/visuals across a series

Acceptance:
- Operator launches with free-text brief, picks a title/thumb, approves gates in-UI; artifacts update accordingly

---

## Observability & QA

- Logging: structured JSON to stdout + `logs/` file; `jobs/state.jsonl` per‑step events.
- Artifacts: each step writes outputs into canonical paths; orchestrator summarizes.
- QA: legibility checks, duration policy checks, coverage checks; fail/warn thresholds in config.

---

## Determinism & Idempotence

- Seeds: centralized in config; passed to design/layout/texture RNGs.
- Idempotence: steps skip if outputs exist (unless `--force` specified); reruns do not duplicate artifacts.

---

## Security & Offline Posture

- Default mode uses local models and caches; no network calls unless toggled.
- When live, rate limits and allowlists apply; no secrets required for default local mode.

---

## Testing Strategy

- Unit tests: slug derivation; brief normalization; palette adapter; VO discovery; config precedence.
- Integration tests: smoke path from script → animatics → assemble; research + grounding with fixtures; LLM integration via mocked client.
- Performance tests: encode duration bounds on M2; memory pressure behavior for model session.

---

## CI/CD & QA Hardening

- Fast smoke workflow: lint, import-only load of active modules, unit tests for slug/brief/palette, tiny animatic render
- Seed-lock tests to catch determinism regressions (scene IDs and durations stable ±3%)
- Make targets for common paths (`make smoke`, `make demo-eames`, `make ui`)

Acceptance:
- `bin/test_e2e.py` passes locally on Mac M2; critical unit tests green; smoke path stable

---

## Migration & Deprecation

- Mark legacy modules in `legacy/` as such; keep entry points but add deprecation notes.
- Consolidate client layers; remove unused/shadowed code after parity tests.

---

## Roadmap & Milestones (2–3 Weeks)

Phase 1 (Stability & Config)
- Orchestrator hardening (slug, flags, brief; output streaming)
- Config unification for research; palette adapter; flattening utility
- VO discovery + thumbnail `--slug`
- Audio validator (LUFS/TP/LRA + sibilance) wired into acceptance harness.

Phase 2 (Research & LLM Hygiene)
- Offline fixture path; provider rate limits; domain scoring from config
- LLM client consolidation; per‑request timeouts; remove `/api/pull` misuse
- Premium TTS lane (config + provider adapter) behind publish flag.

Phase 3 (Platform & Throughput)
- README/platform update; platform‑aware guards
- Tune cooldown/concurrency for Mac profile; encode codec selection by platform

Phase 4 (QA & Tests)
- Add unit/integration tests listed above; CI fast smoke
- Document operator runbooks (golden path; troubleshooting)

Deliverables per phase: PRs with focused changes, updated docs, and passing smoke tests.

---

## Greenlight Checklist (Go/No‑Go)

- One‑command local run from topic/brief to `videos/<slug>_cc.mp4` without manual edits.
- Deterministic outputs with fixed seed; idempotent re‑runs.
- Acceptance harness PASS on: audio (−14 ±0.5 LUFS, TP ≤ −1.5 dBTP, LRA ≤ 11), visuals (contrast/safe areas/±3% timing), research (fact-guard = block cleared), and monetization (disclosure + valid UTMs).
- Platform-aware encode with verified fallback; artifacts and logs complete.
- Operator docs (README + runbooks) updated; platform profiles documented.

Viral Engine addendum (for “10/10”):
- Hook/Title/Thumbnail variants generated with documented selection
- At least one vertical cutdown created per slug
- Chapters and end screens present; captions accurate and legible

Once these items are complete, the pipeline is "greenlit" for active content production on Mac M2 (8GB) with Pi 5 support retained as a secondary profile.

---

## File Reference Index (Fix Sites)

- Orchestrator
  - `bin/run_pipeline.py:595`, `bin/run_pipeline.py:635` (slug extraction)
  - `bin/run_pipeline.py:694` (ingestion gating with `--yt-only`)
  - `bin/run_pipeline.py:166`, `bin/run_pipeline.py:286` (capture_output usage)
- Brief & Config
  - `bin/brief_loader.py:106` (list element normalization)
  - `bin/core.py:308` (create_brief_context joins lists)
- LLM Client
  - `bin/model_runner.py:251` (pull misuse), `bin/model_runner.py:308` (timeouts)
  - `bin/llm_client.py:16` (duplicate layer; consider consolidation)
- Research
  - `bin/research_ground.py:54` (reads research policy from models.yaml)
  - `bin/research_ground.py:345` (undefined `topic` in prompt formatting)
  - `bin/research_collect.py:75` (reads `conf/research.yaml`)
- Rendering
  - `bin/animatics_generate.py:555` (palette `.colors` assumption)
- Assembly & Thumbnail
  - `bin/assemble_video.py:392` (VO selection)
  - `bin/make_thumbnail.py:152` (no `--slug`)
- Guards
  - `bin/core.py:547` (Pi thermal `vcgencmd`), `bin/core.py:571` (disk space)

Use these as a jumping-off point; confirm exact lines in your editor.
