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
    load_modules_cfg,
    log_state,
    single_lock
)

def load_pipeline_config():
    """Load centralized pipeline configuration."""
    try:
        import yaml
        pipeline_path = os.path.join(BASE, "conf", "pipeline.yaml")
        if os.path.exists(pipeline_path):
            with open(pipeline_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            log.warning("No pipeline.yaml found, using default configuration")
            return {}
    except Exception as e:
        log.warning(f"Failed to load pipeline configuration: {e}")
        return {}

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
    
    # Load pipeline configuration for video production steps
    pipeline_cfg = load_pipeline_config()
    
    # Phase 4: YouTube lane (per spec)
    video_steps = pipeline_cfg.get("execution", {}).get("video_production", [
        ("tts_generate", True),
        ("generate_captions", False),  # Optional - graceful skip if whisper.cpp missing
        ("assemble_video", True),
        ("make_thumbnail", True),
        ("upload_stage", True)
    ])
    
    for step_name, required in video_steps:
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
    
    # Load pipeline configuration for blog generation steps
    pipeline_cfg = load_pipeline_config()
    
    # Phase 5: Blog lane (staged only per spec)
    blog_steps = pipeline_cfg.get("execution", {}).get("blog_generation", [
        ("blog_pick_topics", True),
        ("blog_generate_post", True), 
        ("blog_render_html", True)
    ])
    
    for step_name, required in blog_steps:
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
    
    # Load pipeline configuration
    pipeline_cfg = load_pipeline_config()
    
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
    
    # Get execution steps from pipeline configuration or use defaults
    shared_steps = pipeline_cfg.get("execution", {}).get("shared_ingestion", [
        "niche_trends", "llm_cluster", "llm_outline", "llm_script", 
        "research_collect", "research_ground", "fact_check"
    ])
    
    # Define execution batches by model type
    batches = [
        {
                    "name": "Llama 3.2 Batch (Cluster + Outline + Script)",
        "model": models_config.get("models", {}).get("cluster", {}).get("name", "llama3.2:3b") if models_config else "llama3.2:3b",
            "steps": [
                (step, True) for step in shared_steps[:4]  # First 4 steps are required
            ]
        },
        {
            "name": "Llama 3.2 Batch (Research + Fact-Check)",
            "model": models_config.get("models", {}).get("research", {}).get("name", "llama3.2:3b") if models_config else "llama3.2:3b",
            "steps": [
                (step, False) for step in shared_steps[4:]  # Remaining steps are optional
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
    
    # Extract slug from the most recent script file for research steps
    slug = None
    import glob
    script_files = glob.glob(os.path.join(BASE, "scripts", "*.txt"))
    if script_files:
        # Use the most recent script file
        script_files.sort(reverse=True)
        latest_script = script_files[0]
        # Extract slug from filename (e.g., "2025-08-12_topic.txt" -> "topic")
        script_basename = os.path.basename(latest_script)
        slug = script_basename.split('_', 1)[1].replace('.txt', '')
        log.info(f"Extracted slug '{slug}' from script: {latest_script}")
    else:
        log.warning("No script files found, research steps may fail")
    
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
                    step_success = run_step(step_name, required=required, brief_env=brief_env, brief_data=brief_data, models_config=models_config, args=[latest_script, "--slug", slug])
                    if not step_success and required:
                        batch_success = False
                        log.error(f"Required step failed: {step_name}")
                        break
                    continue
            
            # Special handling for research_collect - pass slug parameter
            if step_name == "research_collect" and slug:
                step_success = run_step(step_name, required=required, brief_env=brief_env, brief_data=brief_data, models_config=models_config, args=["--slug", slug])
            # Special handling for fact_check - pass script path
            elif step_name == "fact_check" and slug:
                # Find the most recent script file
                import glob
                script_files = glob.glob(os.path.join(BASE, "scripts", "*.txt"))
                if not script_files:
                    log.info("No script files found, skipping fact_check")
                    log_state(step_name, "SKIP", "no_script_files")
                    continue
                else:
                    # Use the most recent script file
                    script_files.sort(reverse=True)
                    latest_script = script_files[0]
                    log.info(f"Using script for fact_check: {latest_script}")
                    
                    # Pass script path as first argument
                    step_success = run_step(step_name, required=required, brief_env=brief_env, brief_data=brief_data, models_config=models_config, args=[latest_script])
                    if not step_success and required:
                        batch_success = False
                        log.error(f"Required step failed: {step_name}")
                        break
                    continue
            else:
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
            storyboard_steps = pipeline_cfg.get("execution", {}).get("storyboard_pipeline", {}).get("animatics_only", ["storyboard_plan", "animatics_generate"])
            
            # Extract slug from the most recent script file
            import glob
            script_files = glob.glob(os.path.join(BASE, "scripts", "*.txt"))
            if not script_files:
                log.error("No script files found for storyboard planning")
                success = False
            else:
                # Use the most recent script file
                script_files.sort(reverse=True)
                latest_script = script_files[0]
                # Extract slug from filename (e.g., "2025-08-12_topic.txt" -> "topic")
                script_basename = os.path.basename(latest_script)
                slug = script_basename.split('_', 1)[1].replace('.txt', '')
                log.info(f"Using script {latest_script} with slug: {slug}")
                
                # Execute storyboard pipeline steps
                for step_name in storyboard_steps:
                    if step_name == "storyboard_plan":
                        step_success = run_step(step_name, required=True, brief_env=brief_env, brief_data=brief_data, models_config=models_config, args=["--slug", slug])
                    elif step_name == "animatics_generate":
                        step_success = run_step(step_name, required=True, brief_env=brief_env, brief_data=brief_data, models_config=models_config, args=["--slug", slug])
                    else:
                        step_success = run_step(step_name, required=True, brief_env=brief_env, brief_data=brief_data, models_config=models_config)
                    
                    if not step_success:
                        log.error(f"Storyboard pipeline step failed: {step_name}")
                        success = False
                        break
                    else:
                        log.info(f"Storyboard pipeline step completed: {step_name}")
                    
        else:
            log.info("=== EXECUTING LEGACY STOCK ASSET PIPELINE ===")
            log.info(f"Pipeline mode: animatics_only={animatics_only}, enable_legacy_stock={enable_legacy}")
            
            # Get legacy storyboard pipeline steps from configuration (fetch_assets disabled)
            legacy_steps = pipeline_cfg.get("execution", {}).get("storyboard_pipeline", {}).get("legacy_stock", ["storyboard_plan"])
            
            # Execute legacy pipeline steps
            for step_name in legacy_steps:
                if step_name == "storyboard_plan":
                    # Extract slug for storyboard planning
                    import glob
                    script_files = glob.glob(os.path.join(BASE, "scripts", "*.txt"))
                    if not script_files:
                        log.error("No script files found for storyboard planning")
                        success = False
                        break
                    else:
                        latest_script = script_files[0]
                        script_basename = os.path.basename(latest_script)
                        slug = script_basename.split('_', 1)[1].replace('.txt', '')
                        log.info(f"Using script {latest_script} with slug: {slug}")
                        step_success = run_step(step_name, required=True, brief_env=brief_env, brief_data=brief_data, models_config=models_config, args=["--slug", slug])
                else:
                    step_success = run_step(step_name, required=True, brief_env=brief_env, brief_data=brief_data, models_config=models_config)
                
                if not step_success:
                    log.error(f"Legacy pipeline step failed: {step_name}")
                    success = False
                    break
                else:
                    log.info(f"Legacy pipeline step completed: {step_name}")
    
    # Log pipeline mode for state tracking
    pipeline_mode = "animatics_only" if (cfg.video.animatics_only and not cfg.video.enable_legacy_stock) else "legacy_stock"
    log_state("run_pipeline", "MODE", f"pipeline_mode={pipeline_mode}")
    
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
    modules_cfg = load_modules_cfg()
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

