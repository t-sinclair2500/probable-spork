# bin/utils/ffmpeg.py
import platform
import shutil
from typing import List, Optional, Sequence
from bin.utils.subproc import run_streamed

def _default_codecs() -> List[str]:
    # Prefer VideoToolbox on macOS; otherwise just libx264.
    if platform.system().lower() == "darwin":
        return ["h264_videotoolbox", "libx264"]
    return ["libx264"]

def encode_with_fallback(
    input_path: str,
    output_path: str,
    crf: str = "19",
    a_bitrate: str = "320k",
    profile: str = "high",
    pix_fmt: str = "yuv420p",
    extra_video_args: Optional[Sequence[str]] = None,
    codecs: Optional[List[str]] = None,
    log_path: Optional[str] = None,
):
    """
    Try a list of codecs for -c:v, in order. On failure of one, try the next.
    Raises RuntimeError after exhausting all options.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH")

    vcodecs = codecs or _default_codecs()
    last_err = None
    for codec in vcodecs:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-c:v", codec,
            "-crf", crf,
            "-profile:v", profile,
            "-pix_fmt", pix_fmt,
            "-c:a", "aac",
            "-b:a", a_bitrate,
            output_path,
        ]
        if extra_video_args:
            # insert extra args right after codec selection if needed
            # basic merge: ffmpeg args are order sensitive; append near -c:v settings if required
            idx = cmd.index("-c:v")
            # keep it simple: append at the end
            cmd = cmd[:-1] + list(extra_video_args) + [output_path]

        try:
            run_streamed(cmd, log_path=log_path, tail_lines=200, check=True)
            return  # success
        except Exception as e:
            last_err = e
    raise RuntimeError(f"All codec attempts failed. Last error: {last_err}")
