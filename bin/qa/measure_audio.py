import re
import subprocess


def _run(cmd: list[str]) -> str:
    """Run command and return combined stdout + stderr."""
    return (
        subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
        + subprocess.run(cmd, check=True, capture_output=True, text=True).stderr
    )


def ebur128_metrics(path: str) -> dict:
    """Extract LUFS and LRA metrics using ffmpeg ebur128 filter."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-nostats",
                "-hide_banner",
                "-i",
                path,
                "-filter_complex",
                "ebur128=metadata=1",
                "-f",
                "null",
                "-",
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
        txt = proc.stderr

        # Look for Integrated loudness and LRA
        m_i = re.findall(r"I:\s*(-?\d+\.\d+)\s+LUFS", txt)
        m_lra = re.findall(r"LRA:\s*(\d+\.\d+)\s+LU", txt)

        lufs = float(m_i[-1]) if m_i else None
        lra = float(m_lra[-1]) if m_lra else None

        return {"lufs": lufs, "lra": lra}
    except Exception as e:
        return {"lufs": None, "lra": None, "error": str(e)}


def true_peak_db(path: str) -> float | None:
    """Extract true peak level using ffmpeg astats filter."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-nostats",
                "-hide_banner",
                "-i",
                path,
                "-filter_complex",
                "astats=metadata=1:reset=1",
                "-f",
                "null",
                "-",
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
        vals = re.findall(r"Peak_level\s*:\s*(-?\d+\.\d+)", proc.stderr)
        return float(vals[-1]) if vals else None
    except Exception:
        return None


def silence_percentage(path: str) -> float:
    """Calculate percentage of silence in audio file."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-nostats",
                "-hide_banner",
                "-i",
                path,
                "-af",
                "silencedetect=n=-50dB:d=0.3",
                "-f",
                "null",
                "-",
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )

        # accumulate silence durations
        silences = re.findall(r"silence_duration: (\d+\.\d+)", proc.stderr)
        total_sil = sum(float(x) for x in silences)
        dur = float(ffprobe_duration(path))
        return (total_sil / max(dur, 1e-6)) * 100.0
    except Exception:
        return 0.0


def ffprobe_duration(path: str) -> float:
    """Get audio/video duration using ffprobe."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                path,
            ],
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        return float(proc.stdout.strip())
    except Exception:
        return 0.0


def sibilance_proxy_db(path: str) -> float | None:
    """Crude sibilance proxy using overall RMS level."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-nostats",
                "-hide_banner",
                "-i",
                path,
                "-af",
                "astats=metadata=1:reset=1",
                "-f",
                "null",
                "-",
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
        rms = re.findall(r"Overall RMS level\s*:\s*(-?\d+\.\d+)", proc.stderr)
        return float(rms[-1]) if rms else None
    except Exception:
        return None


def ducking_applied_db(music_path: str, vo_path: str) -> float | None:
    """Compare music RMS when VO active vs inactive (approximate at 1s hop)."""
    # TODO: implement if separate stems exist; else return None
    return None
