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


def synthesize_placeholder_wav(text: str, wav_out: str):
    # Lightweight placeholder: generate a short tone via ffmpeg (no extra deps)
    dur_sec = max(3, min(10, int(len(text.split()) / 3) or 3))
    # 220 Hz sine tone
    subprocess.run(
        f'ffmpeg -y -f lavfi -i sine=frequency=220:sample_rate=22050:duration={dur_sec} "{wav_out}"',
        shell=True,
        check=False,
    )


def loudnorm_to_mp3(wav_in: str, mp3_out: str):
    norm_wav = wav_in.replace(".wav", ".norm.wav")
    subprocess.run(
        f'ffmpeg -y -i "{wav_in}" -af loudnorm=I=-16:TP=-1.5:LRA=11 "{norm_wav}"',
        shell=True,
        check=False,
    )
    src = norm_wav if os.path.exists(norm_wav) else wav_in
    subprocess.run(
        f'ffmpeg -y -i "{src}" -codec:a libmp3lame -qscale:a 2 "{mp3_out}"',
        shell=True,
        check=False,
    )
    try:
        if os.path.exists(norm_wav):
            os.remove(norm_wav)
    except Exception:
        pass


def main():
    cfg = load_config()
    guard_system(cfg)
    env = load_env()

    scripts_dir = os.path.join(BASE, "scripts")
    files = [f for f in os.listdir(scripts_dir) if f.endswith(".txt")]
    if not files:
        log_state("tts_generate", "SKIP", "no scripts")
        print("No scripts")
        return
    files.sort(reverse=True)
    sfile = os.path.join(scripts_dir, files[0])
    text = open(sfile, "r", encoding="utf-8").read()
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
    try:
        provider = getattr(cfg.tts, "provider", "coqui").lower()
        if provider == "coqui":
            try:
                from TTS.api import TTS  # type: ignore

                model_name = getattr(cfg.tts, "voice", "tts_models/en/ljspeech/tacotron2-DDC")
                tts = TTS(model_name)
                tts.tts_to_file(text=text, file_path=wav_tmp)
                used = "coqui"
            except Exception:
                synthesize_placeholder_wav(text, wav_tmp)
        elif (provider == "openai" or getattr(cfg.tts, "openai_enabled", False)) and env.get("OPENAI_API_KEY"):
            try:
                # Use OpenAI speech synthesis REST API to produce MP3 directly
                import requests

                api_key = env.get("OPENAI_API_KEY")
                voice = "alloy"
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
                    synthesize_placeholder_wav(text, wav_tmp)
                    used = "placeholder"
            except Exception:
                synthesize_placeholder_wav(text, wav_tmp)
                used = "placeholder"
        else:
            synthesize_placeholder_wav(text, wav_tmp)
    except Exception:
        synthesize_placeholder_wav(text, wav_tmp)

    loudnorm_to_mp3(wav_tmp, out_mp3)
    try:
        os.remove(wav_tmp)
    except Exception:
        pass

    dur = ffprobe_duration(out_mp3)
    log_state("tts_generate", "OK", f"{os.path.basename(out_mp3)};prov={used};dur={round(dur,1)}s")
    print(f"Wrote VO {out_mp3} via {used} ({round(dur,1)}s)")


if __name__ == "__main__":
    with single_lock():
        main()
