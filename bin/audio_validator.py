#!/usr/bin/env python3
"""
Audio Validation and Measurement

Measures audio quality metrics including LUFS, true peak, and ducking effectiveness.
Used by the acceptance pipeline to ensure audio meets broadcast standards.
Enhanced with FFmpeg robustness and ffprobe validation.
"""

import json
import os
import subprocess

# Ensure repo root on path
import sys
import tempfile
from typing import Any, Dict, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger, load_config

log = get_logger("audio_validator")


class AudioValidationError(Exception):
    """Custom exception for audio validation failures"""

    def __init__(self, message: str, error_type: str, details: Dict[str, Any] = None):
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        super().__init__(self.message)


class FFmpegValidator:
    """Validates FFmpeg/FFprobe availability and provides robust audio processing"""

    def __init__(self):
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self._validate_ffmpeg_installation()

    def _validate_ffmpeg_installation(self):
        """Validate FFmpeg and FFprobe installation"""
        try:
            # Check ffmpeg
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.ffmpeg_path = "ffmpeg"
                log.info("[audio-accept] FFmpeg found and working")
            else:
                raise AudioValidationError(
                    "FFmpeg failed version check", "ffmpeg_installation_failed"
                )
        except FileNotFoundError:
            raise AudioValidationError("FFmpeg not found in PATH", "ffmpeg_not_found")
        except subprocess.TimeoutExpired:
            raise AudioValidationError(
                "FFmpeg version check timed out", "ffmpeg_timeout"
            )
        except Exception as e:
            raise AudioValidationError(
                f"FFmpeg validation error: {str(e)}", "ffmpeg_validation_error"
            )

        try:
            # Check ffprobe
            result = subprocess.run(
                ["ffprobe", "-version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.ffprobe_path = "ffprobe"
                log.info("[audio-accept] FFprobe found and working")
            else:
                raise AudioValidationError(
                    "FFprobe failed version check", "ffprobe_installation_failed"
                )
        except FileNotFoundError:
            raise AudioValidationError("FFprobe not found in PATH", "ffprobe_not_found")
        except subprocess.TimeoutExpired:
            raise AudioValidationError(
                "FFprobe version check timed out", "ffprobe_timeout"
            )
        except Exception as e:
            raise AudioValidationError(
                f"FFprobe validation error: {str(e)}", "ffprobe_validation_error"
            )

    def probe_audio_stream(self, file_path: str) -> Dict[str, Any]:
        """Probe audio stream information using ffprobe"""
        try:
            cmd = [
                self.ffprobe_path,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-select_streams",
                "a:0",  # Select first audio stream
                file_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                raise AudioValidationError(
                    f"FFprobe failed: {result.stderr}",
                    "ffprobe_probe_failed",
                    {"stderr": result.stderr, "returncode": result.returncode},
                )

            probe_data = json.loads(result.stdout)
            streams = probe_data.get("streams", [])

            if not streams:
                raise AudioValidationError(
                    "No audio streams found in file",
                    "no_audio_streams",
                    {"file_path": file_path},
                )

            audio_stream = streams[0]
            log.info(
                f"[audio-accept] Audio stream probed: {audio_stream.get('codec_name', 'unknown')} "
                f"({audio_stream.get('sample_rate', 'unknown')}Hz, "
                f"{audio_stream.get('channels', 'unknown')}ch)"
            )

            return audio_stream

        except json.JSONDecodeError as e:
            raise AudioValidationError(
                f"Failed to parse ffprobe output: {str(e)}",
                "ffprobe_parse_error",
                {
                    "file_path": file_path,
                    "raw_output": result.stdout if "result" in locals() else None,
                },
            )
        except subprocess.TimeoutExpired:
            raise AudioValidationError(
                "FFprobe probe timed out", "ffprobe_timeout", {"file_path": file_path}
            )
        except Exception as e:
            raise AudioValidationError(
                f"FFprobe probe error: {str(e)}",
                "ffprobe_error",
                {"file_path": file_path},
            )

    def extract_audio_safely(
        self, video_path: str, output_path: str, codec: str = "mp3"
    ) -> str:
        """Extract audio from video with fallback codec handling"""
        # Try preferred codec first
        codecs_to_try = [codec, "aac", "mp3", "wav"]

        for attempt_codec in codecs_to_try:
            try:
                cmd = [
                    self.ffmpeg_path,
                    "-i",
                    video_path,
                    "-vn",  # No video
                    "-acodec",
                    attempt_codec,
                    "-y",  # Overwrite output
                    output_path,
                ]

                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120
                )

                if result.returncode == 0 and os.path.exists(output_path):
                    log.info(
                        f"[audio-accept] Audio extracted successfully with {attempt_codec} codec"
                    )
                    return output_path
                else:
                    log.warning(
                        f"[audio-accept] Failed to extract with {attempt_codec}: {result.stderr}"
                    )

            except subprocess.TimeoutExpired:
                log.warning(
                    f"[audio-accept] Audio extraction timed out with {attempt_codec}"
                )
                continue
            except Exception as e:
                log.warning(
                    f"[audio-accept] Audio extraction error with {attempt_codec}: {str(e)}"
                )
                continue

        raise AudioValidationError(
            f"Failed to extract audio with any codec: {', '.join(codecs_to_try)}",
            "audio_extraction_failed",
            {"video_path": video_path, "attempted_codecs": codecs_to_try},
        )


class AudioValidator:
    """Validates audio quality metrics for acceptance pipeline"""

    def __init__(self, config=None):
        self.config = config or load_config()
        self.temp_dir = tempfile.mkdtemp(prefix="audio_validator_")

        # Initialize FFmpeg validator
        try:
            self.ffmpeg = FFmpegValidator()
            log.info("[audio-accept] FFmpeg validation initialized successfully")
        except AudioValidationError as e:
            log.error(f"[audio-accept] FFmpeg validation failed: {e.message}")
            raise

        # Audio targets from config
        audio_cfg = getattr(self.config.render, "audio", None)
        if audio_cfg:
            self.vo_lufs_target = getattr(audio_cfg, "vo_lufs_target", -16.0)
            self.music_lufs_target = getattr(audio_cfg, "music_lufs_target", -23.0)
            self.true_peak_max = getattr(audio_cfg, "true_peak_max", -1.0)
            self.ducking_min_db = getattr(audio_cfg, "ducking_min_db", 6.0)
            self.enable_auto_normalization = getattr(
                audio_cfg, "enable_auto_normalization", True
            )
        else:
            # Fallback to old config values
            self.vo_lufs_target = getattr(self.config.tts, "lufs_target", -16.0)
            self.music_lufs_target = getattr(self.config.render, "music_db", -22.0) + 6
            self.true_peak_max = -1.0
            self.ducking_min_db = 6.0
            self.enable_auto_normalization = True

    def __del__(self):
        """Clean up temporary files."""
        try:
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def validate_audio_for_acceptance(
        self, audio_path: str, expected_type: str = "mixed"
    ) -> Dict[str, Any]:
        """
        Validate audio file for acceptance pipeline with robust error handling.

        Args:
            audio_path: Path to audio file
            expected_type: Type of audio ("voiceover", "music", "mixed")

        Returns:
            Dict with validation results and metrics
        """
        log.info(
            f"[audio-accept] Starting acceptance validation for {audio_path} ({expected_type})"
        )

        try:
            # Validate file exists
            if not os.path.exists(audio_path):
                return {
                    "valid": False,
                    "error": f"Audio file not found: {audio_path}",
                    "error_type": "file_not_found",
                }

            # Probe audio stream first
            try:
                stream_info = self.ffmpeg.probe_audio_stream(audio_path)
                log.info(
                    f"[audio-accept] Audio stream validated: {stream_info.get('codec_name', 'unknown')}"
                )
            except AudioValidationError as e:
                return {
                    "valid": False,
                    "error": f"Audio stream validation failed: {e.message}",
                    "error_type": e.error_type,
                    "details": e.details,
                }

            # Measure basic audio metrics
            try:
                metrics = self._measure_audio_metrics(audio_path)
                log.info(
                    f"[audio-accept] Audio metrics measured: LUFS={metrics.get('lufs', 'N/A')}, "
                    f"Peak={metrics.get('true_peak', 'N/A')}"
                )
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Audio measurement failed: {str(e)}",
                    "error_type": "measurement_failed",
                    "stream_info": stream_info,
                }

            # Validate against targets
            validation = self._validate_metrics(metrics, expected_type)

            # If validation fails, attempt one normalization (if enabled)
            if (
                not validation["valid"]
                and validation.get("can_normalize", False)
                and self.enable_auto_normalization
            ):
                log.info(
                    f"[audio-accept] Audio validation failed, attempting normalization for {audio_path}"
                )
                try:
                    normalized_path = self._normalize_audio(audio_path, expected_type)
                    if normalized_path:
                        # Re-validate normalized audio
                        normalized_metrics = self._measure_audio_metrics(
                            normalized_path
                        )
                        normalized_validation = self._validate_metrics(
                            normalized_metrics, expected_type
                        )

                        validation.update(
                            {
                                "normalized": True,
                                "normalized_path": normalized_path,
                                "normalized_metrics": normalized_metrics,
                                "normalized_validation": normalized_validation,
                            }
                        )

                        # Use normalized results if successful
                        if normalized_validation["valid"]:
                            validation.update(normalized_validation)
                            log.info(
                                "[audio-accept] Audio normalized and now passes validation"
                            )
                        else:
                            log.warning(
                                "[audio-accept] Audio normalization failed to resolve issues"
                            )
                except Exception as e:
                    log.warning(f"[audio-accept] Audio normalization failed: {str(e)}")
                    validation["normalization_error"] = str(e)

            # Add stream information to results
            validation["stream_info"] = stream_info
            validation["file_path"] = audio_path
            validation["expected_type"] = expected_type

            log.info(
                f"[audio-accept] Acceptance validation completed: {'PASS' if validation['valid'] else 'FAIL'}"
            )
            return validation

        except Exception as e:
            log.error(
                f"[audio-accept] Unexpected error during acceptance validation: {str(e)}"
            )
            return {
                "valid": False,
                "error": f"Unexpected validation error: {str(e)}",
                "error_type": "unexpected_error",
                "file_path": audio_path,
            }

    def validate_ducking(
        self,
        mixed_audio_path: str,
        voiceover_path: str,
        music_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate that ducking is properly applied during speech segments.

        Args:
            mixed_audio_path: Path to final mixed audio
            voiceover_path: Path to voiceover audio
            music_path: Optional path to music bed for reference

        Returns:
            Dict with ducking validation results
        """
        try:
            # Extract speech segments from voiceover
            speech_segments = self._detect_speech_segments(voiceover_path)

            # If no silence detected, assume continuous speech
            if not speech_segments:
                # Get audio duration to create a single speech segment
                try:
                    import subprocess

                    cmd = [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        voiceover_path,
                    ]
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, check=True
                    )
                    duration = float(result.stdout.strip())

                    speech_segments = [
                        {"start": 0.0, "end": duration, "duration": duration}
                    ]
                except Exception as e:
                    log.warning(f"Could not determine audio duration: {e}")
                    # Fallback: assume 10 seconds of continuous speech
                    speech_segments = [{"start": 0.0, "end": 10.0, "duration": 10.0}]

            # Measure audio levels in speech vs non-speech windows
            ducking_metrics = self._measure_ducking_effectiveness(
                mixed_audio_path, speech_segments
            )

            # Validate ducking effectiveness
            ducking_db = ducking_metrics.get("ducking_difference_db", 0)
            is_effective = ducking_db >= self.ducking_min_db

            return {
                "valid": is_effective,
                "ducking_difference_db": ducking_db,
                "min_required_db": self.ducking_min_db,
                "speech_segments": len(speech_segments),
                "metrics": ducking_metrics,
                "pass": is_effective,
            }

        except Exception as e:
            log.error(f"Ducking validation failed: {e}")
            return {"valid": False, "error": f"Ducking validation error: {str(e)}"}

    def _measure_audio_metrics(self, audio_path: str) -> Dict[str, Any]:
        """Measure LUFS, true peak, and other audio metrics using ffmpeg."""
        try:
            # Use ffprobe to get audio information
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                audio_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            audio_info = json.loads(result.stdout)

            # Extract audio stream info
            audio_stream = None
            for stream in audio_info.get("streams", []):
                if stream.get("codec_type") == "audio":
                    audio_stream = stream
                    break

            if not audio_stream:
                return {"error": "No audio stream found"}

            # Get duration and sample rate
            duration = float(audio_info.get("format", {}).get("duration", 0))
            sample_rate = int(audio_stream.get("sample_rate", 0))

            # Measure LUFS using ffmpeg loudnorm
            lufs_metrics = self._measure_lufs(audio_path)

            # Measure true peak
            true_peak = self._measure_true_peak(audio_path)

            return {
                "duration_seconds": duration,
                "sample_rate": sample_rate,
                "lufs_integrated": lufs_metrics.get("lufs_integrated"),
                "lufs_range": lufs_metrics.get("lufs_range"),
                "true_peak_db": true_peak,
                "format": audio_info.get("format", {}).get("format_name", "unknown"),
            }

        except Exception as e:
            log.error(f"Failed to measure audio metrics: {e}")
            return {"error": f"Measurement failed: {str(e)}"}

    def _measure_lufs(self, audio_path: str) -> Dict[str, float]:
        """Measure LUFS using ffmpeg loudnorm filter."""
        try:
            # Create temporary file for analysis
            temp_output = os.path.join(self.temp_dir, "lufs_analysis.wav")

            # Use loudnorm filter to measure without changing the audio
            cmd = [
                "ffmpeg",
                "-i",
                audio_path,
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                "-f",
                "null",
                "-",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse the JSON output from loudnorm
            lufs_data = {}
            for line in result.stderr.split("\n"):
                line = line.strip()
                if line.startswith('"input_i"'):
                    try:
                        # Extract input_i value
                        import re

                        i_match = re.search(r'"input_i"\s*:\s*"([-\d.]+)"', line)
                        if i_match:
                            lufs_data["lufs_integrated"] = float(i_match.group(1))
                    except (ValueError, AttributeError):
                        continue
                elif line.startswith('"input_tp"'):
                    try:
                        # Extract input_tp value
                        tp_match = re.search(r'"input_tp"\s*:\s*"([-\d.]+)"', line)
                        if tp_match:
                            lufs_data["true_peak"] = float(tp_match.group(1))
                    except (ValueError, AttributeError):
                        continue
                elif line.startswith('"input_lra"'):
                    try:
                        # Extract input_lra value
                        lra_match = re.search(r'"input_lra"\s*:\s*"([-\d.]+)"', line)
                        if lra_match:
                            lufs_data["lufs_range"] = float(lra_match.group(1))
                    except (ValueError, AttributeError):
                        continue

            return lufs_data

        except Exception as e:
            log.error(f"LUFS measurement failed: {e}")
            return {}

    def _measure_true_peak(self, audio_path: str) -> float:
        """Measure true peak using ffmpeg."""
        try:
            cmd = ["ffmpeg", "-i", audio_path, "-af", "volumedetect", "-f", "null", "-"]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse peak from volumedetect output
            for line in result.stderr.split("\n"):
                if "max_volume" in line:
                    try:
                        peak_match = line.split("max_volume:")[1].strip().split()[0]
                        return float(peak_match)
                    except (ValueError, IndexError):
                        continue

            return 0.0

        except Exception as e:
            log.error(f"True peak measurement failed: {e}")
            return 0.0

    def _validate_metrics(
        self, metrics: Dict[str, Any], expected_type: str
    ) -> Dict[str, Any]:
        """Validate audio metrics against targets."""
        if "error" in metrics:
            return {"valid": False, "error": metrics["error"], "can_normalize": False}

        lufs_integrated = metrics.get("lufs_integrated")
        true_peak = metrics.get("true_peak_db", 0)

        # Determine target LUFS based on type
        if expected_type == "voiceover":
            target_lufs = self.vo_lufs_target
            lufs_tolerance = 2.0  # ±2 LUFS tolerance for VO
        elif expected_type == "music":
            target_lufs = self.music_lufs_target
            lufs_tolerance = 3.0  # ±3 LUFS tolerance for music
        else:  # mixed
            target_lufs = self.vo_lufs_target
            lufs_tolerance = 2.0

        # Check LUFS
        lufs_valid = False
        if lufs_integrated is not None:
            lufs_diff = abs(lufs_integrated - target_lufs)
            lufs_valid = lufs_diff <= lufs_tolerance

        # Check true peak
        peak_valid = true_peak <= self.true_peak_max

        # Determine if normalization is possible
        can_normalize = lufs_integrated is not None and not peak_valid

        return {
            "valid": lufs_valid and peak_valid,
            "lufs_valid": lufs_valid,
            "peak_valid": peak_valid,
            "lufs_target": target_lufs,
            "lufs_actual": lufs_integrated,
            "lufs_tolerance": lufs_tolerance,
            "peak_target": self.true_peak_max,
            "peak_actual": true_peak,
            "can_normalize": can_normalize,
            "metrics": metrics,
        }

    def _normalize_audio(self, audio_path: str, expected_type: str) -> Optional[str]:
        """Attempt to normalize audio to meet targets."""
        try:
            # Determine target LUFS
            if expected_type == "voiceover":
                target_lufs = self.vo_lufs_target
            elif expected_type == "music":
                target_lufs = self.music_lufs_target
            else:
                target_lufs = self.vo_lufs_target

            # Create normalized output path
            output_path = os.path.join(
                self.temp_dir, f"normalized_{os.path.basename(audio_path)}"
            )

            # Apply loudness normalization
            cmd = [
                "ffmpeg",
                "-i",
                audio_path,
                "-af",
                f"loudnorm=I={target_lufs}:TP={self.true_peak_max}:LRA=11",
                "-y",
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, check=True)

            if os.path.exists(output_path):
                log.info(f"Audio normalized to {target_lufs} LUFS: {output_path}")
                return output_path
            else:
                log.error("Normalization failed - output file not created")
                return None

        except Exception as e:
            log.error(f"Audio normalization failed: {e}")
            return None

    def _detect_speech_segments(self, voiceover_path: str) -> list:
        """Detect speech segments using energy-based detection."""
        try:
            # Simple energy-based speech detection using ffmpeg
            temp_analysis = os.path.join(self.temp_dir, "speech_analysis.txt")

            cmd = [
                "ffmpeg",
                "-i",
                voiceover_path,
                "-af",
                "silencedetect=noise=-50dB:d=0.1",
                "-f",
                "null",
                "-",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse silence detection output to find speech segments
            speech_segments = []
            lines = result.stderr.split("\n")

            for i, line in enumerate(lines):
                if "silence_start" in line:
                    try:
                        start_time = float(line.split("silence_start:")[1].strip())
                        # Look for corresponding silence_end
                        for j in range(i + 1, len(lines)):
                            if "silence_end" in lines[j]:
                                end_time = float(
                                    lines[j].split("silence_end:")[1].strip()
                                )
                                speech_segments.append(
                                    {
                                        "start": start_time,
                                        "end": end_time,
                                        "duration": end_time - start_time,
                                    }
                                )
                                break
                    except (ValueError, IndexError):
                        continue

            return speech_segments

        except Exception as e:
            log.error(f"Speech detection failed: {e}")
            return []

    def _measure_ducking_effectiveness(
        self, mixed_audio_path: str, speech_segments: list
    ) -> Dict[str, Any]:
        """Measure ducking effectiveness by comparing levels in speech vs non-speech windows."""
        try:
            if not speech_segments:
                return {"error": "No speech segments provided"}

            # Create analysis segments
            analysis_segments = []

            # Add speech segments
            for seg in speech_segments:
                analysis_segments.append(
                    {"type": "speech", "start": seg["start"], "end": seg["end"]}
                )

            # Add non-speech segments (gaps between speech)
            for i in range(len(speech_segments) - 1):
                gap_start = speech_segments[i]["end"]
                gap_end = speech_segments[i + 1]["start"]
                if gap_end - gap_start > 0.5:  # Only significant gaps
                    analysis_segments.append(
                        {"type": "non_speech", "start": gap_start, "end": gap_end}
                    )

            # Measure RMS levels in each segment
            speech_levels = []
            non_speech_levels = []

            for seg in analysis_segments:
                segment_duration = seg["end"] - seg["start"]
                if segment_duration < 0.1:  # Skip very short segments
                    continue

                # Extract segment and measure RMS
                temp_segment = os.path.join(
                    self.temp_dir, f"segment_{seg['type']}_{seg['start']:.2f}.wav"
                )

                cmd = [
                    "ffmpeg",
                    "-i",
                    mixed_audio_path,
                    "-ss",
                    str(seg["start"]),
                    "-t",
                    str(seg["end"] - seg["start"]),
                    "-af",
                    "volumedetect",
                    "-f",
                    "null",
                    "-",
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, check=True)

                # Parse RMS from volumedetect
                rms_level = 0.0
                for line in result.stderr.split("\n"):
                    if "mean_volume" in line:
                        try:
                            rms_match = line.split("mean_volume:")[1].strip().split()[0]
                            rms_level = float(rms_match)
                            break
                        except (ValueError, IndexError):
                            continue

                if seg["type"] == "speech":
                    speech_levels.append(rms_level)
                else:
                    non_speech_levels.append(rms_level)

            # Calculate ducking effectiveness
            if speech_levels and non_speech_levels:
                avg_speech = sum(speech_levels) / len(speech_levels)
                avg_non_speech = sum(non_speech_levels) / len(non_speech_levels)
                ducking_difference = avg_non_speech - avg_speech
            else:
                ducking_difference = 0.0

            return {
                "speech_segments_analyzed": len(speech_levels),
                "non_speech_segments_analyzed": len(non_speech_levels),
                "avg_speech_level_db": (
                    sum(speech_levels) / len(speech_levels) if speech_levels else 0
                ),
                "avg_non_speech_level_db": (
                    sum(non_speech_levels) / len(non_speech_levels)
                    if non_speech_levels
                    else 0
                ),
                "ducking_difference_db": ducking_difference,
            }

        except Exception as e:
            log.error(f"Ducking effectiveness measurement failed: {e}")
            return {"error": f"Measurement failed: {str(e)}"}


def validate_ducking_for_acceptance(
    mixed_audio_path: str, voiceover_path: str
) -> Dict[str, Any]:
    """Validate ducking effectiveness for acceptance pipeline."""
    try:
        validator = AudioValidator()
        return validator.validate_ducking(mixed_audio_path, voiceover_path)
    except Exception as e:
        log.error(f"[audio-accept] Ducking validation error: {str(e)}")
        return {
            "valid": False,
            "error": f"Ducking validation error: {str(e)}",
            "error_type": "ducking_validation_error",
        }


def validate_audio_for_acceptance(
    audio_path: str, expected_type: str = "mixed"
) -> Dict[str, Any]:
    """Convenience function for acceptance pipeline."""
    validator = AudioValidator()
    return validator.validate_audio_for_acceptance(audio_path, expected_type)
