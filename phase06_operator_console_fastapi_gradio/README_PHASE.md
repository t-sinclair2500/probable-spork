# Phase 6 — Operator Console: FastAPI Orchestrator + Gradio UI
Generated: 2025-08-12 17:46:52Z UTC

## Read Me First (MANDATORY for all agents)
1) **Open this README before doing anything.** Apply these rules to every task.
2) **Framework:** Think → Plan → Apply → Verify. Each prompt requires a PLAN section **before** implementation.
3) **Scope:** Build a minimal, reliable **FastAPI** orchestrator that runs the video pipeline with **HITL gates** and a thin **Gradio** control surface. Favor simplicity over cleverness.
4) **Determinism:** Orchestrator must not change pipeline logic; it should call existing modules and respect seeds/config.
5) **No vendor lock:** Start with **in‑process background tasks**. Provide optional Redis queue hooks but keep a zero‑dep path working on a MacBook Air.
6) **HITL:** Pausable stages with Approve/Reject/Resume; decisions stored durably per job.
7) **Storage:** Use `runs/<job_id>/...` for artifacts + a lightweight **SQLite** DB for job metadata. Do not break existing artifacts written by the pipeline.
8) **Security:** Default to **local‑only** (`127.0.0.1`), Bearer token via `ADMIN_TOKEN` env, CORS disabled by default.
9) **Observability:** Add a structured log handler and an **SSE** endpoint for live events; also support polling for environments where SSE is blocked.

## Logging & Artifacts
- Log tags: `[api]`, `[orchestrator]`, `[stage]`, `[gate]`, `[events]`, `[ui]`.
- Artifacts required:
  - `runs/<job_id>/state.json` — current state snapshot (stage, status, timestamps).
  - `runs/<job_id>/events.jsonl` — event stream (append‑only).
  - `runs/<job_id>/artifacts/` — symlink or copy of key outputs (script, storyboard, srt, mp4, acceptance).
- Update `jobs/state.jsonl` at repo root on major transitions (`queued`, `running`, `paused`, `needs_approval`, `completed`, `failed`).

## Job Model (canonical fields)
- `id`, `slug`, `intent`, `status` = one of {queued, running, paused, needs_approval, completed, failed, canceled}
- `stage` = one of {outline, research, script, storyboard, assets, animatics, audio, assemble, acceptance}
- `cfg` (snapshot of brief/render/models/modules), `created_at`, `updated_at`
- `gates`: list of `{stage, required: bool, approved: bool|null, by, at, notes}`
- `artifacts[]`: list of `{stage, kind, path, meta}`

## Acceptance for this Phase (end criteria)
- From a clean terminal: `make op-console` starts FastAPI + Gradio.
- Operator can **submit a job**, watch stage‑by‑stage progress, **approve/reject** at Script, Storyboard+Assets, and Audio gates, and **download** the final MP4 and acceptance report.
- SSE stream shows stage events in real time; polling fallback works.
- Security on by default: local‑only bind + token auth; CORS disabled unless enabled in config.
- No extra infra required; optional Redis queue documented but not required.

## Config Sources (authoritative in this phase)
- `conf/global.yaml`, `conf/render.yaml`, `conf/modules.yaml`, `conf/brief.yaml`
- New (introduced here): `conf/operator.yaml` → server port, bind, auth, CORS, gate defaults, timeouts.

## Rollback
- Orchestrator runs in its own package folder (`fastapi_app/`, `ui/`). A single `make clean-op-console` target removes it without touching the core pipeline.
