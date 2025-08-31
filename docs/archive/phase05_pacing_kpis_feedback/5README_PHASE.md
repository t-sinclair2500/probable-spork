# Phase 5 — Pacing KPIs & One‑Pass Feedback Loop
Generated: 2025-08-12 17:39:03Z UTC

## Read Me First (MANDATORY for all agents)
1) **Open this README before doing anything.** Use Think → Plan → Apply → Verify. Begin each task with a PLAN section; do not write code until the plan is approved in your own log.
2) **Scope:** Compute pacing metrics (words/sec, cuts/min, avg scene length, speech/music ratio), compare against **intent-specific bands**, and run a **single deterministic feedback pass** that nudges scene durations into band without harming VO alignment, legibility, or layout constraints.
3) **Determinism:** Same brief + seed + assets + SRT must produce identical KPIs and the same adjustments.
4) **Priority of truth:** If `timing.align_to_vo=true` and SRT exists, **VO timing is primary**. Visual timing must conform to VO windows. If not enabled, use brief target as primary.
5) **Safety bounds:** The feedback adjuster may shift any scene by **±0.5–1.0s max**, must respect min/max clamps from config, must not exceed total target tolerance from Phase 1, and must not break layout/QA.
6) **Idempotence:** Only one feedback iteration per run. Write an audit trail to metadata. If still out of band, acceptance should WARN/FAIL per rules, not loop again.

## Logging & Artifacts
- Log tags: `[pacing-kpi]`, `[pacing-compare]`, `[pacing-feedback]`, `[pacing-accept]`.
- Artifacts (under `runs/<slug>/`):
  - `pacing_report.json` — raw metrics + per-scene durations + flags before/after feedback.
  - `pacing_adjustments.json` — the exact adjustments proposed/applied.
- Update `videos/<slug>.metadata.json`:
  - `pacing`: words_per_sec, cuts_per_min, avg_scene_s, speech_music_ratio, bands, flags, adjusted:boolean.

## Acceptance Gates (end of Phase 5)
- KPIs computed and stored in metadata.
- If metrics are **outside band by >10%**, a single feedback pass is attempted.
- After feedback:
  - If within band → PASS.
  - If still outside by >10% → WARN (non-strict) or FAIL (strict) per config.
- No layout collisions or contrast regressions introduced by adjustments.

## Config Sources (authoritative in this phase)
- `conf/intent_profiles.yaml` — bands per intent (min/max for each metric).
- `conf/render.yaml` — timing clamps, `timing.target_tolerance_pct`, `timing.align_to_vo`.
- `conf/modules.yaml` — `pacing.enable`, `pacing.strict`, `pacing.max_adjust_ms_per_scene` (default 1000), `pacing.max_total_adjust_ms`.
- `conf/brief.yaml` — video target length and selected intent.

## Required Verifications (each task adds its own)
- Dry‑run the Eames topic; paste KPI metrics pre/post, flags, and acceptance snippet.
- Confirm `adjusted=true/false` recorded; show at least one scene’s before/after duration.

## Rollback
- All changes gated by `pacing.enable`. Provide a short rollback note in your change-list.
