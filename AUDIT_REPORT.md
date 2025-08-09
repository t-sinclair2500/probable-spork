## Audit Report — Code vs. Plans

Scope: Full repo scan of docs, scripts, configs, and artifacts; reconcile work plans; produce SSOT and runbook.

High-level findings
- Purpose and architecture are consistent across README, CURSOR_SHARED_PIPELINE.md, and code.
- MASTER_TODO.md already centralizes tasks; a few doc tasks remain open (README, RUN_BOOK consolidation, WP inline images).
- The pipeline produces end-to-end artifacts locally (voiceover, assets, video). Blog lane performs dry-run post and sitemap ping per logs.

Evidence (selected)
- Video and VO artifacts present:
  - `videos/2025-08-09_ai-tools.mp4` (modified per git status)
  - `voiceovers/2025-08-09_ai-tools.mp3` (modified per git status)
- Assets and licenses present:
  - `assets/2025-08-09_ai-tools/license.json`, `sources_used.txt`
- Blog lane dry-run posting and ping recorded:
  - `jobs/state.jsonl` lines 27–29 show `blog_post_wp` DRY_RUN payload and `blog_ping_search` OK.
- WordPress client features implemented/partial:
  - `bin/blog_post_wp.py` includes category/tag ensure, media upload for featured image, DRY_RUN, and real POST pathways.

Spec vs. Implementation (selected items)
- A1 Ingestion (YouTube API) — Partial; MASTER_TODO.md notes 404s to resolve. Evidence: AGENT_HANDOFF_PLAN.md lines 26–37; need working key/testing and graceful fallback.
- B1 Assets orchestration — Done; assets present with license metadata; normalization evidenced by `_norm.mp4` files.
- C1–C4 Voice/Captions/Assembly/Thumbnail — Done; artifacts exist and Makefile/run-once integrates steps.
- D2 Blog generate — Partial: deliverables exist; acceptance checks for word count/structure to be added.
- D5 WordPress posting — Partial: featured image upload done; inline images not yet attached to content.
- F Ops — Locks/guards/backups/cron present; health server present.

Mac/Pi readiness
- macOS: Make targets and local runs are documented; Ollama + FFmpeg assumed installed. RUN_BOOK adds explicit steps and smoke.
- Raspberry Pi: Debian apt packages, Ollama install, whisper.cpp build steps present in README and PHASE2_CURSOR; Makefile has `pi-*` helpers.

Blockers and next 3 actions
- P0 blockers: YouTube API 404 (ingestion) and inline image upload in WP client.
- Next actions:
  1) Verify YOUTUBE_API_KEY and adjust request parameters; implement resilient fallback. Evidence with new rows in `data/trending_topics.db` and logs.
  2) Implement inline image upload/mapping in `bin/blog_post_wp.py`; add acceptance tests; confirm via WP REST response.
  3) Finalize RUN_BOOK.md and add a short smoke test using Makefile targets on both Mac and Pi.

What changed in this audit
- Consolidated all plans under MASTER_TODO.md; created PURPOSE_SUMMARY.md, DOC_MAP.md, RUN_BOOK.md, and this AUDIT_REPORT.md.
- Archived superseded documents: moved CURSOR_* lists and deprecated conf/sources.yaml to docs/archive/ with explanatory README.
- Updated all references to point to archived locations; added docs/archive/ to .cursorindexingignore.
- Added v2 roadmap section to MASTER_TODO.md (see tasks E/H and D-lane enhancements) — references preserved.

PR plan
- Single PR including documentation, archival, and ignore updates:
  - Add: PURPOSE_SUMMARY.md, DOC_MAP.md, RUN_BOOK.md, AUDIT_REPORT.md, docs/archive/README.md
  - Archive: docs/archive/CURSOR_*/*.txt, docs/archive/sources.yaml
  - Update: MASTER_TODO.md (Status Board, V2 roadmap), .cursorindexingignore (exclude archive)
  - Cross-links updated throughout active docs; deprecated references corrected
- Follow-ups (separate PRs):
  1) Add `.env.example` at repo root (tooling blocked dotfile creation in this session) and update H2 status to DONE.
  2) Implement WP inline image upload + idempotent media reuse.
  3) Harden `bin/test_e2e.py` to skip missing deps and still validate flow.


