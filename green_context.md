# Green Context — Probable Spork (Local-First Video Pipeline)

## Vision & Success Criteria

- **Simple operator experience**: one command to go from topic to finished video
- **Deterministic, idempotent runs**: re-runs with same seed produce same outputs
- **Local-first**: no external SaaS required; optional live research and YouTube publish are explicit toggles
- **Cohesive design language**: distinctive MCM/studio look with legibility and accessibility baked in
- **Healthy performance on M2 8GB**: sequential by default, bounded resource usage, HW accel for encode
- **Observability**: clear logs, artifacts, and QA checks at every stage
- **Monetization-ready quality gates**: explicit PASS thresholds for audio (-14 ±0.5 LUFS, ≤ -1.5 dBTP, LRA ≤ 11), visual legibility (WCAG AA ≥ 4.5:1, text inside title/action safe), and claims (fact-guard = block on unresolved)
- **Premium voice lane**: toggleable local vs premium TTS (SSML-style prosody tags, post-TTS dynamics chain) for publish runs

## Target Platform & Profiles

- **Primary**: macOS (Apple Silicon M2 8GB)
  - Video encode: `h264_videotoolbox` (hardware acceleration)
  - LLM: Ollama (`llama3.2:3b` minimum)
  - Speech: Piper by default; Whisper for captions (local)
- **Secondary**: Raspberry Pi 5 (8GB)
  - Keep sequential execution and low-footprint defaults

## Operator Experience (Golden Path)

- **CLI**: `./venv/bin/python bin/run_pipeline.py --brief conf/brief.yaml --yt-only`
- **Acceptance gate**: `make accept` (or UI button) runs the acceptance harness and must PASS before staging/publish
- **Minimal inputs**: topic or brief; optional research mode (reuse/live) and assets seed
- **Outputs**: `videos/<slug>_cc.mp4`, `videos/<slug>.metadata.json`, `assets/<slug>_animatics/*.mp4`, `voiceovers/<slug>.mp3/.srt`, `scenescripts/<slug>.json`
- **Optional**: `bin/youtube_upload.py` to publish (off by default)

## Current State — High-Level Findings

- **Orchestrator**: robust skeleton, but brittle slug/brief handling and lane-flag semantics; ingestion always tried unless `from-step` set
- **Config fragmentation**: research policy split between `research.yaml` and `models.yaml`; mixed pydantic vs dict access
- **LLM client duplication** (`model_runner.py` vs `llm_client.py`); per-request timeouts missing
- **Research**: reuse mode stubs return zero sources; live providers disabled by default
- **Storyboard/animatics**: palette API mismatch; rasterization callers sometimes pass Scenes
- **Audio/video**: VO discovery brittle; good HW accel path on macOS; music integration present but optional
- **Docs/branding** still Pi-first in places

## Key Context for LLMs

This is a **local-first video content generation pipeline** that researches topics, writes outlines and scripts, grounds/fact-checks content, creates storyboards with MCM design language, renders animatics, generates audio, assembles videos with captions and thumbnails, and optionally publishes to YouTube.

The codebase has recently undergone a **complete WordPress/blog code eradication** (4,306 lines removed) and is now a **pure YouTube content generation pipeline**. All WordPress/blog functionality has been completely removed from the codebase.

The primary target is **Mac M2 8GB** with **Raspberry Pi 5** as a secondary supported platform. The system is designed to be **deterministic and idempotent** with clear quality gates for monetization-ready content.

For detailed implementation plans, see `codex_greenlight.md`.
