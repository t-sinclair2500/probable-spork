#!/usr/bin/env python3
import os
import subprocess
import sys

from bin.core import get_logger, load_config, load_env

log = get_logger("check_env")


def check_ffmpeg_installation():
    """Check FFmpeg and FFprobe installation and versions"""
    issues = []
    ffmpeg_info = {}

    # Check ffmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # Extract version from first line
            version_line = result.stdout.split("\n")[0]
            version = (
                version_line.split(" ")[2]
                if len(version_line.split(" ")) > 2
                else "unknown"
            )
            ffmpeg_info["ffmpeg"] = {
                "available": True,
                "version": version,
                "path": "ffmpeg",
            }
            log.info(f"FFmpeg found: {version}")
        else:
            issues.append("FFmpeg failed version check")
            ffmpeg_info["ffmpeg"] = {
                "available": False,
                "error": "version_check_failed",
            }
    except FileNotFoundError:
        issues.append("FFmpeg not found in PATH")
        ffmpeg_info["ffmpeg"] = {"available": False, "error": "not_found"}
    except subprocess.TimeoutExpired:
        issues.append("FFmpeg version check timed out")
        ffmpeg_info["ffmpeg"] = {"available": False, "error": "timeout"}
    except Exception as e:
        issues.append(f"FFmpeg validation error: {e}")
        ffmpeg_info["ffmpeg"] = {"available": False, "error": str(e)}

    # Check ffprobe
    try:
        result = subprocess.run(
            ["ffprobe", "-version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # Extract version from first line
            version_line = result.stdout.split("\n")[0]
            version = (
                version_line.split(" ")[2]
                if len(version_line.split(" ")) > 2
                else "unknown"
            )
            ffmpeg_info["ffprobe"] = {
                "available": True,
                "version": version,
                "path": "ffprobe",
            }
            log.info(f"FFprobe found: {version}")
        else:
            issues.append("FFprobe failed version check")
            ffmpeg_info["ffprobe"] = {
                "available": False,
                "error": "version_check_failed",
            }
    except FileNotFoundError:
        issues.append("FFprobe not found in PATH")
        ffmpeg_info["ffprobe"] = {"available": False, "error": "not_found"}
    except subprocess.TimeoutExpired:
        issues.append("FFprobe version check timed out")
        ffmpeg_info["ffprobe"] = {"available": False, "error": "timeout"}
    except Exception as e:
        issues.append(f"FFprobe validation error: {e}")
        ffmpeg_info["ffprobe"] = {"available": False, "error": str(e)}

    # Check if both are available
    if ffmpeg_info.get("ffmpeg", {}).get("available") and ffmpeg_info.get(
        "ffprobe", {}
    ).get("available"):
        log.info("FFmpeg and FFprobe are both available and working")
    else:
        issues.append(
            "FFmpeg/FFprobe installation incomplete - audio validation will fail"
        )

    return issues, ffmpeg_info


def main():
    cfg = load_config()
    env = load_env()
    issues = []

    # Check FFmpeg/FFprobe installation
    log.info("=== Checking FFmpeg/FFprobe Installation ===")
    ffmpeg_issues, ffmpeg_info = check_ffmpeg_installation()
    issues.extend(ffmpeg_issues)

    # Check asset configuration - procedural generation is preferred
    # Procedural generation mode - no external API keys needed
    log.info(
        "Asset pipeline configured for procedural generation - no external API keys required"
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
                    issues.append(
                        "procedural.placement settings missing in modules.yaml"
                    )
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

        models_path = os.path.join(
            os.path.dirname(__file__), "..", "conf", "models.yaml"
        )
        if os.path.exists(models_path):
            with open(models_path, "r", encoding="utf-8") as f:
                models_cfg = yaml.safe_load(f)

            # Check for required models
            required_models = ["cluster", "research", "outline", "scriptwriter"]
            for model_type in required_models:
                if model_type not in models_cfg.get("models", {}):
                    issues.append(
                        f"Required model '{model_type}' missing in models.yaml"
                    )

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
                        issues.append(
                            "voice.tts.provider should be 'piper' for this pipeline"
                        )
                    if "voice_id" not in tts:
                        issues.append("voice.tts.voice_id not set in models.yaml")
        else:
            issues.append("models.yaml not found")

    except Exception as e:
        issues.append(f"Failed to load models configuration: {e}")

    # Check render.yaml configuration
    try:
        render_path = os.path.join(
            os.path.dirname(__file__), "..", "conf", "render.yaml"
        )
        if os.path.exists(render_path):
            with open(render_path, "r", encoding="utf-8") as f:
                render_cfg = yaml.safe_load(f)

            # Check acceptance settings
            acceptance = render_cfg.get("acceptance", {})
            if not acceptance:
                issues.append("acceptance settings missing in render.yaml")
            else:
                # Check required acceptance settings
                if "tolerance_pct" not in acceptance:
                    issues.append("acceptance.tolerance_pct not set in render.yaml")
                if "audio_validation_required" not in acceptance:
                    issues.append(
                        "acceptance.audio_validation_required not set in render.yaml"
                    )
                if "caption_validation_required" not in acceptance:
                    issues.append(
                        "acceptance.caption_validation_required not set in render.yaml"
                    )
                if "legibility_validation_required" not in acceptance:
                    issues.append(
                        "acceptance.legibility_validation_required not set in render.yaml"
                    )

            # Check audio settings
            audio = render_cfg.get("audio", {})
            if not audio:
                issues.append("audio settings missing in render.yaml")
            else:
                if "vo_lufs_target" not in audio:
                    issues.append("audio.vo_lufs_target not set in render.yaml")
                if "music_lufs_target" not in audio:
                    issues.append("audio.music_lufs_target not set in render.yaml")
                if "true_peak_max" not in audio:
                    issues.append("audio.true_peak_max not set in render.yaml")

            # Check caption settings
            captions = render_cfg.get("captions", {})
            if not captions:
                issues.append("caption settings missing in render.yaml")
            else:
                if "require" not in captions:
                    issues.append("captions.require not set in render.yaml")
                if "fallback_generation" not in captions:
                    issues.append("captions.fallback_generation not set in render.yaml")
        else:
            issues.append(
                "render.yaml not found - audio validation and acceptance pipeline may fail"
            )

    except Exception as e:
        issues.append(f"Failed to load render configuration: {e}")

    # Print results
    print("=== Environment Check Results ===")

    if issues:
        print(f"\n❌ Found {len(issues)} issues:")
        for issue in issues:
            print(f"  • {issue}")

        print("\n=== Remediation Steps ===")

        # FFmpeg remediation
        if any("FFmpeg" in issue or "FFprobe" in issue for issue in issues):
            print("\n🔧 FFmpeg/FFprobe Installation:")
            print("  1. Install FFmpeg from https://ffmpeg.org/download.html")
            print("  2. Ensure both 'ffmpeg' and 'ffprobe' commands are in PATH")
            print("  3. Verify installation: ffmpeg -version && ffprobe -version")
            print("  4. Restart terminal/IDE after installation")

        # Configuration remediation
        if any("render.yaml" in issue for issue in issues):
            print("\n🔧 Render Configuration:")
            print("  1. Ensure conf/render.yaml exists with acceptance settings")
            print("  2. Check audio targets and validation requirements")
            print("  3. Verify caption and legibility settings")

        if any("modules.yaml" in issue for issue in issues):
            print("\n🔧 Modules Configuration:")
            print("  1. Ensure conf/modules.yaml exists with procedural settings")
            print("  2. Set procedural.seed for deterministic behavior")
            print("  3. Configure placement and motion settings")

        print(f"\n❌ Environment check FAILED with {len(issues)} issues")
        return False
    else:
        print("✅ Environment check PASSED - all requirements met")

        # Print FFmpeg info
        if ffmpeg_info:
            print("\n=== FFmpeg Information ===")
            for tool, info in ffmpeg_info.items():
                if info.get("available"):
                    print(f"  {tool}: {info['version']} ✅")
                else:
                    print(f"  {tool}: {info['error']} ❌")

        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
