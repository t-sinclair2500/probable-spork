# Phase 2 — Storyboard ↔ Asset Loop Hardening (Reuse-First, Gap-Fill, QA-Reflow)
Generated: 2025-08-12 17:30:12Z UTC

## Read Me First (MANDATORY for all agents)
1) **Open this README before doing anything.** Apply these rules to your task.
2) **Framework:** Think → Plan → Apply → Verify. Every prompt demands a PLAN section first; do not code until the PLAN is written.
3) **Scope:** This phase hardens the asset supply chain: manifest → librarian resolve → generator gap-fill → storyboard reflow → QA gates → acceptance.
4) **Reuse-first policy:** Prefer existing on-brand assets before generating anything new. Only generate when a gap is explicit.
5) **Determinism:** All selection/generation must be deterministic by seed (`conf/render.yaml → procedural.seed`) and palette rules.
6) **Do not break existing call sites.** If `bin/cutout/asset_loop.py` exists, keep a backward-compatible wrapper that calls the new modules.
7) **No external network calls.** Only local assets and procedural generation are allowed in this phase.

## Logging & Artifacts
- Use stage tags in logs: `[manifest]`, `[librarian]`, `[generator]`, `[reflow]`, `[qa-assets]`, `[acceptance-assets]`.
- Artifacts to persist per run (under `runs/<slug>/`):
  - `asset_plan.json` — resolved & gaps list
  - `asset_generation_report.json` — new assets with parameters, seeds, palette
  - `reflow_summary.json` — bounding boxes before/after, adjustments made
- Update `videos/<slug>.metadata.json` with an `assets` block: coverage %, reuse ratio, counts generated, manifest version, palette names used.

## Acceptance Gates (must pass at the end of Phase 2)
- **Coverage:** 100% of storyboard placeholders resolved to concrete assets (no unresolved gaps).
- **Reuse ratio:** ≥70% of assets are reused when a library exists; first-run topic is exempt but must report ratio.
- **Palette compliance:** All assets use approved palette colors from `design/design_language.json` (no ad-hoc hexes).
- **QA clean:** No collisions after reflow; safe margins respected; contrast still passes after reflow.
- **Metadata:** `videos/<slug>.metadata.json` contains `assets` section and `provenance` fields for generated items.

## Config Sources (authoritative in this phase)
- `conf/render.yaml` — procedural seed, safe margins, min spacing, texture toggles
- `conf/modules.yaml` — enable/disable librarian/generator, thresholds, generation caps
- `design/design_language.json` — palette, brand names, shapes/taxonomy (extend if needed)

## Required Verifications (each task adds its own)
- Run the Eames topic dry-run. Paste logs showing selection/generation decisions, final asset coverage, reuse %, and QA results.
- Show snippets of `asset_plan.json`, `asset_generation_report.json`, and `reflow_summary.json`.
- Append a short entry to `jobs/state.jsonl` describing what changed.

## Rollback
- All changes must be gated by config flags with safe defaults. Provide a short rollback note at the end of your change-list.
