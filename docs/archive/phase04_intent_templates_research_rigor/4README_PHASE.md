# Phase 4 — Intent Templates + Research Rigor (Grounded, Template-Driven Content)
Generated: 2025-08-12 17:36:19Z UTC

## Read Me First (MANDATORY for all agents)
1) **Open this README before doing anything.** Use Think → Plan → Apply → Verify. Every prompt begins with PLAN-ONLY; do not code until your plan is written.
2) **Scope:** Make outputs *intent-aware* and *evidence-grounded*. Separate “what’s trending” from “what’s true.” Enforce citations and domain quality.
3) **Determinism:** Given same brief, seed, and cache, stages must produce identical results.
4) **No network surprises:** Provide two modes—`reuse` (cache-only, no external calls) and `live` (with rate limits/backoff). The default for tests is **reuse**.
5) **Model discipline:** Research planning/grounding must use the **research model** (e.g., Mistral-7B instruct); scripting/outline polish uses the **script model** (e.g., Llama 3.2). Respect `conf/models.yaml` bindings.
6) **Security & provenance:** Never store credentials in code. All snippets must have URL, title, timestamp, domain, and extract method recorded.

## Logging & Artifacts
- Log tags: `[intent]`, `[outline]`, `[script]`, `[trending]`, `[collect]`, `[ground]`, `[fact-guard]`, `[citations]`, `[acceptance-research]`.
- Artifacts per run (under `runs/<slug>/research/`):
  - `trending_topics.json` (if intake used)
  - `snippets.json` (raw snippets w/ metadata)
  - `references.json` (deduped, normalized citations)
  - `grounded_beats.json` (beats with citations inlined)
  - `fact_guard_report.json` (claims kept/removed/rewritten)
- Update `videos/<slug>.metadata.json` with `citations` block: counts, domains, recency stats, coverage (% beats with ≥1 citation).

## Acceptance Gates (end of Phase 4)
- **Intent correctness:** Outline/script reflect the selected template; CTA policy honored (e.g., `narrative_history` → no CTA).
- **Citation minimums:** For `narrative_history`/`analysis`, ≥1 citation per beat on average and ≥60% beats with ≥1 citation each.
- **Domain quality:** All citations from whitelisted domains unless operator overrides; warn on others.
- **Cache discipline:** `reuse` mode produces the same results across re-runs; `live` mode writes cache for future reuse.
- **Research hygiene:** No orphan factual claims (dates, names, firsts) without a source after fact-guard.

## Config Sources (authoritative in this phase)
- `conf/intent_templates.yaml` — intent types, beat templates, CTA policy, tone defaults
- `conf/research.yaml` — whitelists, blacklist, rate limits, backoff, reuse/live toggle
- `conf/models.yaml` — research vs script model bindings
- `conf/global.yaml` — seeds, testing mode

## Required Verifications (each task adds its own)
- Dry-run the Eames topic in **reuse** mode; paste outline beats, citations stats, any fact-guard removals, and acceptance snippet.
- Run one **live** collection with strict rate limits; show cache files created and subsequent reuse run equivalence.

## Rollback
- All changes behind flags and config with safe defaults. Provide a short rollback note at the end of your change-set.
