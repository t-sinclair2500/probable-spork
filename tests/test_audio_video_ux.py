#!/usr/bin/env python3
"""
Test Audio/Video UX Improvements

Verifies production-grade assembly and thumbnail generation:
1. Tolerant VO discovery for slug (exact → tokenized → contains; newest wins)
2. Thumbnail CLI supports --slug and sanitizes ellipsis to ASCII ...
3. Platform-aware encoder: h264_videotoolbox on macOS, fallback to libx264 elsewhere
"""

import json
import os

# Ensure repo root on path
import sys
import tempfile
from unittest.mock import patch

import pytest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.utils.ffmpeg import _default_codecs, encode_with_fallback
from bin.utils.media import (
    find_voiceover_for_slug,
    resolve_metadata_for_slug,
    sanitize_text_for_pillow,
    write_media_inspector,
)


class TestVoiceoverDiscovery:
    """Test tolerant VO discovery for slug."""

    def test_exact_match_priority(self, tmp_path):
        """Test that exact stem match has highest priority."""
        # Create test voiceover directory
        vo_dir = tmp_path / "voiceovers"
        vo_dir.mkdir()

        # Create files with different match levels
        exact_match = vo_dir / "test-slug.mp3"
        exact_match.write_text("exact")

        prefix_match = vo_dir / "2024-01-01_test-slug.wav"
        prefix_match.write_text("prefix")

        contains_match = vo_dir / "my-test-slug-v2.m4a"
        contains_match.write_text("contains")

        # Find voiceover for slug
        result = find_voiceover_for_slug("test-slug", search_dirs=[str(vo_dir)])

        # Should return exact match
        assert result is not None
        assert result.name == "test-slug.mp3"

    def test_tokenized_match_priority(self, tmp_path):
        """Test that tokenized matches (prefix/suffix) have second priority."""
        # Create test voiceover directory
        vo_dir = tmp_path / "voiceovers"
        vo_dir.mkdir()

        # Create files with different match levels (no exact match)
        prefix_match = vo_dir / "2024-01-01_test-slug.wav"
        prefix_match.write_text("prefix")

        suffix_match = vo_dir / "test-slug_v2.m4a"
        suffix_match.write_text("suffix")

        contains_match = vo_dir / "my-test-slug-v2.mp3"
        contains_match.write_text("contains")

        # Find voiceover for slug
        result = find_voiceover_for_slug("test-slug", search_dirs=[str(vo_dir)])

        # Should return tokenized match (prefix or suffix)
        assert result is not None
        assert "test-slug" in result.name
        # Should prefer shorter stem distance
        if "2024-01-01_test-slug" in result.name:
            assert result.name == "2024-01-01_test-slug.wav"
        else:
            assert result.name == "test-slug_v2.m4a"

    def test_contains_match_fallback(self, tmp_path):
        """Test that contains match is used as fallback."""
        # Create test voiceover directory
        vo_dir = tmp_path / "voiceovers"
        vo_dir.mkdir()

        # Create only contains match
        contains_match = vo_dir / "my-test-slug-v2.mp3"
        contains_match.write_text("contains")

        # Find voiceover for slug
        result = find_voiceover_for_slug("test-slug", search_dirs=[str(vo_dir)])

        # Should return contains match
        assert result is not None
        assert result.name == "my-test-slug-v2.mp3"

    def test_newest_wins_tiebreak(self, tmp_path):
        """Test that newest file wins when scores are tied."""
        # Create test voiceover directory
        vo_dir = tmp_path / "voiceovers"
        vo_dir.mkdir()

        # Create two files with same score but different mtimes
        old_file = vo_dir / "test-slug_v1.mp3"
        old_file.write_text("old")

        new_file = vo_dir / "test-slug_v2.mp3"
        new_file.write_text("new")

        # Set different mtimes
        old_time = 1000000000  # 2001-09-09
        new_time = 1700000000  # 2023-11-14

        os.utime(old_file, (old_time, old_time))
        os.utime(new_file, (new_time, new_time))

        # Find voiceover for slug
        result = find_voiceover_for_slug("test-slug", search_dirs=[str(vo_dir)])

        # Should return newest file
        assert result is not None
        assert result.name == "test-slug_v2.mp3"

    def test_no_match_returns_none(self, tmp_path):
        """Test that None is returned when no match found."""
        # Create test voiceover directory
        vo_dir = tmp_path / "voiceovers"
        vo_dir.mkdir()

        # Create file that doesn't match
        no_match = vo_dir / "completely-different.mp3"
        no_match.write_text("different")

        # Find voiceover for slug
        result = find_voiceover_for_slug("test-slug", search_dirs=[str(vo_dir)])

        # Should return None
        assert result is None

    def test_ignores_non_audio_files(self, tmp_path):
        """Test that non-audio files are ignored."""
        # Create test voiceover directory
        vo_dir = tmp_path / "voiceovers"
        vo_dir.mkdir()

        # Create non-audio file with matching name
        non_audio = vo_dir / "test-slug.txt"
        non_audio.write_text("text file")

        # Find voiceover for slug
        result = find_voiceover_for_slug("test-slug", search_dirs=[str(vo_dir)])

        # Should return None (no audio files)
        assert result is None


class TestThumbnailSlugSupport:
    """Test thumbnail CLI --slug support and text sanitization."""

    def test_resolve_metadata_for_slug_scripts_priority(self, tmp_path):
        """Test that scripts/<slug>.metadata.json has highest priority."""
        # Create test directories
        scripts_dir = tmp_path / "scripts"
        videos_dir = tmp_path / "videos"
        scripts_dir.mkdir()
        videos_dir.mkdir()

        # Create metadata files in different locations
        scripts_meta = scripts_dir / "test-slug.metadata.json"
        scripts_meta.write_text('{"title": "Scripts Title"}')

        videos_meta = videos_dir / "test-slug.metadata.json"
        videos_meta.write_text('{"title": "Videos Title"}')

        # Change to tmp_path directory and test
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = resolve_metadata_for_slug("test-slug")

            # Should return scripts metadata
            assert result is not None
            assert "scripts" in str(result)
        finally:
            os.chdir(original_cwd)

    def test_resolve_metadata_for_slug_videos_fallback(self, tmp_path):
        """Test that videos metadata is used as fallback."""
        # Create test directories
        videos_dir = tmp_path / "videos"
        videos_dir.mkdir()

        # Create only videos metadata
        videos_meta = videos_dir / "test-slug.metadata.json"
        videos_meta.write_text('{"title": "Videos Title"}')

        # Change to tmp_path directory and test
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = resolve_metadata_for_slug("test-slug")

            # Should return videos metadata
            assert result is not None
            assert "videos" in str(result)
        finally:
            os.chdir(original_cwd)

    def test_resolve_metadata_for_slug_none_when_missing(self, tmp_path):
        """Test that None is returned when no metadata found."""
        # Create test directories (empty)
        scripts_dir = tmp_path / "scripts"
        videos_dir = tmp_path / "videos"
        scripts_dir.mkdir()
        videos_dir.mkdir()

        # Change to tmp_path directory and test
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = resolve_metadata_for_slug("test-slug")

            # Should return None
            assert result is None
        finally:
            os.chdir(original_cwd)

    def test_sanitize_text_for_pillow_ellipsis_replacement(self):
        """Test that Unicode ellipsis is replaced with ASCII."""
        # Test Unicode ellipsis replacement
        text_with_unicode = "This is a long title with ellipsis…"
        sanitized = sanitize_text_for_pillow(text_with_unicode)

        assert sanitized == "This is a long title with ellipsis..."
        assert "…" not in sanitized
        assert "..." in sanitized

    def test_sanitize_text_for_pillow_none_handling(self):
        """Test that None input is handled gracefully."""
        # Test None input
        sanitized = sanitize_text_for_pillow(None)

        assert sanitized == ""

    def test_sanitize_text_for_pillow_no_ellipsis(self):
        """Test that text without ellipsis is unchanged."""
        # Test text without ellipsis
        normal_text = "This is a normal title"
        sanitized = sanitize_text_for_pillow(normal_text)

        assert sanitized == normal_text

    def test_sanitize_text_for_pillow_multiple_ellipsis(self):
        """Test that multiple ellipsis are all replaced."""
        # Test multiple ellipsis
        text_with_multiple = "First… Second… Third…"
        sanitized = sanitize_text_for_pillow(text_with_multiple)

        assert sanitized == "First... Second... Third..."
        assert text_with_multiple.count("…") == 3
        assert sanitized.count("...") == 3


class TestPlatformAwareEncoding:
    """Test platform-aware encoder selection."""

    def test_default_codecs_macos(self):
        """Test that macOS prefers VideoToolbox."""
        with patch("platform.system") as mock_system:
            mock_system.return_value = "Darwin"
            codecs = _default_codecs()

        assert codecs == ["h264_videotoolbox", "libx264"]
        assert codecs[0] == "h264_videotoolbox"  # VideoToolbox first

    def test_default_codecs_other_platforms(self):
        """Test that other platforms use libx264."""
        with patch("platform.system") as mock_system:
            mock_system.return_value = "Linux"
            codecs = _default_codecs()

        assert codecs == ["libx264"]

    def test_default_codecs_windows(self):
        """Test that Windows uses libx264."""
        with patch("platform.system") as mock_system:
            mock_system.return_value = "Windows"
            codecs = _default_codecs()

        assert codecs == ["libx264"]

    @patch("bin.utils.ffmpeg.run_streamed")
    def test_encode_with_fallback_success_first_try(self, mock_run):
        """Test that encoding succeeds on first codec attempt."""
        # Mock successful encoding
        mock_run.return_value = None

        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as output_file:
            output_path = output_file.name

        try:
            # Test encoding
            encode_with_fallback(
                input_path=input_path, output_path=output_path, codecs=["libx264"]
            )

            # Should have called run_streamed once
            mock_run.assert_called_once()

        finally:
            # Clean up
            os.unlink(input_path)
            os.unlink(output_path)

    @patch("bin.utils.ffmpeg.run_streamed")
    def test_encode_with_fallback_fallback_behavior(self, mock_run):
        """Test that encoding falls back to second codec on failure."""
        # Mock first codec failure, second success
        mock_run.side_effect = [Exception("First codec failed"), None]

        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as output_file:
            output_path = output_file.name

        try:
            # Test encoding with fallback
            encode_with_fallback(
                input_path=input_path,
                output_path=output_path,
                codecs=["h264_videotoolbox", "libx264"],
            )

            # Should have called run_streamed twice
            assert mock_run.call_count == 2

        finally:
            # Clean up
            os.unlink(input_path)
            os.unlink(output_path)

    @patch("bin.utils.ffmpeg.run_streamed")
    def test_encode_with_fallback_all_fail(self, mock_run):
        """Test that encoding raises exception when all codecs fail."""
        # Mock all codecs failing
        mock_run.side_effect = [
            Exception("Codec 1 failed"),
            Exception("Codec 2 failed"),
        ]

        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as output_file:
            output_path = output_file.name

        try:
            # Test encoding with all failures
            with pytest.raises(RuntimeError) as exc_info:
                encode_with_fallback(
                    input_path=input_path,
                    output_path=output_path,
                    codecs=["h264_videotoolbox", "libx264"],
                )

            # Should mention all codec attempts failed
            assert "All codec attempts failed" in str(exc_info.value)

        finally:
            # Clean up
            os.unlink(input_path)
            os.unlink(output_path)


class TestMediaInspector:
    """Test media inspector functionality."""

    @patch("bin.utils.media.ffprobe_json")
    def test_write_media_inspector_creates_report(self, mock_ffprobe):
        """Test that media inspector creates proper report."""
        # Mock ffprobe response
        mock_ffprobe.return_value = {
            "streams": [{"codec_type": "video"}],
            "format": {"duration": "10.0"},
        }

        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as output_file:
            output_path = Path(output_file.name)

        try:
            # Test media inspector
            report_path = write_media_inspector(
                slug="test-slug",
                output_path=output_path,
                encode_args={"crf": "19", "a_bitrate": "320k"},
            )

            # Should create report file
            assert report_path.exists()

            # Should contain expected data
            report_data = json.loads(report_path.read_text())
            assert report_data["slug"] == "test-slug"
            assert report_data["output"] == str(output_path)
            assert "ffprobe" in report_data
            assert "encode_args" in report_data
            assert report_data["encode_args"]["crf"] == "19"

        finally:
            # Clean up
            os.unlink(output_path)
            if report_path.exists():
                os.unlink(report_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
