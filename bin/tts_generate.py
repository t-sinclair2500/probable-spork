#!/usr/bin/env python3
import os, json, time, subprocess, tempfile
from util import single_lock, log_state, load_global_config, BASE, ensure_dirs

def main():
    cfg = load_global_config(); ensure_dirs(cfg)
    scripts_dir = os.path.join(BASE,"scripts")
    files = [f for f in os.listdir(scripts_dir) if f.endswith(".txt")]
    if not files:
        log_state("tts_generate","SKIP","no scripts"); print("No scripts"); return
    files.sort(reverse=True)
    sfile = os.path.join(scripts_dir, files[0])
    voice_dir = os.path.join(BASE,"voiceovers")
    os.makedirs(voice_dir, exist_ok=True)
    out_mp3 = os.path.join(voice_dir, files[0].replace(".txt",".mp3"))
    # Placeholder: synthesize a short VO, then normalize loudness using ffmpeg loudnorm
    import numpy as np, soundfile as sf
    sr = 22050
    dur_sec = 5
    t = np.linspace(0, dur_sec, int(sr*dur_sec), endpoint=False)
    tone = 0.05*np.sin(2*np.pi*220*t)
    wav_tmp = out_mp3.replace(".mp3",".wav")
    sf.write(wav_tmp, tone, sr)
    # Loudness normalization to -16 LUFS stereo target (mono handled by ffmpeg)
    norm_wav = wav_tmp.replace(".wav",".norm.wav")
    subprocess.run(f'ffmpeg -y -i "{wav_tmp}" -af loudnorm=I=-16:TP=-1.5:LRA=11 "{norm_wav}"', shell=True, check=True)
    subprocess.run(f'ffmpeg -y -i "{norm_wav}" -codec:a libmp3lame -qscale:a 2 "{out_mp3}"', shell=True, check=True)
    try:
        os.remove(wav_tmp)
        os.remove(norm_wav)
    except Exception:
        pass
    log_state("tts_generate","OK",os.path.basename(out_mp3))
    print(f"Wrote placeholder VO {out_mp3}. Replace with real Coqui/OpenAI TTS in Phase 2.")

if __name__ == "__main__":
    with single_lock():
        main()
