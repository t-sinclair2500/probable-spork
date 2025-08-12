#!/usr/bin/env python3
import json
import os
import sys

from bin.core import get_logger, load_config, load_env

log = get_logger("check_env")


def main():
    cfg = load_config()
    env = load_env()
    issues = []

    # If assets providers enabled, require at least one API key
    if cfg.assets.providers:
        if not (
            env.get("PIXABAY_API_KEY")
            or env.get("PEXELS_API_KEY")
            or env.get("UNSPLASH_ACCESS_KEY")
        ):
            issues.append(
                "No asset provider API keys set (PIXABAY_API_KEY/PEXELS_API_KEY/UNSPLASH_ACCESS_KEY)."
            )

    # Check for required models configuration
    try:
        from bin.core import load_modules_cfg
        modules_cfg = load_modules_cfg()
        
        if not modules_cfg:
            issues.append("modules.yaml not found or empty")
        else:
            # Check procedural settings
            procedural = modules_cfg.get("procedural", {})
            if not procedural:
                issues.append("procedural settings missing in modules.yaml")
            else:
                # Check required procedural settings
                if "seed" not in procedural:
                    issues.append("procedural.seed not set in modules.yaml")
                if "placement" not in procedural:
                    issues.append("procedural.placement settings missing in modules.yaml")
                if "motion" not in procedural:
                    issues.append("procedural.motion settings missing in modules.yaml")
            
            # Check render settings
            render = modules_cfg.get("render", {})
            if not render:
                issues.append("render settings missing in modules.yaml")
            else:
                if "resolution" not in render:
                    issues.append("render.resolution not set in modules.yaml")
                if "fps" not in render:
                    issues.append("render.fps not set in modules.yaml")
        
    except Exception as e:
        issues.append(f"Failed to load modules configuration: {e}")

    # Check for required models
    try:
        import yaml
        models_path = os.path.join(os.path.dirname(__file__), "..", "conf", "models.yaml")
        if os.path.exists(models_path):
            with open(models_path, 'r', encoding='utf-8') as f:
                models_cfg = yaml.safe_load(f)
            
            # Check for required models
            required_models = ["cluster", "research", "outline", "scriptwriter"]
            for model_type in required_models:
                if model_type not in models_cfg.get("models", {}):
                    issues.append(f"Required model '{model_type}' missing in models.yaml")
            
            # Check voice configuration
            voice = models_cfg.get("voice", {})
            if not voice:
                issues.append("voice configuration missing in models.yaml")
            else:
                tts = voice.get("tts", {})
                if not tts:
                    issues.append("voice.tts configuration missing in models.yaml")
                else:
                    if tts.get("provider") != "piper":
                        issues.append("voice.tts.provider should be 'piper' for this pipeline")
                    if "voice_id" not in tts:
                        issues.append("voice.tts.voice_id not set in models.yaml")
        else:
            issues.append("models.yaml not found")
            
    except Exception as e:
        issues.append(f"Failed to load models configuration: {e}")

    # If blog lane used later, remind about WP app password
    from pathlib import Path

    blog_cfg = Path(os.path.join(os.path.dirname(__file__), "..", "conf", "blog.yaml"))
    if blog_cfg.exists():
        pass

    if issues:
        log.error(json.dumps({"issues": issues}))
        sys.exit(2)
    log.info("Environment/config checks passed.")


if __name__ == "__main__":
    main()
