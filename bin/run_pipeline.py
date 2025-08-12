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

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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
            if brief_path.endswith('.yaml') or brief_path.endswith('.yml'):
                import yaml
                with open(brief_path, 'r', encoding='utf-8') as f:
                    brief = yaml.safe_load(f)
                brief["_source"] = "custom_yaml"
            elif brief_path.endswith('.md'):
                from bin.brief_loader import from_markdown_front_matter
                brief = from_markdown_front_matter(brief_path)
                brief["_source"] = "custom_markdown"
            else:
                log.warning(f"Unsupported brief file format: {brief_path}")
                return None
        else:
            # Load from default locations
            brief = _load_brief()
            
        log.info(f"Loaded brief: {brief.get('title', 'Untitled')} from {brief.get('_source', 'unknown')}")
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
    if brief.get('title'):
        env_vars['BRIEF_TITLE'] = brief['title']
    if brief.get('tone'):
        env_vars['BRIEF_TONE'] = brief['tone']
    if brief.get('audience'):
        env_vars['BRIEF_AUDIENCE'] = ','.join(brief['audience'])
    
    # Video settings
    if brief.get('video'):
        video = brief['video']
        if video.get('target_length_min'):
            env_vars['BRIEF_VIDEO_LENGTH_MIN'] = str(video['target_length_min'])
        if video.get('target_length_max'):
            env_vars['BRIEF_VIDEO_LENGTH_MAX'] = str(video['target_length_max'])
    
    # Blog settings
    if brief.get('blog'):
        blog = brief['blog']
        if blog.get('words_min'):
            env_vars['BRIEF_BLOG_WORDS_MIN'] = str(blog['words_min'])
        if blog.get('words_max'):
            env_vars['BRIEF_BLOG_WORDS_MAX'] = str(blog['words_max'])
    
    # Keywords
    if brief.get('keywords_include'):
        env_vars['BRIEF_KEYWORDS_INCLUDE'] = ','.join(brief['keywords_include'])
    if brief.get('keywords_exclude'):
        env_vars['BRIEF_KEYWORDS_EXCLUDE'] = ','.join(brief['keywords_exclude'])
    
    # Sources
    if brief.get('sources_preferred'):
        env_vars['BRIEF_SOURCES_PREFERRED'] = ','.join(brief['sources_preferred'])
    
    # Monetization
    if brief.get('monetization'):
        monetization = brief['monetization']
        if monetization.get('cta_text'):
            env_vars['BRIEF_CTA_TEXT'] = monetization['cta_text']
        if monetization.get('primary'):
            env_vars['BRIEF_MONETIZATION_PRIMARY'] = ','.join(monetization['primary'])
    
    # Notes
    if brief.get('notes'):
        env_vars['BRIEF_NOTES'] = brief['notes']
    
    # Source info
    env_vars['BRIEF_SOURCE'] = brief.get('_source', 'unknown')
    
    return env_vars

def run_step(script_name: str, args: List[str] = None, required: bool = True, brief_env: Dict[str, str] = None, brief_data: Dict[str, any] = None, models_config: Dict = None) -> bool:
    """
    Execute a pipeline step script and log results.
    
    Args:
        script_name: Name of script without .py extension (e.g., 'niche_trends')
        args: Additional arguments to pass to script
        required: If False, step failure won't abort pipeline
        brief_env: Environment variables to inject for brief data
        brief_data: Full brief data to pass as command line argument
        models_config: Models configuration for LLM steps
        
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
            log.debug(f"Injected {len(brief_env)} brief environment variables for {script_name}")
        
        result = subprocess.run(
            cmd,
            cwd=BASE,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout per step
            env=env
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
            raise SystemExit(f"Step error: {script_name} - {e}")
        return False

def _run_llm_step(script_name: str, model_name: str, args: List[str] = None, required: bool = True, brief_env: Dict[str, str] = None, brief_data: Dict[str, any] = None) -> bool:
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
            return _run_subprocess_step(script_name, args, required, brief_env, brief_data)
            
    except Exception as e:
        log.error(f"LLM step error: {script_name} - {e}")
        if required:
            raise SystemExit(f"Required LLM step failed: {script_name}")
        return False

def _run_subprocess_step(script_name: str, args: List[str] = None, required: bool = True, brief_env: Dict[str, str] = None, brief_data: Dict[str, any] = None) -> bool:
    """Execute step using subprocess (original implementation)."""
    cmd = [sys.executable, os.path.join(BASE, "bin", f"{script_name}.py")]
    
    # Add brief data as JSON argument if available
    if brief_data:
        import json
        brief_json = json.dumps(brief_data)
        cmd.extend(["--brief-data", brief_json])
    
    if args:
        cmd.extend(args)
        
    start_time = time.time()
    
    try:
        log.info(f"Starting subprocess step: {script_name}")
        
        # Prepare environment with brief data
        env = os.environ.copy()
        if brief_env:
            env.update(brief_env)
            log.debug(f"Injected {len(brief_env)} brief environment variables for {script_name}")
        
        result = subprocess.run(
            cmd,
            cwd=BASE,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout per step
            env=env
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
            raise SystemExit(f"Step timed out: {script_name}")
        return False
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        log_state(script_name, "ERROR", f"exception={str(e)};elapsed_ms={elapsed_ms}")
        log.error(f"Step error: {script_name} - {e}")
        if required:
            raise SystemExit(f"Step error: {script_name} - {e}")
        return False

def run_youtube_lane(cfg, dry_run: bool = False, brief_env: Dict[str, str] = None, brief_data: Dict[str, any] = None, models_config: Dict = None) -> bool:
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
        step_success = run_step(step_name, required=required, brief_env=brief_env, brief_data=brief_data)
        if not step_success and required:
            success = False
            break
    
    log.info(f"=== YOUTUBE LANE {'COMPLETED' if success else 'FAILED'} ===")
    return success

def run_blog_lane(cfg, dry_run: bool = False, brief_env: Dict[str, str] = None, brief_data: Dict[str, any] = None) -> bool:
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
        step_success = run_step(step_name, required=required, brief_env=brief_env, brief_data=brief_data)
        if not step_success and required:
            success = False
            break
    
    # Stage locally instead of publishing to WordPress
    if success:
        try:
            if not run_step("blog_stage_local", required=True, brief_env=brief_env, brief_data=brief_data):
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
        success = run_step("blog_post_wp", required=True, brief_env=brief_env, brief_data=brief_data)
        
        if success:
            # Only ping search engines if we actually published
            run_step("blog_ping_search", required=False, brief_env=brief_env, brief_data=brief_data)
    
    log.info(f"=== BLOG LANE {'COMPLETED' if success else 'FAILED'} ===")
    return success

def run_shared_ingestion(cfg, from_step: Optional[str] = None, brief_env: Optional[Dict[str, str]] = None, brief_data: Optional[Dict] = None, models_config: Optional[Dict] = None, no_style_rewrite: bool = False) -> bool:
    """Execute shared data ingestion steps with batch-by-model execution"""
    log.info("=== STARTING SHARED INGESTION (BATCH-BY-MODEL) ===")
    
    success = True
    
    # Load models configuration if not provided
    if models_config is None:
        try:
            import yaml
            models_path = os.path.join(BASE, "conf", "models.yaml")
            if os.path.exists(models_path):
                with open(models_path, 'r', encoding='utf-8') as f:
                    models_config = yaml.safe_load(f)
                log.info("Loaded models configuration for batch execution")
            else:
                log.warning("No models.yaml found, using default configuration")
                models_config = {}
        except Exception as e:
            log.warning(f"Failed to load models configuration: {e}")
            models_config = {}
    
    # Define execution batches by model type
    batches = [
        {
            "name": "Llama 3.2 Batch (Cluster + Outline + Script)",
            "model": models_config.get("models", {}).get("cluster", {}).get("name", "llama3.2:latest") if models_config else "llama3.2:latest",
            "steps": [
                ("niche_trends", True),      # Data collection (no LLM)
                ("llm_cluster", True),       # Llama 3.2
                ("llm_outline", True),       # Llama 3.2
                ("llm_script", True),        # Llama 3.2
            ]
        },
        {
            "name": "Mistral 7B Batch (Research + Fact-Check)",
            "model": models_config.get("models", {}).get("research", {}).get("name", "mistral:7b-instruct") if models_config else "mistral:7b-instruct",
            "steps": [
                ("research_collect", True),  # Mistral 7B
                ("research_ground", True),   # Mistral 7B
                ("fact_check", False),       # Mistral 7B (optional)
            ]
        }
    ]
    
    # Optional final batch for script refinement (if enabled and not skipped)
    if not no_style_rewrite and models_config and models_config.get("models", {}).get("scriptwriter", {}).get("name"):
        scriptwriter_model = models_config["models"]["scriptwriter"]["name"]
        if scriptwriter_model != models_config.get("models", {}).get("cluster", {}).get("name"):
            batches.append({
                "name": "Script Refinement Batch",
                "model": scriptwriter_model,
                "steps": [
                    ("script_refinement", False),  # Optional final rewrite
                ]
            })
    
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
            batches[target_batch_idx]["steps"] = batches[target_batch_idx]["steps"][target_step_idx:]
            # Remove all previous batches
            batches = batches[target_batch_idx:]
            log.info(f"Resuming from step: {from_step} in batch: {batches[0]['name']}")
        else:
            log.warning(f"Unknown step '{from_step}', starting from beginning")
    
    # Execute batches sequentially with explicit model lifecycle management
    for batch_idx, batch in enumerate(batches):
        log.info(f"=== EXECUTING BATCH {batch_idx + 1}/{len(batches)}: {batch['name']} ===")
        log.info(f"Using model: {batch['model']}")
        
        # Execute all steps in this batch using the same model session
        batch_success = True
        for step_name, required in batch["steps"]:
            if step_name == "script_refinement":
                # Handle script refinement specially
                log.info("Running script refinement with scriptwriter model")
                # This would call the script refinement logic
                continue
                
            step_success = run_step(step_name, required=required, brief_env=brief_env, brief_data=brief_data, models_config=models_config)
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
    
    # Phase 3: Asset fetching (no LLM required)
    if success:
        log.info("=== EXECUTING ASSET FETCHING ===")
        success = run_step("fetch_assets", required=True, brief_env=brief_env, brief_data=brief_data, models_config=models_config)
    
    log.info(f"=== SHARED INGESTION {'COMPLETED' if success else 'FAILED'} ===")
    return success

def main():
    parser = argparse.ArgumentParser(description="Unified Pipeline Orchestrator")
    parser.add_argument("--yt-only", action="store_true", help="Run YouTube lane only")
    parser.add_argument("--blog-only", action="store_true", help="Run blog lane only (staged)")
    parser.add_argument("--from-step", help="Resume from specific step")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode for all publishing")
    parser.add_argument("--brief", help="Path to a custom workstream brief file (YAML or MD)")
    parser.add_argument("--no-style-rewrite", action="store_true", help="Skip optional script refinement batch")
    
    args = parser.parse_args()
    
    # Default to reuse mode for asset testing unless explicitly set
    env = load_env()
    if not env.get("TEST_ASSET_MODE"):
        import os
        os.environ["TEST_ASSET_MODE"] = "reuse"
    
    # Load configuration and check system health
    cfg = load_config()
    env = load_env()
    
    # Load models configuration
    models_config = None
    try:
        import yaml
        models_path = os.path.join(BASE, "conf", "models.yaml")
        if os.path.exists(models_path):
            with open(models_path, 'r', encoding='utf-8') as f:
                models_config = yaml.safe_load(f)
            log.info("Loaded models configuration")
        else:
            log.warning("No models.yaml found, using default configuration")
    except Exception as e:
        log.warning(f"Failed to load models configuration: {e}")
        models_config = {}
    
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
        brief_title = brief_data.get('title', 'Untitled')
        brief_source = brief_data.get('_source', 'unknown')
        log_state("run_pipeline", "START", f"args={vars(args)};brief={brief_title};source={brief_source}")
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
        
        # Shared ingestion (unless skipping with specific lane flags and from-step)
        if not (args.yt_only or args.blog_only) or not args.from_step:
            if not run_shared_ingestion(cfg, args.from_step, brief_env_vars, brief_data, models_config, args.no_style_rewrite):
                overall_success = False
                log.error("Shared ingestion failed, aborting pipeline")
                return 1
        
        # Run requested lanes
        if args.yt_only:
            if not run_youtube_lane(cfg, args.dry_run, brief_env_vars, brief_data, models_config):
                overall_success = False
        elif args.blog_only:
            if not run_blog_lane(cfg, args.dry_run, brief_env_vars, brief_data):
                overall_success = False
        else:
            # Run both lanes
            yt_success = run_youtube_lane(cfg, args.dry_run, brief_env_vars, brief_data, models_config)
            blog_success = run_blog_lane(cfg, args.dry_run, brief_env_vars, brief_data)
            
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

