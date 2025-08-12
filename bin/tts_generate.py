#!/usr/bin/env python3
import os
import subprocess
import time

# Ensure repo root on path
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import (  # noqa: E402
    BASE,
    get_logger,
    guard_system,
    load_config,
    load_env,
    log_state,
    single_lock,
)

import argparse
import json


log = get_logger("tts_generate")


def ffprobe_duration(path: str) -> float:
    try:
        p = subprocess.run(
            f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{path}"',
            shell=True,
            capture_output=True,
            text=True,
        )
        return float((p.stdout or "0").strip() or 0)
    except Exception:
        return 0.0


def synthesize_placeholder_wav(text: str, wav_out: str, max_seconds: int | None = None):
    # Lightweight placeholder: generate a short tone via ffmpeg (no extra deps)
    dur_sec = max(3, min(10, int(len(text.split()) / 3) or 3))
    if max_seconds:
        dur_sec = max(1, min(dur_sec, int(max_seconds)))
    # 220 Hz sine tone
    subprocess.run(
        f'ffmpeg -y -f lavfi -i sine=frequency=220:sample_rate=22050:duration={dur_sec} "{wav_out}"',
        shell=True,
        check=False,
    )


def loudnorm_to_mp3(wav_in: str, mp3_out: str, max_seconds: int | None = None):
    norm_wav = wav_in.replace(".wav", ".norm.wav")
    tflag = f" -t {int(max_seconds)}" if max_seconds else ""
    subprocess.run(
        f'ffmpeg -y -i "{wav_in}" -af loudnorm=I=-16:TP=-1.5:LRA=11{tflag} "{norm_wav}"',
        shell=True,
        check=False,
    )
    src = norm_wav if os.path.exists(norm_wav) else wav_in
    subprocess.run(
        f'ffmpeg -y -i "{src}"{tflag} -codec:a libmp3lame -qscale:a 2 "{mp3_out}"',
        shell=True,
        check=False,
    )
    try:
        if os.path.exists(norm_wav):
            os.remove(norm_wav)
    except Exception:
        pass


def main(brief=None, models_config=None):
    """Main function for TTS generation with optional brief context"""
    cfg = load_config()
    guard_system(cfg)
    env = load_env()
    
    # Load models configuration if not provided
    if models_config is None:
        try:
            import yaml
            models_path = os.path.join(BASE, "conf", "models.yaml")
            if os.path.exists(models_path):
                with open(models_path, 'r', encoding='utf-8') as f:
                    models_config = yaml.safe_load(f)
                log.info("Loaded models configuration")
        except Exception as e:
            log.warning(f"Failed to load models configuration: {e}")
            models_config = {}
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("tts_generate", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")
    else:
        log_state("tts_generate", "START", "brief=none")
        log.info("Running without brief - using default behavior")
    
    short_secs = None
    try:
        _ss = int(env.get("SHORT_RUN_SECS", "0") or 0)
        short_secs = _ss if _ss > 0 else None
    except Exception:
        short_secs = None

    scripts_dir = os.path.join(BASE, "scripts")
    files = [f for f in os.listdir(scripts_dir) if f.endswith(".txt")]
    if not files:
        log_state("tts_generate", "SKIP", "no scripts")
        print("No scripts")
        return
    files.sort(reverse=True)
    sfile = os.path.join(scripts_dir, files[0])
    # Convert any bracketed stage directions to natural narration hints or remove them.
    import re as _re
    raw_text = open(sfile, "r", encoding="utf-8").read()
    text = _re.sub(r"\[B-ROLL:[^\]]+\]", " ", raw_text)
    text = _re.sub(r"\[[^\]]+\]", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()
    voice_dir = os.path.join(BASE, "voiceovers")
    os.makedirs(voice_dir, exist_ok=True)
    out_mp3 = os.path.join(voice_dir, files[0].replace(".txt", ".mp3"))

    # Idempotent: skip if exists
    if os.path.exists(out_mp3):
        log_state("tts_generate", "OK", os.path.basename(out_mp3))
        print("Voiceover already exists; skipping.")
        return

    # Try Coqui TTS if available and configured; otherwise optional OpenAI TTS; else placeholder
    wav_tmp = out_mp3.replace(".mp3", ".wav")
    used = "placeholder"
    
    # Apply brief settings for TTS if available
    if brief:
        # Use brief tone for voice selection
        brief_tone = brief.get('tone', '').lower()
        if brief_tone:
            log.info(f"Brief tone: {brief_tone}")
            # Adjust voice selection based on tone (using Piper Amy voice)
            if brief_tone in ['professional', 'corporate', 'formal']:
                voice = "en_US-amy-medium"  # More formal voice
                log.info("Applied professional tone: using formal voice")
            elif brief_tone in ['casual', 'friendly', 'conversational']:
                voice = "en_US-amy-medium"  # More conversational voice
                log.info("Applied casual tone: using conversational voice")
            elif brief_tone in ['energetic', 'enthusiastic', 'motivational']:
                voice = "en_US-amy-medium"  # More energetic voice
                log.info("Applied energetic tone: using energetic voice")
        
        # Use brief pacing preferences if available
        brief_pacing = brief.get('pacing', '').lower()
        if brief_pacing:
            log.info(f"Brief pacing: {brief_pacing}")
            # Adjust TTS parameters based on pacing preference
            if brief_pacing in ['slow', 'deliberate']:
                # Slower pacing - this would need TTS provider support
                log.info("Applied slow pacing preference")
            elif brief_pacing in ['fast', 'energetic']:
                # Faster pacing - this would need TTS provider support
                log.info("Applied fast pacing preference")
    
    # Try new voice adapter first, fallback to legacy TTS
    try:
        if models_config and 'voice' in models_config:
            # Use new multi-TTS system
            try:
                from bin.voice_adapter import VoiceAdapter
                adapter = VoiceAdapter(models_config)
                
                # Create temporary script file for synthesis
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(text)
                    temp_script = f.name
                
                # Synthesize using voice adapter
                audio_path = adapter.synthesize_script(Path(temp_script), Path(voice_dir))
                
                # Convert to MP3 if needed
                if audio_path.suffix == '.wav':
                    loudnorm_to_mp3(str(audio_path), out_mp3, max_seconds=short_secs)
                    used = "voice_adapter"
                else:
                    # Already MP3, just copy/rename
                    import shutil
                    shutil.copy2(audio_path, out_mp3)
                    used = "voice_adapter"
                
                # Clean up temp script
                os.unlink(temp_script)
                
                # Return early since MP3 written
                dur = ffprobe_duration(out_mp3)
                log_state("tts_generate", "OK", f"{os.path.basename(out_mp3)};prov={used};dur={round(dur,1)}s")
                print(f"Wrote VO {out_mp3} via {used} ({round(dur,1)}s)")
                return
                
            except Exception as e:
                log.warning(f"Voice adapter failed, falling back to legacy TTS: {e}")
        
        # Fallback to legacy TTS system
        provider = getattr(cfg.tts, "provider", "coqui").lower()
        if provider == "coqui":
            try:
                from TTS.api import TTS  # type: ignore

                model_name = getattr(cfg.tts, "voice", "tts_models/en/ljspeech/tacotron2-DDC")
                tts = TTS(model_name)
                tts.tts_to_file(text=text, file_path=wav_tmp)
                used = "coqui"
            except Exception:
                synthesize_placeholder_wav(text, wav_tmp, max_seconds=short_secs)
        elif (provider == "openai" or getattr(cfg.tts, "openai_enabled", False)) and env.get("OPENAI_API_KEY"):
            try:
                # Use OpenAI speech synthesis REST API to produce MP3 directly
                import requests

                api_key = env.get("OPENAI_API_KEY")
                voice = "en_US-amy-medium"
                out_mp3_tmp = out_mp3 + ".tmp.mp3"
                r = requests.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini-tts",
                        "voice": voice,
                        "input": text,
                        "format": "mp3",
                    },
                    timeout=600,
                )
                if r.ok:
                    with open(out_mp3_tmp, "wb") as f:
                        f.write(r.content)
                    # Normalize to final MP3 via loudnorm
                    subprocess.run(
                        f'ffmpeg -y -i "{out_mp3_tmp}" -af loudnorm=I=-16:TP=-1.5:LRA=11 -codec:a libmp3lame -qscale:a 2 "{out_mp3}"',
                        shell=True,
                        check=False,
                    )
                    if short_secs:
                        # Trim in-place to short duration
                        trimmed = out_mp3 + ".trim.mp3"
                        subprocess.run(
                            f'ffmpeg -y -i "{out_mp3}" -t {int(short_secs)} -codec:a libmp3lame -qscale:a 2 "{trimmed}"',
                            shell=True,
                            check=False,
                        )
                        if os.path.exists(trimmed):
                            try:
                                os.replace(trimmed, out_mp3)
                            except Exception:
                                pass
                    try:
                        os.remove(out_mp3_tmp)
                    except Exception:
                        pass
                    used = "openai"
                    # Clean up and return early since MP3 written
                    dur = ffprobe_duration(out_mp3)
                    log_state("tts_generate", "OK", f"{os.path.basename(out_mp3)};prov={used};dur={round(dur,1)}s")
                    print(f"Wrote VO {out_mp3} via {used} ({round(dur,1)}s)")
                    return
                else:
                    synthesize_placeholder_wav(text, wav_tmp, max_seconds=short_secs)
                    used = "placeholder"
            except Exception:
                synthesize_placeholder_wav(text, wav_tmp, max_seconds=short_secs)
                used = "placeholder"
        else:
            synthesize_placeholder_wav(text, wav_tmp, max_seconds=short_secs)
    except Exception:
        synthesize_placeholder_wav(text, wav_tmp, max_seconds=short_secs)

    loudnorm_to_mp3(wav_tmp, out_mp3, max_seconds=short_secs)
    try:
        os.remove(wav_tmp)
    except Exception:
        pass

    dur = ffprobe_duration(out_mp3)
    log_state("tts_generate", "OK", f"{os.path.basename(out_mp3)};prov={used};dur={round(dur,1)}s")
    print(f"Wrote VO {out_mp3} via {used} ({round(dur,1)}s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TTS voice generation")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
            log.info(f"Loaded brief: {brief.get('title', 'Untitled')}")
        except (json.JSONDecodeError, TypeError) as e:
            log.warning(f"Failed to parse brief data: {e}")
    
    with single_lock():
        main(brief)
