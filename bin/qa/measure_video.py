import json
import subprocess


def ffprobe_streams(path: str) -> dict:
    """Get detailed stream information using ffprobe."""
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout
        return json.loads(out)
    except Exception as e:
        return {"error": str(e)}


def delivery_profile_ok(streams: dict, th: dict) -> tuple[bool, list]:
    """Check if video meets delivery profile requirements."""
    notes = []

    if "error" in streams:
        return False, [f"ffprobe error: {streams['error']}"]

    v = next(
        (s for s in streams.get("streams", []) if s.get("codec_type") == "video"), None
    )
    a = next(
        (s for s in streams.get("streams", []) if s.get("codec_type") == "audio"), None
    )

    if not v or not a:
        return False, ["missing video/audio streams"]

    vcodec = v.get("codec_name", "")
    pix = v.get("pix_fmt", "")
    prof = v.get("profile", "")
    abitrate_kbps = int(int(a.get("bit_rate", "320000")) / 1000)
    sr = int(a.get("sample_rate", "48000"))

    ok = True

    # Video codec check
    if vcodec not in ("h264", "prores"):
        ok = False
        notes.append(f"vcodec={vcodec}")

    # Pixel format check for H.264
    if vcodec == "h264" and pix != "yuv420p":
        ok = False
        notes.append(f"pix_fmt={pix}")

    # Profile check (non-blocking warning)
    if vcodec == "h264" and prof.lower() not in (
        "high",
        "constrained baseline",
        "main",
    ):
        notes.append(f"profile={prof}")

    # Audio bitrate check
    if abitrate_kbps < th.get("audio_bitrate_kbps_min", 320):
        ok = False
        notes.append(f"audio_bitrate={abitrate_kbps}")

    # Sample rate check
    if sr != th.get("audio_sample_rate_hz", 48000):
        ok = False
        notes.append(f"sample_rate={sr}")

    return ok, notes
