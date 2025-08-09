# Repository Audit & Action Plan — Probable Spork (Revised: Defer WordPress Publishing)
**Timestamp (UTC):** 2025-08-09 20:54:52Z

## Executive Summary (What changed)
- We are **deferring WordPress publishing** until you have a real domain/hosting ready.
- The pipeline will still **generate blog-ready content** (SEO-checked HTML, images, meta, schema) and **stage it locally** for manual upload later.
- We will **disable all push-to-WP actions** via config flags and orchestrator logic, but **keep blog generation** fully functional.
- Everything else in the plan remains: orchestrator, A/V polish, monetization templates, acceptance harness, DRY_RUN governance.

## High-Priority Gaps (Fix Order)
1. **Create `bin/run_pipeline.py` orchestrator** (single daily loop; lock-aware; flags `--yt-only`, `--blog-only`, `--from-step`).
2. **A/V Quality**: Add **loudness normalization** and **sidechain ducking** in `assemble_video.py`; ensure ≥85% b-roll coverage.
3. **Monetization**: Add `conf/monetization.yaml` and wire **CTAs/UTMs** into YouTube descriptions and blog HTML payloads (stored locally).
4. **Local Blog Staging (NEW)**: Create `bin/blog_stage_local.py` to export blog artifacts under `exports/blog/YYYYMMDD_slug/`:
   - `post.html` (sanitized, SEO linted), `post.md`, `post.meta.json` (title/slug/desc/tags/cat), `schema.json`, `assets/` images, `credits.json`, and a `wp_rest_payload.json` (future POST body).
   - Optional zip bundle: `exports/blog/YYYYMMDD_slug.zip`.
5. **Acceptance Test**: Add `bin/acceptance.py` validating artifacts & quality thresholds; **check local blog export instead of live WP post**.
6. **DRY_RUN Governance**: Replace hard-coded DRY_RUN with config/flag; add `blog.publish_enabled: false` in `conf/blog.yaml` and obey it in orchestrator.

## Config Changes to Make Now
- In `conf/blog.yaml`, add:
```yaml
wordpress:
  base_url: "http://127.0.0.1"   # keep placeholder
  api_user: "poster_user"
  api_app_password: "REPLACE_LATER"
  publish_enabled: false          # <- NEW: disables live posting
  staging_root: "exports/blog"    # <- NEW: local export root
blog:
  daily_posts: 1
  min_words: 800
  max_words: 1500
  tone: "informative"
```

## Orchestrator (Updated Plan)
**`bin/run_pipeline.py` steps (single daily run):**
1) `niche_trends` → `llm_cluster`  
2) `llm_outline` → `llm_script` → fact_check (gate)  
3) `fetch_assets`  
4) **YouTube lane**: `tts_generate` → `generate_captions` → `assemble_video` → `make_thumbnail` → `upload_stage` (or `youtube_upload` if you later flip a flag)  
5) **Blog lane (staged only)**: `blog_pick_topics` → `blog_generate_post` → `blog_render_html` → **`blog_stage_local` (NEW)**  
6) Update health & state logs. Respect lock, backoff, thermal/disk guards.

## What We’re NOT Doing Yet
- **No live WordPress post**. We keep `blog_post_wp.py` for later, but the orchestrator must skip it while `publish_enabled: false`.
- **No sitemap ping** or cache warm calls until you set a real domain + enable publishing.

---

# Cursor Prompts — Revised (WordPress Publish Deferred)

## Prompt A — Orchestrator & Cron Unification (WP Deferred)
SYSTEM: Senior integrator.  
TASK: Create `bin/run_pipeline.py` orchestrator with flags and guards. Order:
1) niche_trends → llm_cluster  
2) llm_outline → llm_script → fact_check (gate on high-risk)  
3) fetch_assets  
4) YouTube lane: tts_generate → generate_captions → assemble_video → make_thumbnail → upload_stage (or youtube_upload when enabled)  
5) Blog lane (staged only): blog_pick_topics → blog_generate_post → blog_render_html → **blog_stage_local (NEW)**  
RULES:
- Single lock; backoff retries; update `jobs/state.jsonl` after each step with elapsed_ms and artifact paths.
- Guard thermal/disk (defer if cpu_temp>75°C or free<5GB).
- Obey `conf/blog.yaml` key `wordpress.publish_enabled`. If false, **skip** `blog_post_wp.py` and **run blog_stage_local instead**.
- CLI flags: `--yt-only`, `--blog-only`, `--from-step`, `--dry-run`.
- Replace multi-entry cron with one daily call to `run_pipeline.py`; keep hourly health cron.
CONTEXT TO REVIEW (MANDATORY)
- Read top-of-doc sections: Executive Summary, High-Priority Gaps, Config Changes to Make Now, Orchestrator (Updated Plan), and What We’re NOT Doing Yet.
- Open repo docs if present: RED_TEAM_BRIEFING.md, PRODUCTION_READINESS_CHECKLIST.md, RED_TEAM_FILE_INVENTORY.md, OPERATOR_RUNBOOK.md, MASTER_TODO.md, MONETIZATION_STRATEGY.md.
- Inspect configuration and env: conf/global.yaml, conf/blog.yaml, conf/render.yaml, and .env (or .env.example).
- Check current state & scheduling: jobs/state.jsonl, logs/, and crontab.seed.txt.

WORKING FRAMEWORK — THINK → PLAN → APPLY
- THINK: Summarize current state, constraints, and risks (≤10 bullets) using the CONTEXT above.
- PLAN: List the exact file edits/new files, CLI flags, ordering, rollback, and tests you will run.
- APPLY: Implement the changes, run the verification commands, and append a brief date-stamped changelog under this prompt section.
SUCCESS CRITERIA & VERIFICATION
`python bin/run_pipeline.py --dry-run` completes both lanes and writes a **local blog export** under `exports/blog/YYYYMMDD_slug/` with all files.

Verification commands:
- python bin/run_pipeline.py --dry-run
- crontab -l | grep run_pipeline.py

## Prompt B — A/V Quality: Loudness, Ducking, Coverage
SYSTEM: Motion editor + audio engineer.  
TASK:
- In `assemble_video.py`, add VO **ffmpeg loudnorm** pass and final mix normalization.
- Add **sidechain ducking** of music under VO (`sidechaincompress`).
- Enforce ≥85% visual coverage; deterministic fallback filler from top-rated assets.
- Reasonable transitions: dissolve every ≥6s; avoid rapid cuts.
CONTEXT TO REVIEW (MANDATORY)
- Read top-of-doc sections: Executive Summary, High-Priority Gaps, Config Changes to Make Now, Orchestrator (Updated Plan), and What We’re NOT Doing Yet.
- Open repo docs if present: RED_TEAM_BRIEFING.md, PRODUCTION_READINESS_CHECKLIST.md, RED_TEAM_FILE_INVENTORY.md, OPERATOR_RUNBOOK.md, MASTER_TODO.md, MONETIZATION_STRATEGY.md.
- Inspect configuration and env: conf/global.yaml, conf/blog.yaml, conf/render.yaml, and .env (or .env.example).
- Check current state & scheduling: jobs/state.jsonl, logs/, and crontab.seed.txt.

WORKING FRAMEWORK — THINK → PLAN → APPLY
- THINK: Summarize current state, constraints, and risks (≤10 bullets) using the CONTEXT above.
- PLAN: List the exact file edits/new files, CLI flags, ordering, rollback, and tests you will run.
- APPLY: Implement the changes, run the verification commands, and append a brief date-stamped changelog under this prompt section.
SUCCESS CRITERIA & VERIFICATION
Output MP4 has stable VO loudness (~-16 LUFS), balanced music, clean transitions, coverage≥85% (log metrics).

Verification commands:
- python bin/assemble_video.py
- ffprobe -hide_banner videos/<slug>.mp4

## Prompt C — Monetization Wiring (Staged)
SYSTEM: Growth engineer.  
TASK:
- Create `conf/monetization.yaml` with:
  - `youtube: cta_text, cta_url, affiliate_disclosure, default_hashtags, utm_source, utm_medium, utm_campaign`
  - `blog: affiliate_disclosure, newsletter_html_slot (optional), utm_*`
- Update `youtube_upload.py` (or upload_stage metadata) to generate description body with **summary, chapters, CTA (UTM-tagged), disclosure, hashtags**.
- Update `blog_generate_post.py`/`blog_render_html.py` to **inject affiliate disclosure** and **newsletter slot** (if present) in HTML, but **do not publish**.
- Ensure all crosslinks (video↔blog) receive UTMs; include them in the staged JSON.
CONTEXT TO REVIEW (MANDATORY)
- Read top-of-doc sections: Executive Summary, High-Priority Gaps, Config Changes to Make Now, Orchestrator (Updated Plan), and What We’re NOT Doing Yet.
- Open repo docs if present: RED_TEAM_BRIEFING.md, PRODUCTION_READINESS_CHECKLIST.md, RED_TEAM_FILE_INVENTORY.md, OPERATOR_RUNBOOK.md, MASTER_TODO.md, MONETIZATION_STRATEGY.md.
- Inspect configuration and env: conf/global.yaml, conf/blog.yaml, conf/render.yaml, and .env (or .env.example).
- Check current state & scheduling: jobs/state.jsonl, logs/, and crontab.seed.txt.

WORKING FRAMEWORK — THINK → PLAN → APPLY
- THINK: Summarize current state, constraints, and risks (≤10 bullets) using the CONTEXT above.
- PLAN: List the exact file edits/new files, CLI flags, ordering, rollback, and tests you will run.
- APPLY: Implement the changes, run the verification commands, and append a brief date-stamped changelog under this prompt section.
SUCCESS CRITERIA & VERIFICATION
Staged blog export contains monetized HTML (disclosure + optional newsletter slot) and metadata JSON with CTAs/UTMs; YouTube description JSON is templated.

Verification commands:
- python bin/youtube_upload.py --dry-run
- cat exports/blog/*/post.meta.json

## Prompt D — Local Blog Staging (NEW)
SYSTEM: Build engineer.  
TASK: Implement `bin/blog_stage_local.py`:
- Inputs: `data/cache/post.html`, `post.meta.json`, assets from `assets/{slug}`.
- Outputs under `exports/blog/YYYYMMDD_{slug}/`:
  - `post.html`, `post.md`, `post.meta.json`, `schema.json` (Article JSON-LD), `assets/` (copied), `credits.json` (license info), `wp_rest_payload.json` (future POST body: title, content, excerpt, slug, categories, tags, featured_media placeholder).
  - Optionally, zip the folder into `exports/blog/YYYYMMDD_{slug}.zip`.
- Sanitize HTML; ensure image `alt` text; SEO lint must pass.
CONTEXT TO REVIEW (MANDATORY)
- Read top-of-doc sections: Executive Summary, High-Priority Gaps, Config Changes to Make Now, Orchestrator (Updated Plan), and What We’re NOT Doing Yet.
- Open repo docs if present: RED_TEAM_BRIEFING.md, PRODUCTION_READINESS_CHECKLIST.md, RED_TEAM_FILE_INVENTORY.md, OPERATOR_RUNBOOK.md, MASTER_TODO.md, MONETIZATION_STRATEGY.md.
- Inspect configuration and env: conf/global.yaml, conf/blog.yaml, conf/render.yaml, and .env (or .env.example).
- Check current state & scheduling: jobs/state.jsonl, logs/, and crontab.seed.txt.

WORKING FRAMEWORK — THINK → PLAN → APPLY
- THINK: Summarize current state, constraints, and risks (≤10 bullets) using the CONTEXT above.
- PLAN: List the exact file edits/new files, CLI flags, ordering, rollback, and tests you will run.
- APPLY: Implement the changes, run the verification commands, and append a brief date-stamped changelog under this prompt section.
SUCCESS CRITERIA & VERIFICATION
Running blog lane produces a folder+zip with all artifacts ready for manual upload later.

Verification commands:
- python bin/blog_stage_local.py
- tree exports/blog | head -100

## CHANGELOG - Prompt D Implementation

**Date: 2025-08-09 21:28 UTC**
**Agent: Agent 4**
**Task: Local Blog Staging (Prompt D)**

### ✅ COMPLETED
- **Created `bin/blog_stage_local.py`** - Full implementation with all required features
- **Implemented staging pipeline** - Processes blog content to local export structure
- **Generated staged export** - Successfully created `exports/blog/20250809_ai-tools/` 
- **All required files present**:
  - `post.html` (sanitized, SEO-linted)
  - `post.md` (original markdown)
  - `post.meta.json` (WordPress-ready metadata)
  - `schema.json` (Article JSON-LD structured data)
  - `assets/` (8 video files copied)
  - `credits.json` (comprehensive license aggregation)
  - `wp_rest_payload.json` (WordPress REST API ready)
  - `20250809_ai-tools.zip` (46MB bundle)

### 🔧 TECHNICAL IMPLEMENTATION
- **HTML sanitization** with automatic alt text injection for accessibility
- **SEO validation** using existing `bin/seo_lint.py` 
- **Schema.org JSON-LD** generation for structured data
- **Asset copying** with permission preservation
- **License aggregation** from source asset metadata
- **WordPress payload** generation for future publishing
- **ZIP bundling** for easy manual upload
- **Idempotency** - skips if export already exists
- **Error handling** with graceful degradation and cleanup
- **Lock-aware execution** following project standards

### 📊 SUCCESS METRICS
- **Files created**: 6 core files + 8 assets + 1 ZIP
- **Export size**: 46MB (including video assets)
- **Processing time**: <2 seconds for staging operation
- **Validation**: Full fact-checking and SEO lint integration
- **Compatibility**: ARM/Pi 5 ready, follows project patterns

### ✅ VERIFICATION RESULTS
```bash
# Successful staging execution
{"ts": "2025-08-09T21:28:03Z", "step": "blog_stage_local", "status": "OK", "notes": "files=6, assets=8, zip=true"}

# Export structure verified
exports/blog/20250809_ai-tools/
├── post.html (2.7KB)
├── post.md (1.9KB)  
├── post.meta.json (3.6KB)
├── schema.json (353B)
├── credits.json (4.3KB)
├── wp_rest_payload.json (6.8KB)
├── assets/ (8 video files, ~49MB total)
└── ZIP bundle: 46MB compressed
```

### 🔗 INTEGRATION STATUS
- **Orchestrator integration**: Ready (graceful handling already implemented)
- **Web UI**: Can be added to step mapping if desired
- **Cron compatibility**: Lock-aware, idempotent execution
- **WordPress deferral**: Fully implements staging-only requirement

## Prompt E — Acceptance Harness (Local Focus)
SYSTEM: Release manager.  
TASK: Add `bin/acceptance.py` that runs the orchestrator in **DRY mode** and asserts:
CONTEXT TO REVIEW (MANDATORY)
- Read top-of-doc sections: Executive Summary, High-Priority Gaps, Config Changes to Make Now, Orchestrator (Updated Plan), and What We’re NOT Doing Yet.
- Open repo docs if present: RED_TEAM_BRIEFING.md, PRODUCTION_READINESS_CHECKLIST.md, RED_TEAM_FILE_INVENTORY.md, OPERATOR_RUNBOOK.md, MASTER_TODO.md, MONETIZATION_STRATEGY.md.
- Inspect configuration and env: conf/global.yaml, conf/blog.yaml, conf/render.yaml, and .env (or .env.example).
- Check current state & scheduling: jobs/state.jsonl, logs/, and crontab.seed.txt.

WORKING FRAMEWORK — THINK → PLAN → APPLY
- THINK: Summarize current state, constraints, and risks (≤10 bullets) using the CONTEXT above.
- PLAN: List the exact file edits/new files, CLI flags, ordering, rollback, and tests you will run.
- APPLY: Implement the changes, run the verification commands, and append a brief date-stamped changelog under this prompt section.
- outline, script, ≥10 assets, VO MP3, SRT, MP4, thumbnail.
- blog `post.html`, `post.meta.json`, `schema.json`, `credits.json`, and `wp_rest_payload.json` inside the export folder.
- Quality thresholds: script score≥80, SEO lint pass, image alt text for all inlines, visual coverage≥85%.
SUCCESS CRITERIA & VERIFICATION
- Emit PASS/FAIL JSON with pointers to artifacts.

Verification commands:
- python bin/acceptance.py

## Prompt F — DRY_RUN & Publish Governance
SYSTEM: QA lead.  
TASK: Centralize `DRY_RUN` and publication toggles:
- Add `core.get_publish_flags()` or similar that reads `--dry-run` plus YAML env flags.
- Make `blog_post_wp.py` and `youtube_upload.py` **no-op** if dry-run or publish disabled.
- Update README and OPERATOR_RUNBOOK with exact toggles.
CONTEXT TO REVIEW (MANDATORY)
- Read top-of-doc sections: Executive Summary, High-Priority Gaps, Config Changes to Make Now, Orchestrator (Updated Plan), and What We’re NOT Doing Yet.
- Open repo docs if present: RED_TEAM_BRIEFING.md, PRODUCTION_READINESS_CHECKLIST.md, RED_TEAM_FILE_INVENTORY.md, OPERATOR_RUNBOOK.md, MASTER_TODO.md, MONETIZATION_STRATEGY.md.
- Inspect configuration and env: conf/global.yaml, conf/blog.yaml, conf/render.yaml, and .env (or .env.example).
- Check current state & scheduling: jobs/state.jsonl, logs/, and crontab.seed.txt.

WORKING FRAMEWORK — THINK → PLAN → APPLY
- THINK: Summarize current state, constraints, and risks (≤10 bullets) using the CONTEXT above.
- PLAN: List the exact file edits/new files, CLI flags, ordering, rollback, and tests you will run.
- APPLY: Implement the changes, run the verification commands, and append a brief date-stamped changelog under this prompt section.
SUCCESS CRITERIA & VERIFICATION
No hard-coded DRY_RUN strings remain; switching flags properly gates publishing.

Verification commands:
- make check && make test
- grep -R "DRY_RUN" -n bin/ | wc -l  # should be 0 except in config/flags handling

---

## Operator Quickstart (with WP deferred)
```bash
# 1) Put monetization and blog flags in place
cp conf/blog.example.yaml conf/blog.yaml   # then set publish_enabled: false, staging_root: exports/blog
# 2) Run orchestrator in dry mode
python bin/run_pipeline.py --dry-run
# 3) Inspect staged blog export
tree exports/blog | head -100
# 4) Run acceptance
python bin/acceptance.py
```

When your domain and WordPress are ready, we’ll re-activate Prompt D (original “WordPress Production Wiring”) and switch `publish_enabled: true`.
