#!/usr/bin/env python3
"""
Unified Pipeline Orchestrator for YouTube + Blog Content Generation

This script orchestrates the entire content pipeline in a single daily run,
replacing the fragmented cron jobs with lock-aware sequential execution.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from bin.core import (
    BASE,
    get_logger,
    get_publish_flags,
    guard_system, 
    load_config,
    load_env,
    log_state,
    single_lock
)

log = get_logger("run_pipeline")

# Blog publish checking now handled by centralized get_publish_flags() in bin.core

def run_step(script_name: str, args: List[str] = None, required: bool = True) -> bool:
    """
    Execute a pipeline step script and log results.
    
    Args:
        script_name: Name of script without .py extension (e.g., 'niche_trends')
        args: Additional arguments to pass to script
        required: If False, step failure won't abort pipeline
        
    Returns:
        True if step succeeded, False otherwise
    """
    script_path = os.path.join(BASE, "bin", f"{script_name}.py")
    if not os.path.exists(script_path):
        log.error(f"Script not found: {script_path}")
        if required:
            raise SystemExit(f"Required script missing: {script_name}")
        return False
        
    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)
        
    start_time = time.time()
    
    try:
        log.info(f"Starting step: {script_name}")
        result = subprocess.run(
            cmd,
            cwd=BASE,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout per step
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        if result.returncode == 0:
            log_state(script_name, "OK", f"elapsed_ms={elapsed_ms}")
            log.info(f"Step completed: {script_name} ({elapsed_ms}ms)")
            return True
        else:
            log_state(script_name, "FAIL", f"exit_code={result.returncode};elapsed_ms={elapsed_ms}")
            log.error(f"Step failed: {script_name} (exit {result.returncode})")
            log.error(f"STDERR: {result.stderr}")
            
            if required:
                raise SystemExit(f"Required step failed: {script_name}")
            return False
            
    except subprocess.TimeoutExpired:
        log_state(script_name, "TIMEOUT", f"timeout=3600s")
        log.error(f"Step timed out: {script_name}")
        if required:
            raise SystemExit(f"Required step timed out: {script_name}")
        return False
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        log_state(script_name, "ERROR", f"exception={str(e)};elapsed_ms={elapsed_ms}")
        log.error(f"Step error: {script_name} - {e}")
        if required:
            raise SystemExit(f"Required step error: {script_name} - {e}")
        return False

def run_youtube_lane(cfg, dry_run: bool = False) -> bool:
    """Execute YouTube content generation lane"""
    log.info("=== STARTING YOUTUBE LANE ===")
    
    success = True
    
    # Phase 4: YouTube lane (per spec)
    steps = [
        ("tts_generate", True),
        ("generate_captions", False),  # Optional - graceful skip if whisper.cpp missing
        ("assemble_video", True),
        ("make_thumbnail", True),
        ("upload_stage", True)
    ]
    
    for step_name, required in steps:
        step_success = run_step(step_name, required=required)
        if not step_success and required:
            success = False
            break
    
    log.info(f"=== YOUTUBE LANE {'COMPLETED' if success else 'FAILED'} ===")
    return success

def run_blog_lane(cfg, dry_run: bool = False) -> bool:
    """Execute blog content generation lane (staged only)"""
    log.info("=== STARTING BLOG LANE (STAGED) ===")
    
    # Use centralized flag governance  
    flags = get_publish_flags(cli_dry_run=dry_run, target="blog")
    publish_enabled = flags["blog_publish_enabled"]
    
    success = True
    
    # Phase 5: Blog lane (staged only per spec)
    steps = [
        ("blog_pick_topics", True),
        ("blog_generate_post", True), 
        ("blog_render_html", True)
    ]
    
    for step_name, required in steps:
        step_success = run_step(step_name, required=required)
        if not step_success and required:
            success = False
            break
    
    # Stage locally instead of publishing to WordPress
    if success:
        try:
            if not run_step("blog_stage_local", required=True):
                success = False
        except SystemExit:
            # blog_stage_local doesn't exist yet - skip gracefully
            log.warning("blog_stage_local.py not found, skipping local staging")
            log_state("blog_stage_local", "SKIP", "script_not_found")
    
    # Skip WordPress publishing when disabled
    if success and not publish_enabled:
        log.info("WordPress publishing disabled, skipping blog_post_wp.py")
        log_state("blog_post_wp", "SKIP", "publish_disabled")
    elif success and publish_enabled:
        log.info("WordPress publishing enabled, running blog_post_wp.py")
        success = run_step("blog_post_wp", required=True)
        
        if success:
            # Only ping search engines if we actually published
            run_step("blog_ping_search", required=False)
    
    log.info(f"=== BLOG LANE {'COMPLETED' if success else 'FAILED'} ===")
    return success

def run_shared_ingestion(cfg, from_step: Optional[str] = None) -> bool:
    """Execute shared data ingestion steps"""
    log.info("=== STARTING SHARED INGESTION ===")
    
    success = True
    
    # Phase 1 & 2: Shared ingestion (per spec)
    steps = [
        ("niche_trends", True),
        ("llm_cluster", True),
        ("llm_outline", True),
        ("llm_script", True),
        ("fact_check", False)  # Optional gate on high-risk content
    ]
    
    # Skip to specific step if requested
    if from_step:
        step_names = [s[0] for s in steps]
        if from_step in step_names:
            start_idx = step_names.index(from_step)
            steps = steps[start_idx:]
            log.info(f"Resuming from step: {from_step}")
        else:
            log.warning(f"Unknown step '{from_step}', starting from beginning")
    
    for step_name, required in steps:
        step_success = run_step(step_name, required=required)
        if not step_success and required:
            success = False
            break
    
    # Phase 3: Asset fetching
    if success:
        success = run_step("fetch_assets", required=True)
    
    log.info(f"=== SHARED INGESTION {'COMPLETED' if success else 'FAILED'} ===")
    return success

def main():
    parser = argparse.ArgumentParser(description="Unified Pipeline Orchestrator")
    parser.add_argument("--yt-only", action="store_true", help="Run YouTube lane only")
    parser.add_argument("--blog-only", action="store_true", help="Run blog lane only (staged)")
    parser.add_argument("--from-step", help="Resume from specific step")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode for all publishing")
    
    args = parser.parse_args()
    
    # Default to reuse mode for asset testing unless explicitly set
    env = load_env()
    if not env.get("TEST_ASSET_MODE"):
        import os
        os.environ["TEST_ASSET_MODE"] = "reuse"
    
    # Load configuration and check system health
    cfg = load_config()
    env = load_env()
    
    log.info("=== PIPELINE ORCHESTRATOR STARTING ===")
    log_state("run_pipeline", "START", f"args={vars(args)}")
    
    try:
        # Check system health before heavy work
        guard_system(cfg)
        
        overall_success = True
        
        # Shared ingestion (unless skipping with specific lane flags and from-step)
        if not (args.yt_only or args.blog_only) or not args.from_step:
            if not run_shared_ingestion(cfg, args.from_step):
                overall_success = False
                log.error("Shared ingestion failed, aborting pipeline")
                return 1
        
        # Run requested lanes
        if args.yt_only:
            if not run_youtube_lane(cfg, args.dry_run):
                overall_success = False
        elif args.blog_only:
            if not run_blog_lane(cfg, args.dry_run):
                overall_success = False
        else:
            # Run both lanes
            yt_success = run_youtube_lane(cfg, args.dry_run)
            blog_success = run_blog_lane(cfg, args.dry_run)
            
            if not (yt_success and blog_success):
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

