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
from bin.core import BASE, get_logger, load_config, log_state, single_lock

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
    if not os.path.exists(bin_path):
        log_state("generate_captions", "SKIP", "whisper.cpp binary not found")
        print("Skipping captions: whisper.cpp binary not found at", bin_path)
        return
    if not os.path.exists(model_path):
        # Try to fetch tiny/base English if not present
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        # Do not auto-download. Skip to keep pipeline running.
        log_state("generate_captions", "SKIP", "ASR model not found")
        print("Skipping captions: ASR model not found at", model_path)
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


if __name__ == "__main__":
    with single_lock():
        main()
