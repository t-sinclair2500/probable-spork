# Phase 3 — Visual Polish: Texture “Paper Print” + SVG Geometry Ops
Generated: 2025-08-12 17:33:03Z UTC

## Read Me First (MANDATORY for all agents)
1) **Open this README before doing anything.** Use Think → Plan → Apply → Verify.
2) **Scope:** This phase completes and hardens the *visual polish* systems:
   - Paper/print textures (grain, feather, posterize, optional halftone) applied *post-composite, pre-encode* with caching.
   - SVG geometry engine for booleans, offsets, morphs, and programmatic assembly of motifs/icons.
   - Micro‑animations that leverage geometry (subtle morphs, parallax-safe transforms).
3) **Determinism:** All effects must be deterministic (same seed + config → identical output). Cache by signature.
4) **Legibility first:** If a texture harms WCAG contrast or readability, auto-dial back and retry up to 2 times, then WARN.
5) **Graceful degradation:** If optional libs (e.g., `shapely`, `scikit-image`) are missing, degrade with clear WARN and skip only the affected sub-feature.

## Logging & Artifacts
- Log tags: `[texture-core]`, `[texture-integrate]`, `[texture-qa]`, `[geom-core]`, `[motif-core]`, `[micro-anim]`.
- Artifacts (under `runs/<slug>/`):
  - `texture_probe_grid.png` — preview grid of strength/posterize/halftone combos for a representative frame.
  - `geom_validation_report.json` — boolean/morph/offset test results.
  - `style_signature.json` — hashed config of texture + geometry choices used.
- Update `videos/<slug>.metadata.json`:
  - `textures`: enable, parameters, cache hits, fallback notes.
  - `geometry`: ops available, library versions, fallback flags.
  - `micro_animations`: which scenes/elements received morphs, max offset, duration.

## Acceptance Gates (end of Phase 3)
- **Textures:** Enabled by config yield consistent paper/print feel without reducing contrast below AA; cache shows hits on re-run.
- **Geometry validity:** All SVGs produced/modified are valid; no self-intersections that break renderers; booleans work when available.
- **Performance:** Texture pass adds ≤ 15% wall-time to per-scene render on M2 Air (baseline measured without textures); geometry ops complete within budget (<150ms per icon generation on average).

## Config Sources (authoritative in this phase)
- `conf/render.yaml` — `textures.*` (enable, strength, posterize levels, halftone cell/angle/opacity, feather px), `procedural.seed`
- `design/design_language.json` — palette, motif defaults
- `conf/modules.yaml` — toggles for geometry/micro-animations

## Required Verifications (each task adds its own)
- Dry-run the Eames topic and paste: texture cache stats, any auto‑dialbacks, examples of micro‑animation logs, geometry report summary.
- Provide before/after thumbnails for one scene (with texture on vs off).

## Rollback
- All changes must be gated by config flags (`textures.enable`, `geometry.enable`, `micro_anim.enable`) with safe defaults (off). Provide a short rollback note.
