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
    # whisper.cpp example: ./main -m models/ggml-base.en.bin -f audio.wav -osrt -of out
    # We convert MP3 to WAV first with ffmpeg to ensure compatibility.
    wav_tmp = audio_path.replace(".mp3", ".wav")
    run(f'ffmpeg -y -i "{audio_path}" -ar 16000 -ac 1 "{wav_tmp}"')
    out_base = srt_out[:-4]  # drop .srt
    cmd = f"{shlex.quote(binary)} -m {shlex.quote(model_path)} -f {shlex.quote(wav_tmp)} -osrt -of {shlex.quote(out_base)}"
    return cmd, wav_tmp


def main():
    parser = argparse.ArgumentParser(description="Generate captions (SRT) using whisper.cpp")
    parser.add_argument("--input", "-i", help="Input audio file (.mp3)")
    parser.add_argument("--output", "-o", help="Output SRT path")
    args = parser.parse_args()

    cfg = load_config()
    guard_system(cfg)
    if args.input:
        mp3 = args.input
        if not args.output:
            base, _ = os.path.splitext(mp3)
            srt = base + ".srt"
        else:
            srt = args.output
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
    env = load_env()
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
    # whisper.cpp writes <out_base>.srt
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

    # Metrics: duration and WPM estimate
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
        log_state("generate_captions", "METRIC", f"dur={round(dur,1)}s;wpm={wpm}")
    except Exception:
        pass


if __name__ == "__main__":
    with single_lock():
        main()
