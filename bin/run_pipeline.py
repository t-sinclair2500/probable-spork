#!/usr/bin/env python3
"""
Unified Pipeline Orchestrator for YouTube + Blog Content Generation

This script orchestrates the entire content pipeline in a single daily run,
replacing the fragmented cron jobs with lock-aware sequential execution.
"""

import argparse
import os
import subprocess
import sys
import time
from typing import Dict, List, Optional

from pathlib import Path

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.cli.args import build_common_parser as _common_args
from bin.contracts.exit_codes import FAIL as EC_FAIL
from bin.contracts.exit_codes import INTERRUPTED as EC_INTR
from bin.contracts.exit_codes import OK as EC_OK
from bin.contracts.exit_codes import PARTIAL as EC_PARTIAL
from bin.contracts.paths import artifact_paths, ensure_dirs_for_slug
from bin.core import (
    BASE,
    get_logger,
    guard_system,
    load_config,
    load_env,
    load_modules_cfg,
    log_state,
    single_lock,
)
from bin.orchestrator.state import StateMachine, Step
from bin.utils.config import _read_yaml, load_all_configs, load_pipeline_config
from bin.utils.flags import compute_viral_flags
from bin.utils.logs import audit_event, get_logger
from bin.utils.platform import get_recommended_profile
from bin.utils.subproc import run_streamed


def _policy_for(step_name: str, pipeline_cfg):
    pol = pipeline_cfg.steps.get(step_name)
    # Default: required true if not specified
    if pol is None:
        return {"required": True, "on_fail": "block"}
    return {"required": bool(pol.required), "on_fail": pol.on_fail}


log = get_logger("run_pipeline")


def run_step(
    step_name: str,
    cmd: list[str],
    env: dict | None = None,
    cwd: str | None = None,
    notes: str = "",
    pipeline_cfg=None,
) -> str:
    """
    Execute a pipeline step with centralized policy and structured logging.
    Returns status: "OK" | "FAIL" | "PARTIAL" | "SKIP"
    """
    pol = _policy_for(step_name, pipeline_cfg)
    required = pol["required"]
    on_fail = pol["on_fail"]

    start = time.time()
    audit_event(step_name, "START", cmd=" ".join(cmd), notes=notes)
    log.info(f"[{step_name}] starting ({'required' if required else 'optional'})")

    log_path = os.path.join("logs", "subprocess", f"{step_name}.log")
    try:
        rc = run_streamed(
            cmd, cwd=cwd, env=env, log_path=log_path, tail_lines=200, check=True
        )
        dur_ms = int((time.time() - start) * 1000)
        audit_event(step_name, "OK", rc=rc, duration_ms=dur_ms, log_path=log_path)
        log.info(f"[{step_name}] OK in {dur_ms} ms")
        return "OK"
    except Exception as e:
        dur_ms = int((time.time() - start) * 1000)
        msg = str(e)
        # Apply policy
        if required or on_fail == "block":
            audit_event(
                step_name, "FAIL", error=msg, duration_ms=dur_ms, log_path=log_path
            )
            log.error(f"[{step_name}] FAIL in {dur_ms} ms: {msg}")
            raise
        elif on_fail == "skip":
            audit_event(
                step_name, "SKIP", error=msg, duration_ms=dur_ms, log_path=log_path
            )
            log.warning(f"[{step_name}] SKIP (optional) in {dur_ms} ms: {msg}")
            return "SKIP"
        else:
            # warn
            audit_event(
                step_name, "PARTIAL", error=msg, duration_ms=dur_ms, log_path=log_path
            )
            log.warning(
                f"[{step_name}] PARTIAL (optional; continuing) in {dur_ms} ms: {msg}"
            )
            return "PARTIAL"


# Blog publish checking now handled by centralized get_publish_flags() in bin.core


def _should_run_shared_ingestion(args) -> bool:
    """
    Strict policy:
    - If --yt-only is set: NEVER run shared ingestion.
    - Otherwise: run ingestion as usual.
    """
    # Skip ingestion under --yt-only unless operator explicitly sets --from-step to ingestion
    if getattr(args, "yt_only", False):
        fs = getattr(args, "from_step", None)
        if fs:
            # Strip whitespace and normalize
            fs_clean = fs.strip().lower()
            return fs_clean in {
                "ingest",
                "ingestion",
                "research_collect",
                "shared_ingestion",
            }
        return False
    return True


def _deep_merge(a: dict, b: dict) -> dict:
    """Deep merge two dictionaries."""
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_with_profile(base_cfg: dict, profile_name: str | None) -> dict:
    """Load configuration with profile overlay."""
    if not profile_name:
        return base_cfg

    prof_map = {
        "m2_8gb_optimized": "conf/m2_8gb_optimized.yaml",
        "pi_8gb": "conf/pi_8gb.yaml",
    }

    p = prof_map.get(profile_name)
    if not p or not Path(p).exists():
        log.warning(f"Profile {profile_name} not found; continuing without overlay.")
        return base_cfg

    try:
        overlay = _read_yaml(p)
        merged = _deep_merge(base_cfg, overlay)
        log.info(f"Loaded profile overlay: {profile_name} ({p})")
        return merged
    except Exception as e:
        log.warning(f"Failed to load profile {profile_name}: {e}")
        return base_cfg


def load_brief(brief_path: Optional[str] = None) -> Optional[Dict[str, any]]:
    """
    Load the workstream brief from the specified path or default locations.

    Args:
        brief_path: Optional path to brief file, defaults to conf/brief.yaml then conf/brief.md

    Returns:
        Brief configuration dict or None if no brief found
    """
    try:
        from bin.brief_loader import load_brief as _load_brief

        if brief_path:
            # Load from specific path
            if brief_path.endswith(".yaml") or brief_path.endswith(".yml"):
                import yaml

                with open(brief_path, "r", encoding="utf-8") as f:
                    brief = yaml.safe_load(f)
                brief["_source"] = "custom_yaml"
            elif brief_path.endswith(".md"):
                from bin.brief_loader import from_markdown_front_matter

                brief = from_markdown_front_matter(brief_path)
                brief["_source"] = "custom_markdown"
            else:
                log.warning(f"Unsupported brief file format: {brief_path}")
                return None
        else:
            # Load from default locations
            brief = _load_brief()

        log.info(
            f"Loaded brief: {brief.get('title', 'Untitled')} from {brief.get('_source', 'unknown')}"
        )
        return brief

    except Exception as e:
        log.warning(f"Failed to load brief: {e}")
        return None


def inject_brief_environment(brief: Dict[str, any]) -> Dict[str, str]:
    """
    Convert brief data to environment variables for step scripts.

    Args:
        brief: Brief configuration dictionary

    Returns:
        Dictionary of environment variables to inject
    """
    env_vars = {}

    if not brief:
        return env_vars

    # Core brief fields
    if brief.get("title"):
        env_vars["BRIEF_TITLE"] = brief["title"]
    if brief.get("tone"):
        env_vars["BRIEF_TONE"] = brief["tone"]
    if brief.get("audience"):
        env_vars["BRIEF_AUDIENCE"] = ",".join(brief["audience"])

    # Video settings
    if brief.get("video"):
        video = brief["video"]
        if video.get("target_length_min"):
            env_vars["BRIEF_VIDEO_LENGTH_MIN"] = str(video["target_length_min"])
        if video.get("target_length_max"):
            env_vars["BRIEF_VIDEO_LENGTH_MAX"] = str(video["target_length_max"])

    # Keywords
    if brief.get("keywords_include"):
        env_vars["BRIEF_KEYWORDS_INCLUDE"] = ",".join(brief["keywords_include"])
    if brief.get("keywords_exclude"):
        env_vars["BRIEF_KEYWORDS_EXCLUDE"] = ",".join(brief["keywords_exclude"])

    # Sources
    if brief.get("sources_preferred"):
        env_vars["BRIEF_SOURCES_PREFERRED"] = ",".join(brief["sources_preferred"])

    # Monetization
    if brief.get("monetization"):
        monetization = brief["monetization"]
        if monetization.get("cta_text"):
            env_vars["BRIEF_CTA_TEXT"] = monetization["cta_text"]
        if monetization.get("primary"):
            env_vars["BRIEF_MONETIZATION_PRIMARY"] = ",".join(monetization["primary"])

    # Notes
    if brief.get("notes"):
        env_vars["BRIEF_NOTES"] = brief["notes"]

    # Source info
    env_vars["BRIEF_SOURCE"] = brief.get("_source", "unknown")

    return env_vars


# ---- Minimal greenlight orchestrator path (opt-in) ----
def _run_minimal_orchestrator(argv: Optional[list] = None) -> int:
    """Optional streamlined path using the new state machine and config bundle."""
    # Parse only common args to avoid clobbering legacy CLI
    ap = argparse.ArgumentParser(parents=[_common_args()], add_help=True)
    args = ap.parse_args(argv)

    cfg = load_all_configs(
        profile=args.profile,
        cli_overrides=(
            {("research"): {"policy": {"mode": args.mode}}} if args.mode else None
        ),
    )
    slug = args.slug or "untitled"
    ensure_dirs_for_slug(slug)

    pol = getattr(cfg, "pipeline").steps if hasattr(cfg, "pipeline") else {}
    apaths = artifact_paths(slug)

    steps = [
        Step(
            "research_collect",
            [
                sys.executable,
                os.path.join(BASE, "bin", "research_collect.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("research_collect", {}).get("required", True)
                if isinstance(pol, dict)
                else True
            ),
            on_fail=(
                pol.get("research_collect", {}).get("on_fail", "block")
                if isinstance(pol, dict)
                else "block"
            ),
            idempotent_outputs=[str(apaths["research_sources"])],
        ),
        Step(
            "research_ground",
            [
                sys.executable,
                os.path.join(BASE, "bin", "research_ground.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("research_ground", {}).get("required", True)
                if isinstance(pol, dict)
                else True
            ),
            on_fail=(
                pol.get("research_ground", {}).get("on_fail", "block")
                if isinstance(pol, dict)
                else "block"
            ),
            idempotent_outputs=[
                str(apaths["grounded_beats"]),
                str(apaths["references"]),
            ],
        ),
        Step(
            "storyboard",
            [
                sys.executable,
                os.path.join(BASE, "bin", "storyboard_plan.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("storyboard", {}).get("required", True)
                if isinstance(pol, dict)
                else True
            ),
            idempotent_outputs=[str(apaths["scenescript"])],
        ),
        Step(
            "animatics",
            [
                sys.executable,
                os.path.join(BASE, "bin", "animatics_generate.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("animatics", {}).get("required", True)
                if isinstance(pol, dict)
                else True
            ),
            idempotent_outputs=[str(apaths["animatics_dir"])],
        ),
        Step(
            "audio",
            [
                sys.executable,
                os.path.join(BASE, "bin", "tts_generate.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("audio", {}).get("required", True)
                if isinstance(pol, dict)
                else True
            ),
            idempotent_outputs=[
                str(apaths["voiceover_mp3"]),
                str(apaths["voiceover_srt"]),
            ],
        ),
        Step(
            "assemble",
            [
                sys.executable,
                os.path.join(BASE, "bin", "assemble_video.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("assemble", {}).get("required", True)
                if isinstance(pol, dict)
                else True
            ),
            idempotent_outputs=[str(apaths["video_cc"]), str(apaths["video_meta"])],
        ),
        Step(
            "quality_gates",
            [
                sys.executable,
                os.path.join(BASE, "bin", "qa", "run_gates.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("quality_gates", {}).get("required", True)
                if isinstance(pol, dict)
                else True
            ),
            on_fail=(
                pol.get("quality_gates", {}).get("on_fail", "block")
                if isinstance(pol, dict)
                else "block"
            ),
            idempotent_outputs=[str(Path("reports") / slug / "qa_report.json")],
        ),
        Step(
            "viral_lab",
            [
                sys.executable,
                os.path.join(BASE, "bin", "viral", "run.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("viral_lab", {}).get("required", False)
                if isinstance(pol, dict)
                else False
            ),
            on_fail=(
                pol.get("viral_lab", {}).get("on_fail", "skip")
                if isinstance(pol, dict)
                else "skip"
            ),
            idempotent_outputs=[str(Path("videos") / slug / "metadata.json")],
        ),
        Step(
            "shorts_lab",
            [
                sys.executable,
                os.path.join(BASE, "bin", "viral", "shorts.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("shorts_lab", {}).get("required", False)
                if isinstance(pol, dict)
                else False
            ),
            on_fail=(
                pol.get("shorts_lab", {}).get("on_fail", "skip")
                if isinstance(pol, dict)
                else "skip"
            ),
            idempotent_outputs=[str(Path("videos") / slug / "shorts")],
        ),
        Step(
            "seo_packaging",
            [
                sys.executable,
                os.path.join(BASE, "bin", "packaging", "seo_packager.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("seo_packaging", {}).get("required", True)
                if isinstance(pol, dict)
                else True
            ),
            on_fail=(
                pol.get("seo_packaging", {}).get("on_fail", "block")
                if isinstance(pol, dict)
                else "block"
            ),
            idempotent_outputs=[str(Path("videos") / slug / "metadata.json")],
        ),
        Step(
            "end_screens",
            [
                sys.executable,
                os.path.join(BASE, "bin", "packaging", "end_screens.py"),
                "--slug",
                slug,
            ],
            required=(
                pol.get("end_screens", {}).get("required", False)
                if isinstance(pol, dict)
                else False
            ),
            on_fail=(
                pol.get("end_screens", {}).get("on_fail", "skip")
                if isinstance(pol, dict)
                else "skip"
            ),
            idempotent_outputs=[str(Path("assets") / "generated" / slug)],
        ),
    ]

    def _runner(step_name: str, cmd: list[str]) -> str:
        log_path = os.path.join("logs", "subprocess", f"{step_name}.log")
        try:
            rc = run_streamed(
                cmd,
                cwd=BASE,
                env=os.environ.copy(),
                log_path=log_path,
                tail_lines=200,
                check=True,
            )
            audit_event(step_name, "OK", rc=rc, log_path=log_path)
            return "OK"
        except Exception as e:
            audit_event(step_name, "PARTIAL", error=str(e), log_path=log_path)
            # Policy handling is minimal here; required/optional can be extended if desired
            return "PARTIAL"

    sm = StateMachine(steps, runner=_runner)
    try:
        status = sm.run(force=args.force)
    except KeyboardInterrupt:
        audit_event("pipeline", "TIMEOUT", notes="interrupted")
        return EC_INTR
    except Exception as e:
        log.error(f"Minimal orchestrator error: {e}")
        audit_event("pipeline", "FAIL", error=str(e))
        return EC_FAIL

    return EC_OK if status == "OK" else EC_PARTIAL


def run_step_legacy(
    script_name: str,
    args: List[str] = None,
    required: bool = True,
    brief_env: Dict[str, str] = None,
    brief_data: Dict[str, any] = None,
    models_config: Dict = None,
    pipeline_cfg=None,
) -> bool:
    """
    Legacy wrapper for run_step with centralized policy.
    """
    script_path = os.path.join(BASE, "bin", f"{script_name}.py")
    if not os.path.exists(script_path):
        log.error(f"Script not found: {script_path}")
        if required:
            raise SystemExit(f"Required script missing: {script_name}")
        return False

    cmd = [sys.executable, script_path]

    # Add brief data as JSON argument if available
    if brief_data:
        import json

        brief_json = json.dumps(brief_data)
        cmd.extend(["--brief-data", brief_json])

    if args:
        cmd.extend(args)

    start_time = time.time()

    try:
        log.info(f"Starting step: {script_name}")

        # Prepare environment with brief data
        env = os.environ.copy()
        if brief_env:
            env.update(brief_env)
            log.debug(
                f"Injected {len(brief_env)} brief environment variables for {script_name}"
            )

        # Use streamed subprocess with logging
        log_path = os.path.join("logs", "subprocess", f"{script_name}.log")
        try:
            rc = run_streamed(
                cmd,
                cwd=BASE,
                env=env,
                log_path=log_path,
                tail_lines=200,
                text=True,
                check=False,  # We'll handle the return code ourselves
                echo=True,
            )

            elapsed_ms = int((time.time() - start_time) * 1000)

            if rc == 0:
                log_state(script_name, "OK", f"elapsed_ms={elapsed_ms}")
                log.info(f"Step completed: {script_name} ({elapsed_ms}ms)")
                return True
            else:
                log_state(
                    script_name, "FAIL", f"exit_code={rc};elapsed_ms={elapsed_ms}"
                )
                log.error(f"Step failed: {script_name} (exit {rc})")

                if required:
                    raise SystemExit(f"Required step failed: {script_name}")
                return False

        except RuntimeError as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            log_state(
                script_name, "FAIL", f"exception={str(e)};elapsed_ms={elapsed_ms}"
            )
            log.error(f"Step failed: {script_name} - {e}")

            if required:
                raise SystemExit(f"Required step failed: {script_name}")
            return False

    except subprocess.TimeoutExpired:
        log_state(script_name, "TIMEOUT", "timeout=3600s")
        log.error(f"Step timed out: {script_name}")
        if required:
            raise SystemExit(f"Required step timed out: {script_name}")
        return False

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        log_state(script_name, "ERROR", f"exception={str(e)};elapsed_ms={elapsed_ms}")
        log.error(f"Step error: {script_name} - {e}")
        if required:
            raise SystemExit(f"Step error: {script_name} - {e}")
        return False


def _run_llm_step(
    script_name: str,
    model_name: str,
    args: List[str] = None,
    required: bool = True,
    brief_env: Dict[str, str] = None,
    brief_data: Dict[str, any] = None,
    pipeline_cfg=None,
) -> bool:
    """Execute LLM step using model session context manager."""
    try:
        log.info(f"Starting LLM step: {script_name} with model {model_name}")

        # Import model_runner here to avoid circular imports
        from bin.model_runner import model_session

        # Set environment variables for the model session
        env = os.environ.copy()
        if brief_env:
            env.update(brief_env)

        # Use model session context manager
        with model_session(model_name) as session:
            # For now, we'll still use subprocess but the model session ensures
            # the model is loaded and will be unloaded when the context exits
            # In the future, we could refactor to call LLM functions directly
            log.info(f"Model session active for {model_name}")

            # Run the actual step
            return _run_subprocess_step(
                script_name, args, required, brief_env, brief_data, pipeline_cfg
            )

    except Exception as e:
        log.error(f"LLM step error: {script_name} - {e}")
        if required:
            raise SystemExit(f"Required LLM step failed: {script_name}")
        return False


def _run_subprocess_step(
    script_name: str,
    args: List[str] = None,
    required: bool = True,
    brief_env: Dict[str, str] = None,
    brief_data: Dict[str, any] = None,
    pipeline_cfg=None,
) -> bool:
    """Execute step using subprocess with centralized policy."""
    cmd = [sys.executable, os.path.join(BASE, "bin", f"{script_name}.py")]

    # Add brief data as JSON argument if available
    if brief_data:
        import json

        brief_json = json.dumps(brief_data)
        cmd.extend(["--brief-data", brief_json])

    if args:
        cmd.extend(args)

    # Prepare environment with brief data
    env = os.environ.copy()
    if brief_env:
        env.update(brief_env)
        log.debug(
            f"Injected {len(brief_env)} brief environment variables for {script_name}"
        )

    # Use centralized run_step with policy enforcement
    try:
        status = run_step(
            script_name,
            cmd,
            env=env,
            cwd=BASE,
            notes="subprocess step",
            pipeline_cfg=pipeline_cfg,
        )
        return status == "OK"
    except Exception:
        # run_step already handles policy and logging
        return False


def run_youtube_lane(
    cfg,
    args=None,
    dry_run: bool = False,
    brief_env: Dict[str, str] = None,
    brief_data: Dict[str, any] = None,
    models_config: Dict = None,
) -> bool:
    """Execute YouTube content generation lane"""
    log.info("=== STARTING YOUTUBE LANE ===")

    success = True

    # Load pipeline configuration for video production steps
    pipeline_cfg = load_pipeline_config()

    # Phase 4: YouTube lane (per spec)
    # Convert Pydantic model to dict for compatibility
    pipeline_dict = pipeline_cfg.model_dump() if hasattr(pipeline_cfg, 'model_dump') else pipeline_cfg.__dict__
    video_steps_raw = pipeline_dict.get("execution", {}).get(
        "video_production",
        ["tts_generate", "generate_captions", "assemble_video", "make_thumbnail"],
    )

    # Convert to tuples with required flags
    video_steps = []
    for step in video_steps_raw:
        if step == "generate_captions":
            video_steps.append(
                (step, False)
            )  # Optional - graceful skip if whisper.cpp missing
        else:
            video_steps.append((step, True))

    for step_name, required in video_steps:
        # Pass slug to video production steps if available
        step_args = []
        if slug:
            step_args = ["--slug", slug]
        
        step_success = run_step_legacy(
            step_name, args=step_args, required=required, brief_env=brief_env, brief_data=brief_data
        )
        if not step_success and required:
            success = False
            break

    # Use provided slug or extract from the most recent script file for viral steps
    slug = None
    if args and hasattr(args, "slug") and args.slug:
        slug = args.slug
        log.info(f"Using provided slug: {slug}")
    else:
        import glob

        script_files = glob.glob(os.path.join(BASE, "scripts", "*.txt"))
        if script_files:
            # Use the most recent script file
            script_files.sort(reverse=True)
            latest_script = script_files[0]
            # Extract slug from filename using robust utility
            from bin.utils.slug import safe_slug_from_script

            slug = safe_slug_from_script(latest_script)
            log.info(f"Extracted slug '{slug}' from script: {latest_script}")
        else:
            log.warning("No script files found, viral steps may fail")

    # Phase 5: Viral steps (after assemble + thumbnails, before QA)
    if args and slug:
        # Compute viral flags based on CLI args and config
        viral_flags = compute_viral_flags(args, cfg)

        # Viral lab step (optional)
        if viral_flags["viral_on"]:
            log.info("=== RUNNING VIRAL LAB ===")
            viral_cmd = ["python", "bin/viral/run.py", "--slug", slug]
            if hasattr(args, "seed") and args.seed:
                viral_cmd.extend(["--seed", str(args.seed)])
            rc = run_streamed(
                viral_cmd, log_path=f"logs/subprocess/viral_lab_{slug}.log", check=False
            )
            if rc != 0:
                log.warning(f"[viral_lab] rc={rc} (continuing)")
        else:
            log.info("[viral_lab] disabled by flag/config")

        # Shorts lab step (optional)
        if viral_flags["shorts_on"]:
            log.info("=== RUNNING SHORTS LAB ===")
            shorts_cmd = ["python", "bin/viral/shorts.py", "--slug", slug]
            if hasattr(args, "seed") and args.seed:
                shorts_cmd.extend(["--seed", str(args.seed)])
            rc = run_streamed(
                shorts_cmd,
                log_path=f"logs/subprocess/shorts_lab_{slug}.log",
                check=False,
            )
            if rc != 0:
                log.warning(f"[shorts_lab] rc={rc} (continuing)")
        else:
            log.info("[shorts_lab] disabled by flag/config")

        # SEO packaging step (required if enabled)
        if viral_flags["seo_on"]:
            log.info("=== RUNNING SEO PACKAGING ===")
            rc = run_streamed(
                ["python", "bin/packaging/seo_packager.py", "--slug", slug],
                log_path=f"logs/subprocess/seo_packaging_{slug}.log",
                check=True,
            )
            if rc != 0:
                log.error(f"[seo_packaging] rc={rc} (failing)")
                success = False
        else:
            log.info("[seo_packaging] disabled by flag/config")

        # End screens step (optional, requires SEO)
        if viral_flags["seo_on"]:
            log.info("=== RUNNING END SCREENS ===")
            rc = run_streamed(
                ["python", "bin/packaging/end_screens.py", "--slug", slug],
                log_path=f"logs/subprocess/end_screens_{slug}.log",
                check=False,
            )
            if rc != 0:
                log.warning(f"[end_screens] rc={rc} (continuing)")
        else:
            log.info("[end_screens] disabled (SEO disabled)")

    # Phase 6: QA gates (after viral steps, blocks upload)
    if success and slug:
        log.info("=== RUNNING QA GATES ===")
        qa_rc = run_streamed(
            ["python", "bin/qa/run_gates.py", "--slug", slug],
            log_path=f"logs/subprocess/qa_{slug}.log",
            check=False,
        )
        if qa_rc != 0:
            log.error(
                f"[QA] Blocking publish for slug={slug} (exit={qa_rc}). See reports/{slug}/qa_report.*"
            )
            success = False
        else:
            log.info("[QA] Gates passed, proceeding to upload")

    # Phase 7: Upload stage (only if QA passes)
    if success:
        log.info("=== RUNNING UPLOAD STAGE ===")
        upload_success = run_step_legacy(
            "upload_stage", required=True, brief_env=brief_env, brief_data=brief_data
        )
        if not upload_success:
            success = False

    log.info(f"=== YOUTUBE LANE {'COMPLETED' if success else 'FAILED'} ===")
    return success


def run_shared_ingestion(
    cfg,
    from_step: Optional[str] = None,
    brief_env: Optional[Dict[str, str]] = None,
    brief_data: Optional[Dict] = None,
    models_config: Optional[Dict] = None,
    no_style_rewrite: bool = False,
    slug: Optional[str] = None,
) -> bool:
    """Execute shared data ingestion steps with batch-by-model execution"""
    log.info("=== STARTING SHARED INGESTION (BATCH-BY-MODEL) ===")

    success = True

    # Load pipeline configuration
    pipeline_cfg = load_pipeline_config()

    # Load models configuration if not provided
    if models_config is None:
        try:
            import yaml

            models_path = os.path.join(BASE, "conf", "models.yaml")
            if os.path.exists(models_path):
                with open(models_path, "r", encoding="utf-8") as f:
                    models_config = yaml.safe_load(f)
                log.info("Loaded models configuration for batch execution")
            else:
                log.warning("No models.yaml found, using default configuration")
                models_config = {}
        except Exception as e:
            log.warning(f"Failed to load models configuration: {e}")
            models_config = {}

    # Get execution steps from pipeline configuration or use defaults
    # Handle both Pydantic model and dict for backward compatibility
    if hasattr(pipeline_cfg, "execution"):
        shared_steps = getattr(
            pipeline_cfg.execution,
            "shared_ingestion",
            [
                "niche_trends",
                "llm_cluster",
                "llm_outline",
                "llm_script",
                "research_collect",
                "research_ground",
                "fact_check",
            ],
        )
    else:
        # Fallback for dict-based config
        # Convert Pydantic model to dict for compatibility
        pipeline_dict = pipeline_cfg.model_dump() if hasattr(pipeline_cfg, 'model_dump') else pipeline_cfg.__dict__
        shared_steps = pipeline_dict.get("execution", {}).get(
            "shared_ingestion",
            [
                "niche_trends",
                "llm_cluster",
                "llm_outline",
                "llm_script",
                "research_collect",
                "research_ground",
                "fact_check",
            ],
        )

    # Define execution batches by model type
    batches = [
        {
            "name": "Llama 3.2 Batch (Cluster + Outline + Script)",
            "model": (
                models_config.get("models", {})
                .get("cluster", {})
                .get("name", "llama3.2:3b")
                if models_config
                else "llama3.2:3b"
            ),
            "steps": [
                (step, True) for step in shared_steps[:4]  # First 4 steps are required
            ],
        },
        {
            "name": "Llama 3.2 Batch (Research + Fact-Check)",
            "model": (
                models_config.get("models", {})
                .get("research", {})
                .get("name", "llama3.2:3b")
                if models_config
                else "llama3.2:3b"
            ),
            "steps": [
                (step, False)
                for step in shared_steps[4:]  # Remaining steps are optional
            ],
        },
    ]

    # Optional final batch for script refinement (if enabled and not skipped)
    if (
        not no_style_rewrite
        and models_config
        and models_config.get("models", {}).get("scriptwriter", {}).get("name")
    ):
        scriptwriter_model = models_config["models"]["scriptwriter"]["name"]
        if scriptwriter_model != models_config.get("models", {}).get("cluster", {}).get(
            "name"
        ):
            batches.append(
                {
                    "name": "Script Refinement Batch",
                    "model": scriptwriter_model,
                    "steps": [
                        ("script_refinement", False),  # Optional final rewrite
                    ],
                }
            )

    # Skip to specific step if requested
    if from_step:
        # Find which batch contains the requested step
        target_batch_idx = None
        target_step_idx = None

        for batch_idx, batch in enumerate(batches):
            step_names = [s[0] for s in batch["steps"]]
            if from_step in step_names:
                target_batch_idx = batch_idx
                target_step_idx = step_names.index(from_step)
                break

        if target_batch_idx is not None:
            # Modify the target batch to start from the requested step
            batches[target_batch_idx]["steps"] = batches[target_batch_idx]["steps"][
                target_step_idx:
            ]
            # Remove all previous batches
            batches = batches[target_batch_idx:]
            log.info(f"Resuming from step: {from_step} in batch: {batches[0]['name']}")
        else:
            log.warning(f"Unknown step '{from_step}', starting from beginning")

    # Use provided slug or extract from the most recent script file for research steps
    if slug:
        log.info(f"Using provided slug: {slug}")
    else:
        import glob

        script_files = glob.glob(os.path.join(BASE, "scripts", "*.txt"))
        if script_files:
            # Use the most recent script file
            script_files.sort(reverse=True)
            latest_script = script_files[0]
            # Extract slug from filename using robust utility
            from bin.utils.slug import safe_slug_from_script

            slug = safe_slug_from_script(latest_script)
            log.info(f"Extracted slug '{slug}' from script: {latest_script}")
        else:
            log.warning("No script files found, research steps may fail")

    # Execute batches sequentially with explicit model lifecycle management
    for batch_idx, batch in enumerate(batches):
        log.info(
            f"=== EXECUTING BATCH {batch_idx + 1}/{len(batches)}: {batch['name']} ==="
        )
        log.info(f"Using model: {batch['model']}")

        # Execute all steps in this batch using the same model session
        batch_success = True
        for step_name, required in batch["steps"]:
            if step_name == "script_refinement":
                # Handle script refinement specially
                log.info("Running script refinement with scriptwriter model")
                # This would call the script refinement logic
                continue

            # Special handling for research_ground - pass script path and slug
            if step_name == "research_ground" and slug:
                # Find the most recent script file
                import glob

                script_files = glob.glob(os.path.join(BASE, "scripts", "*.txt"))
                if not script_files:
                    log.info("No script files found, skipping research_ground")
                    log_state(step_name, "SKIP", "no_script_files")
                    continue
                else:
                    # Use the most recent script file
                    script_files.sort(reverse=True)
                    latest_script = script_files[0]
                    log.info(f"Using script for research_ground: {latest_script}")

                    # Pass script path as first argument and slug as --slug
                    step_success = run_step_legacy(
                        step_name,
                        args=[latest_script, "--slug", slug],
                        required=required,
                        brief_env=brief_env,
                        brief_data=brief_data,
                        models_config=models_config,
                    )
                    if not step_success and required:
                        batch_success = False
                        log.error(f"Required step failed: {step_name}")
                        break
                    continue

            # Special handling for research_collect - pass slug parameter
            elif step_name == "research_collect" and slug:
                step_success = run_step_legacy(
                    step_name,
                    args=["--slug", slug],
                    required=required,
                    brief_env=brief_env,
                    brief_data=brief_data,
                    models_config=models_config,
                )
            # Special handling for llm_outline - pass slug parameter
            elif step_name == "llm_outline" and slug:
                step_success = run_step_legacy(
                    step_name,
                    args=["--slug", slug],
                    required=required,
                    brief_env=brief_env,
                    brief_data=brief_data,
                    models_config=models_config,
                )
            # Special handling for llm_script - pass slug parameter
            elif step_name == "llm_script" and slug:
                step_success = run_step_legacy(
                    step_name,
                    args=["--slug", slug],
                    required=required,
                    brief_env=brief_env,
                    brief_data=brief_data,
                    models_config=models_config,
                )
            # Special handling for fact_check - pass script path
            elif step_name == "fact_check" and slug:
                # Find the specific script file for this slug
                script_path = os.path.join(BASE, "scripts", f"{slug}.txt")
                if not os.path.exists(script_path):
                    log.info(f"Script file not found for slug {slug}, skipping fact_check")
                    log_state(step_name, "SKIP", f"no_script_file_for_{slug}")
                    continue
                else:
                    log.info(f"Using script for fact_check: {script_path}")

                    # Pass script path as first argument (fact_check doesn't need brief_data)
                    step_success = run_step_legacy(
                        step_name,
                        args=[script_path],
                        required=required,
                        brief_env=brief_env,
                        brief_data=None,  # fact_check doesn't use brief_data
                        models_config=models_config,
                    )
                    if not step_success and required:
                        batch_success = False
                        log.error(f"Required step failed: {step_name}")
                        break
                    continue
            else:
                step_success = run_step_legacy(
                    step_name,
                    required=required,
                    brief_env=brief_env,
                    brief_data=brief_data,
                    models_config=models_config,
                )
            if not step_success and required:
                batch_success = False
                log.error(f"Required step failed: {step_name}")
                break

        if not batch_success:
            success = False
            log.error(f"Batch {batch['name']} failed, aborting pipeline")
            break

        log.info(f"=== BATCH {batch['name']} COMPLETED ===")

        # Explicit model unloading happens automatically when the model_session context exits
        # This ensures memory is freed before the next batch starts

    # Phase 3: Asset pipeline routing (animatics vs legacy)
    if success:
        # Load pipeline configuration for storyboard pipeline
        pipeline_cfg = load_pipeline_config()

        # Check pipeline mode configuration
        animatics_only = cfg.video.animatics_only
        enable_legacy = cfg.video.enable_legacy_stock

        if animatics_only and not enable_legacy:
            log.info("=== EXECUTING ANIMATICS-ONLY PIPELINE ===")
            log.info("Pipeline mode: animatics_only=true, enable_legacy_stock=false")

            # Get storyboard pipeline steps from configuration
            # Convert Pydantic model to dict for compatibility
            pipeline_dict = pipeline_cfg.model_dump() if hasattr(pipeline_cfg, 'model_dump') else pipeline_cfg.__dict__
            storyboard_steps = (
                pipeline_dict.get("execution", {})
                .get("storyboard_pipeline", {})
                .get("animatics_only", ["storyboard_plan", "animatics_generate"])
            )

            # Use the provided slug for storyboard planning
            if not slug:
                log.error("No slug provided for storyboard planning")
                success = False
            else:
                log.info(f"Using provided slug for storyboard planning: {slug}")

                # Execute storyboard pipeline steps
                for step_name in storyboard_steps:
                    if step_name == "storyboard_plan":
                        step_success = run_step_legacy(
                            step_name,
                            args=["--slug", slug],
                            required=True,
                            brief_env=brief_env,
                            brief_data=None,  # storyboard_plan doesn't use brief_data
                            models_config=models_config,
                        )
                    elif step_name == "animatics_generate":
                        step_success = run_step_legacy(
                            step_name,
                            args=["--slug", slug],
                            required=True,
                            brief_env=brief_env,
                            brief_data=None,  # animatics_generate doesn't use brief_data
                            models_config=models_config,
                        )
                    else:
                        step_success = run_step_legacy(
                            step_name,
                            required=True,
                            brief_env=brief_env,
                            brief_data=brief_data,
                            models_config=models_config,
                        )

                    if not step_success:
                        log.error(f"Storyboard pipeline step failed: {step_name}")
                        success = False
                        break
                    else:
                        log.info(f"Storyboard pipeline step completed: {step_name}")

        else:
            log.info("=== EXECUTING LEGACY STOCK ASSET PIPELINE ===")
            log.info(
                f"Pipeline mode: animatics_only={animatics_only}, enable_legacy_stock={enable_legacy}"
            )

            # Get legacy storyboard pipeline steps from configuration (fetch_assets disabled)
            # Convert Pydantic model to dict for compatibility
            pipeline_dict = pipeline_cfg.model_dump() if hasattr(pipeline_cfg, 'model_dump') else pipeline_cfg.__dict__
            legacy_steps = (
                pipeline_dict.get("execution", {})
                .get("storyboard_pipeline", {})
                .get("legacy_stock", ["storyboard_plan"])
            )

            # Execute legacy pipeline steps
            for step_name in legacy_steps:
                if step_name == "storyboard_plan":
                    # Use the provided slug for storyboard planning
                    if not slug:
                        log.error("No slug provided for storyboard planning")
                        success = False
                        break
                    else:
                        log.info(f"Using provided slug for storyboard planning: {slug}")
                        step_success = run_step(
                            step_name,
                            required=True,
                            brief_env=brief_env,
                            brief_data=brief_data,
                            models_config=models_config,
                            args=["--slug", slug],
                        )
                else:
                    step_success = run_step(
                        step_name,
                        required=True,
                        brief_env=brief_env,
                        brief_data=brief_data,
                        models_config=models_config,
                    )

                if not step_success:
                    log.error(f"Legacy pipeline step failed: {step_name}")
                    success = False
                    break
                else:
                    log.info(f"Legacy pipeline step completed: {step_name}")

    # Log pipeline mode for state tracking
    pipeline_mode = (
        "animatics_only"
        if (cfg.video.animatics_only and not cfg.video.enable_legacy_stock)
        else "legacy_stock"
    )
    log_state("run_pipeline", "MODE", f"pipeline_mode={pipeline_mode}")

    log.info(f"=== SHARED INGESTION {'COMPLETED' if success else 'FAILED'} ===")
    return success


def main():
    parser = argparse.ArgumentParser(description="Unified Pipeline Orchestrator")
    parser.add_argument("--slug", help="Slug identifier (required for most steps)")
    parser.add_argument("--yt-only", action="store_true", help="Run YouTube lane only")
    parser.add_argument(
        "--profile",
        choices=["m2_8gb_optimized", "pi_8gb"],
        default=None,
        help="Platform profile overlay",
    )
    parser.add_argument("--from-step", help="Resume from specific step")
    parser.add_argument(
        "--dry-run", action="store_true", help="Force dry-run mode for all publishing"
    )
    parser.add_argument(
        "--brief", help="Path to a custom workstream brief file (YAML or MD)"
    )
    parser.add_argument(
        "--no-style-rewrite",
        action="store_true",
        help="Skip optional script refinement batch",
    )
    parser.add_argument(
        "--enable-viral",
        action="store_true",
        default=True,
        help="Enable viral lab steps (default: True)",
    )
    parser.add_argument(
        "--no-viral",
        action="store_false",
        dest="enable_viral",
        help="Disable viral lab steps",
    )
    parser.add_argument(
        "--enable-shorts",
        action="store_true",
        default=True,
        help="Enable shorts generation (default: True)",
    )
    parser.add_argument(
        "--no-shorts",
        action="store_false",
        dest="enable_shorts",
        help="Disable shorts generation",
    )
    parser.add_argument(
        "--enable-seo",
        action="store_true",
        default=True,
        help="Enable SEO packaging (default: True)",
    )
    parser.add_argument(
        "--no-seo",
        action="store_false",
        dest="enable_seo",
        help="Disable SEO packaging",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="Seed for deterministic runs (default: 1337)",
    )

    args = parser.parse_args()
    
    # Extract slug for error handling
    slug = args.slug or "untitled"
    
    # Optional minimal orchestrator trigger via env flag
    if os.getenv("GREENLIGHT_MINIMAL") == "1":
        return _run_minimal_orchestrator(sys.argv[1:])

    # Default to reuse mode for asset testing unless explicitly set
    env = load_env()
    if not env.get("TEST_ASSET_MODE"):
        os.environ["TEST_ASSET_MODE"] = "reuse"

    # Load configuration and check system health
    cfg = load_config()

    # Apply profile overlay if specified
    if args.profile:
        # Convert Pydantic model to dict, apply overlay, then convert back
        cfg_dict = cfg.model_dump()
        cfg_dict = load_with_profile(cfg_dict, args.profile)
        # Recreate the Pydantic model with merged config
        cfg = type(cfg)(**cfg_dict)
        log.info(f"Applied profile: {args.profile}")
    else:
        # Auto-detect recommended profile
        recommended = get_recommended_profile()
        if recommended != "default":
            log.info(f"Auto-detected platform, recommended profile: {recommended}")
            log.info(f"Use --profile {recommended} to apply platform optimizations")

    modules_cfg = load_modules_cfg()
    env = load_env()

    # Load models configuration
    models_config = None
    try:
        import yaml

        models_path = os.path.join(BASE, "conf", "models.yaml")
        if os.path.exists(models_path):
            with open(models_path, "r", encoding="utf-8") as f:
                models_config = yaml.safe_load(f)
            log.info("Loaded models configuration")
        else:
            log.warning("No models.yaml found, using default configuration")
    except Exception as e:
        log.warning(f"Failed to load models configuration: {e}")
        models_config = {}

    # Load pipeline configuration
    pipeline_cfg = load_pipeline_config()
    log.info("Loaded pipeline configuration")

    # Load brief if provided
    brief_data = None
    brief_env_vars = None
    if args.brief:
        brief_data = load_brief(args.brief)
        if not brief_data:
            log.error(f"Failed to load brief from {args.brief}. Aborting pipeline.")
            return 1
    else:
        # Attempt to load brief from default locations if not provided
        brief_data = load_brief()
        if not brief_data:
            log.warning("No brief file found, proceeding without brief data.")

    log.info("=== PIPELINE ORCHESTRATOR STARTING ===")

    # Log brief context if available
    if brief_data:
        brief_title = brief_data.get("title", "Untitled")
        brief_source = brief_data.get("_source", "unknown")
        log_state(
            "run_pipeline",
            "START",
            f"args={vars(args)};brief={brief_title};source={brief_source}",
        )
    else:
        log_state("run_pipeline", "START", f"args={vars(args)};brief=none")

    try:
        # Check system health before heavy work
        guard_system(cfg)

        overall_success = True

        # Inject brief data into environment for all steps
        if brief_data:
            brief_env_vars = inject_brief_environment(brief_data)
            os.environ.update(brief_env_vars)
            log.info(f"Injected {len(brief_env_vars)} brief environment variables.")

        # Shared ingestion gating based on --yt-only flag
        if _should_run_shared_ingestion(args):
            log.info("Running shared ingestion (yt-only is OFF).")
            if not run_shared_ingestion(
                cfg,
                args.from_step,
                brief_env_vars,
                brief_data,
                models_config,
                args.no_style_rewrite,
                args.slug,
            ):
                overall_success = False
                log.error("Shared ingestion failed, aborting pipeline")
                return 1
        else:
            log.info("Skipping shared ingestion (yt-only is ON).")

        # Run requested lanes
        if args.yt_only:
            if not run_youtube_lane(
                cfg, args, args.dry_run, brief_env_vars, brief_data, models_config
            ):
                overall_success = False

        else:
            # Run YouTube lane only
            yt_success = run_youtube_lane(
                cfg, args, args.dry_run, brief_env_vars, brief_data, models_config
            )

            if not yt_success:
                overall_success = False

        # Final status
        if overall_success:
            log_state("run_pipeline", "SUCCESS", "all_lanes_completed")
            log.info("=== PIPELINE ORCHESTRATOR COMPLETED SUCCESSFULLY ===")
            return 0
        else:
            log_state("run_pipeline", "PARTIAL", "some_lanes_failed")
            log.error("=== PIPELINE ORCHESTRATOR COMPLETED WITH FAILURES ===")
            return 1

    except KeyboardInterrupt:
        log_state("run_pipeline", "INTERRUPTED", "user_interrupt")
        log.info("Pipeline interrupted by user")
        return 130
    except Exception as e:
        log_state("run_pipeline", "ERROR", f"exception={str(e)}")
        log.error(f"Pipeline failed with exception: {e}")
        return 1


if __name__ == "__main__":
    with single_lock():
        sys.exit(main())
