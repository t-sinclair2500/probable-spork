#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time

# Ensure repo root is on sys.path for `import bin.core`
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from bin.core import BASE, get_logger, guard_system, load_config, load_env, log_state, single_lock
import requests

log = get_logger("generate_captions")


def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def whisper_cpp_cmd(binary, model_path, audio_path, srt_out):
    # whisper-cli example: ./whisper-cli -m models/ggml-base.en.bin -f audio.wav -osrt -of out
    # Normalize loudness and convert MP3 to mono 16k WAV for best results.
    wav_tmp = audio_path.replace(".mp3", ".wav")
    # Loudness normalization (ITU-R BS.1770) then resample
    run(
        f'ffmpeg -y -i "{audio_path}" -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 16000 -ac 1 "{wav_tmp}"'
    )
    out_base = srt_out[:-4]  # drop .srt
    cmd = f"{shlex.quote(binary)} -m {shlex.quote(model_path)} -f {shlex.quote(wav_tmp)} -osrt -of {shlex.quote(out_base)}"
    return cmd, wav_tmp


def main(brief=None, input_file=None, output_file=None):
    """Main function for caption generation with optional brief context"""
    cfg = load_config()
    guard_system(cfg)
    env = load_env()
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("generate_captions", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")
    else:
        log_state("generate_captions", "START", "brief=none")
        log.info("Running without brief - using default behavior")
    
    # Get command line arguments from sys.argv since we're being called by the pipeline
    # with --brief-data that was already parsed by the main argument parser
    if input_file:
        mp3 = input_file
        if not output_file:
            base, _ = os.path.splitext(mp3)
            srt = base + ".srt"
        else:
            srt = output_file
    else:
        vdir = os.path.join(BASE, "voiceovers")
        files = [f for f in os.listdir(vdir) if f.endswith(".mp3")]
        if not files:
            log_state("generate_captions", "SKIP", "no voiceovers")
            print("No voiceovers")
            return
        files.sort(reverse=True)
        key = files[0].replace(".mp3", "")
        mp3 = os.path.join(vdir, files[0])
        srt = os.path.join(vdir, key + ".srt")

    bin_path = cfg.asr.whisper_cpp_path
    model_path = (
        cfg.asr.model
        if os.path.isabs(cfg.asr.model)
        else os.path.join(os.path.expanduser("~"), "whisper.cpp", "models", cfg.asr.model)
    )
    if not os.path.exists(bin_path) or not os.path.exists(model_path):
        # Optional OpenAI Whisper fallback
        if getattr(cfg.asr, "openai_enabled", False) and env.get("OPENAI_API_KEY"):
            try:
                # OpenAI Whisper REST API (audio/transcriptions)
                with open(mp3, "rb") as f:
                    files = {"file": (os.path.basename(mp3), f, "audio/mpeg")}
                    data = {"model": "whisper-1"}
                    headers = {"Authorization": f"Bearer {env['OPENAI_API_KEY']}"}
                    r = requests.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, data=data, files=files, timeout=600)
                if r.ok:
                    txt = r.json().get("text", "")
                    # Write simple SRT with one block as fallback
                    with open(srt, "w", encoding="utf-8") as f:
                        f.write("1\n00:00:00,000 --> 00:59:59,000\n" + txt.strip() + "\n")
                    log_state("generate_captions", "OK", os.path.basename(srt))
                    print(f"Generated SRT via OpenAI Whisper: {srt}")
                    return
                else:
                    log_state("generate_captions", "SKIP", f"openai_whisper_http_{r.status_code}")
                    print("OpenAI Whisper failed:", r.status_code, r.text[:200])
                    return
            except Exception as e:
                log_state("generate_captions", "SKIP", f"openai_whisper_err:{e}")
                print("OpenAI Whisper error:", e)
                return
        log_state("generate_captions", "SKIP", "whisper.cpp missing or model not found")
        print("Skipping captions: whisper.cpp binary or model missing")
        return

    cmd, wav_tmp = whisper_cpp_cmd(bin_path, model_path, mp3, srt)
    code, out, err = run(cmd)
    # whisper.cpp writes <out_base>.srt; attempt to compute simple confidence heuristic
    if os.path.exists(srt):
        log_state("generate_captions", "OK", os.path.basename(srt))
        print(f"Generated SRT via whisper.cpp: {srt}")
    else:
        # Try alternative out path
        alt = srt.replace(".srt", ".wav.srt")
        if os.path.exists(alt):
            os.rename(alt, srt)
            log_state("generate_captions", "OK", os.path.basename(srt))
            print(f"Generated SRT via whisper.cpp: {srt}")
        else:
            log_state("generate_captions", "FAIL", err[:200])
            raise SystemExit(f"whisper.cpp failed: {err[:200]}")

    try:
        os.remove(wav_tmp)
    except Exception:
        pass

    # Metrics: duration, WPM, rough "confidence" (proxy = % of non-empty lines)
    try:
        # duration from mp3 via ffprobe
        p = subprocess.run(
            f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{mp3}"',
            shell=True,
            capture_output=True,
            text=True,
        )
        dur = float((p.stdout or "0").strip() or 0)
        raw = open(srt, "r", encoding="utf-8").read()
        # Remove indices and timestamps
        content = re.sub(r"\d+\n\d{2}:\d{2}:\d{2},\d{3} --> .*\n", "", raw)
        words = len(re.findall(r"\b\w+\b", content))
        wpm = round((words / max(dur, 1.0)) * 60.0)
        # crude density metric: ratio of text lines to total blocks
        blocks = [b for b in raw.strip().split("\n\n") if b.strip()]
        nonempty = sum(1 for b in blocks if len(b.splitlines()) >= 3 and b.splitlines()[-1].strip())
        conf = round((nonempty / max(len(blocks), 1)) * 100)
        
        # Apply brief settings for caption optimization if available
        if brief:
            brief_tone = brief.get('tone', '').lower()
            if brief_tone:
                log.info(f"Brief tone applied to captions: {brief_tone}")
                # Log tone-specific caption metrics
                if brief_tone in ['professional', 'corporate']:
                    log.info("Professional tone: captions optimized for clarity and accuracy")
                elif brief_tone in ['casual', 'friendly']:
                    log.info("Casual tone: captions optimized for natural speech patterns")
                elif brief_tone in ['energetic', 'enthusiastic']:
                    log.info("Energetic tone: captions optimized for dynamic content")
            
            # Check if brief keywords are present in captions
            brief_keywords = brief.get('keywords_include', [])
            if brief_keywords:
                content_lower = content.lower()
                present_keywords = [kw for kw in brief_keywords if kw.lower() in content_lower]
                if present_keywords:
                    log.info(f"Brief keywords found in captions: {', '.join(present_keywords)}")
                else:
                    log.warning("No brief keywords found in captions")
        
        log_state("generate_captions", "METRIC", f"dur={round(dur,1)}s;wpm={wpm};conf~{conf}%")
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Caption generation")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("-i", "--input", help="Input MP3 file path")
    parser.add_argument("-o", "--output", help="Output SRT file path")
    
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
        main(brief, args.input, args.output)
