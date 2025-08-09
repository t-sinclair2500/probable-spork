## Documentation Map — Inventory and Status

Legend: Active (canonical) | Overlapping | Obsolete (archived)

- README.md — Active. Quick start, Mac/Pi commands, make targets, blog lane notes.
- MASTER_TODO.md — Active (canonical). Phased build plan, acceptance criteria, status.
- CURSOR_SHARED_PIPELINE.md — Active. Architecture, contracts, acceptance; agent roles.
- AGENT_HANDOFF_PLAN.md — Overlapping. Execution plan aligning to MASTER_TODO; keep for context.
- PHASE2_CURSOR.md — Overlapping. Detailed TODOs/acceptance per component; superseded by MASTER_TODO.
- OPERATOR_RUNBOOK.md — Active. Recovery/backup/ops steps.
- TYLER_TODO.md — Overlapping. Operator checklist for keys and run order; aligned with README.
- docs/archive/CURSOR_TODO_FULL.txt — Obsolete (archived). Moved to archive with banner.
- docs/archive/CURSOR_TASKS_AFTER_PAUSE.txt — Obsolete (archived). Moved to archive with banner.

Additional archived items
- docs/archive/sources.yaml — Deprecated config file for API keys, replaced by `.env`

WordPress-related docs/tasks
- conf/blog.example.yaml — Active. Config schema for WP base URL, poster, app password, defaults.
- README.md (Blog Lane section) — Active. Setup + run commands; DRY_RUN notes.
- bin/blog_post_wp.py — Active/Partial. Featured image upload done; inline images pending; DRY_RUN supported via env.
- jobs/state.jsonl — Evidence of dry-run posting and sitemap ping.

Notes on supersession
- MASTER_TODO.md is the SSOT for work items. PHASE2_CURSOR.md and AGENT_HANDOFF_PLAN.md provide narrative and context; task status and acceptance criteria should be updated only in MASTER_TODO.md.


