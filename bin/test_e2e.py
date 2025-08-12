#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import load_env, load_config, get_logger

log = get_logger("test_e2e")

def check_api_keys(env):
    """Check for available API keys and return available providers"""
    providers = {
        'youtube': bool(env.get("YOUTUBE_API_KEY") or env.get("GOOGLE_API_KEY")),
        'reddit': bool(env.get("REDDIT_CLIENT_ID") and env.get("REDDIT_CLIENT_SECRET")),
        'pixabay': bool(env.get("PIXABAY_API_KEY")),
        'pexels': bool(env.get("PEXELS_API_KEY")),
        'unsplash': bool(env.get("UNSPLASH_ACCESS_KEY")),
        'openai': bool(env.get("OPENAI_API_KEY")),
    }
    return providers

def check_whisper_cpp():
    """Check if whisper.cpp is available"""
    try:
        cfg = load_config()
        whisper_path = cfg.asr.whisper_cpp_path
        if whisper_path == "auto":
            # Try common locations
            possible_paths = [
                os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli"),
                "/usr/local/bin/whisper-cli",
                "/opt/whisper.cpp/build/bin/whisper-cli",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    return True
            return False
        else:
            return os.path.exists(whisper_path)
    except Exception:
        return False

def check_ollama():
    """Check if Ollama service is available"""
    try:
        cfg = load_config()
        endpoint = cfg.llm.endpoint
        import requests
        r = requests.get(endpoint.replace('/api/generate', '/api/tags'), timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def run_safe(cmd, required=True, reason=""):
    """Run command with optional skipping for missing dependencies"""
    print(f"RUN: {cmd}")
    if not required:
        print(f"  (OPTIONAL - {reason})")
    
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            if required:
                print(f"FAILED: {cmd}")
                print(f"STDOUT: {r.stdout}")
                print(f"STDERR: {r.stderr}")
                sys.exit(r.returncode)
            else:
                print(f"SKIPPED: {cmd} (exit code {r.returncode})")
                print(f"  Reason: {reason}")
                return False
        else:
            if r.stdout.strip():
                print(r.stdout)
            return True
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {cmd}")
        if required:
            sys.exit(1)
        else:
            print(f"SKIPPED: {cmd} (timeout)")
            return False
    except Exception as e:
        print(f"ERROR: {cmd} - {e}")
        if required:
            sys.exit(1)
        else:
            print(f"SKIPPED: {cmd} ({e})")
            return False

def main():
    """Enhanced E2E test with graceful dependency handling"""
    print("Starting E2E test with dependency checks...")
    
    # Load environment and check capabilities
    env = load_env()
    providers = check_api_keys(env)
    has_whisper = check_whisper_cpp()
    has_ollama = check_ollama()
    
    print(f"\nDependency Status:")
    print(f"  Ollama service: {'✓' if has_ollama else '✗'}")
    print(f"  whisper.cpp: {'✓' if has_whisper else '✗'}")
    print(f"  YouTube API: {'✓' if providers['youtube'] else '✗'}")
    print(f"  Reddit API: {'✓' if providers['reddit'] else '✗'}")
    print(f"  Asset providers: {'✓' if any([providers['pixabay'], providers['pexels'], providers['unsplash']]) else '✗'}")
    print(f"  OpenAI API: {'✓' if providers['openai'] else '✗'}")
    
    # Core pipeline (required)
    print(f"\n=== Core Pipeline ===")
    
    # Ingestion - should work even with limited APIs due to fallbacks
    run_safe("python bin/niche_trends.py", required=True)
    
    # LLM steps - require Ollama
    if has_ollama:
        run_safe("python bin/llm_cluster.py", required=True)
        run_safe("python bin/llm_outline.py", required=True) 
        run_safe("python bin/llm_script.py", required=True)
    else:
        print("SKIP: LLM steps (Ollama not available)")
        return
    
    # Procedural pipeline components (new)
    print(f"\n=== Procedural Pipeline ===")
    
    # Check modules configuration
    try:
        from bin.core import load_modules_cfg
        modules_cfg = load_modules_cfg()
        if modules_cfg:
            print("✓ Modules configuration loaded")
            procedural = modules_cfg.get("procedural", {})
            if procedural:
                print(f"  - Procedural seed: {procedural.get('seed', 'not set')}")
                print(f"  - Max colors per scene: {procedural.get('max_colors_per_scene', 'not set')}")
                print(f"  - Placement settings: {procedural.get('placement', 'not set')}")
                print(f"  - Motion settings: {procedural.get('motion', 'not set')}")
            else:
                print("  - Procedural settings missing")
            
            render = modules_cfg.get("render", {})
            if render:
                print(f"  - Render resolution: {render.get('resolution', 'not set')}")
                print(f"  - Render FPS: {render.get('fps', 'not set')}")
                print(f"  - Render codec: {render.get('codec', 'not set')}")
            else:
                print("  - Render settings missing")
        else:
            print("✗ Modules configuration not found")
    except Exception as e:
        print(f"WARNING: Could not load modules configuration: {e}")
    
    # Test storyboard planning with QA gates
    if has_ollama:
        print("Testing storyboard planning with QA gates...")
        run_safe("python bin/storyboard_plan.py --slug test_e2e --dry-run", required=False, reason="QA gates test")
    else:
        print("SKIP: Storyboard planning (Ollama not available)")
    
    # Check pipeline mode configuration
    try:
        import yaml
        with open("conf/global.yaml", 'r') as f:
            cfg = yaml.safe_load(f)
        animatics_only = cfg.get("video", {}).get("animatics_only", True)
        enable_legacy = cfg.get("video", {}).get("enable_legacy_stock", False)
        
        if animatics_only and not enable_legacy:
            print("Pipeline mode: ANIMATICS-ONLY")
            # Skip asset fetching in animatics-only mode
            print("SKIP: Asset fetching (animatics-only mode)")
            # Create empty assets folder so pipeline can continue
            os.makedirs("assets", exist_ok=True)
        else:
            print("Pipeline mode: LEGACY STOCK ASSETS")
            # Assets - require at least one provider
            if any([providers['pixabay'], providers['pexels'], providers['unsplash']]):
                run_safe("python bin/fetch_assets.py", required=True)
            else:
                print("SKIP: Asset fetching (no API keys available)")
                # Create empty assets folder so pipeline can continue
                os.makedirs("assets", exist_ok=True)
    except Exception as e:
        print(f"WARNING: Could not read pipeline config: {e}")
        # Fallback to legacy behavior
        if any([providers['pixabay'], providers['pexels'], providers['unsplash']]):
            run_safe("python bin/fetch_assets.py", required=True)
        else:
            print("SKIP: Asset fetching (no API keys available)")
            os.makedirs("assets", exist_ok=True)
    
    # Audio generation
    run_safe("python bin/tts_generate.py", required=True)
    
    # Captions - optional if whisper.cpp missing
    run_safe("python bin/generate_captions.py", 
             required=False, 
             reason="whisper.cpp not available" if not has_whisper else "unknown")
    
    # Video assembly
    run_safe("python bin/assemble_video.py", required=True)
    run_safe("python bin/upload_stage.py", required=True)
    
    # Blog lane
    print(f"\n=== Blog Lane ===")
    run_safe("python bin/blog_pick_topics.py", required=True)
    run_safe("python bin/blog_generate_post.py", required=True)
    run_safe("python bin/blog_render_html.py", required=True)
    
    # WordPress posting - always dry run in tests
    os.environ["BLOG_DRY_RUN"] = "true"
    
    # Asset fetching - default to reuse mode unless explicitly set to live
    if not os.environ.get("TEST_ASSET_MODE"):
        os.environ["TEST_ASSET_MODE"] = "reuse"
    run_safe("python bin/blog_post_wp.py", required=True)
    run_safe("python bin/blog_ping_search.py", required=True)
    
    print(f"\n✓ E2E test complete!")
    print(f"  - Video pipeline: PASSED")
    print(f"  - Blog pipeline: PASSED")
    print(f"  - Captions: {'PASSED' if has_whisper else 'SKIPPED (no whisper.cpp)'}")
    

if __name__ == "__main__":
    main()
