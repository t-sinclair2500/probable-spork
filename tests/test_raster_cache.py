"""
Unit tests for SVG rasterizer and asset cache.

Tests cache hits/misses, fallback methods, and error handling.
"""

import os
import tempfile
import time
from unittest.mock import patch

import pytest
from pathlib import Path

from bin.cutout.raster_cache import (
    CACHE_DIR,
    _get_cache_key,
    _get_cached_path,
    clear_cache,
    get_cache_stats,
    get_cached,
    rasterize_svg,
)


class TestCacheKeyGeneration:
    """Test cache key generation and path handling."""

    def test_cache_key_uniqueness(self):
        """Test that different inputs generate different cache keys."""
        key1 = _get_cache_key("test.svg", 100, 100)
        key2 = _get_cache_key("test.svg", 200, 100)
        key3 = _get_cache_key("test.svg", 100, 200)

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_cache_key_consistency(self):
        """Test that same inputs generate same cache keys."""
        key1 = _get_cache_key("test.svg", 100, 100)
        key2 = _get_cache_key("test.svg", 100, 100)

        assert key1 == key2

    def test_cache_path_generation(self):
        """Test cache path generation."""
        cache_key = "abc123"
        expected_path = CACHE_DIR / "abc123.png"

        assert _get_cached_path(cache_key) == expected_path


class TestCacheOperations:
    """Test cache hit/miss operations."""

    def setup_method(self):
        """Set up test environment."""
        # Ensure cache directory exists
        CACHE_DIR.mkdir(exist_ok=True)

        # Create a temporary SVG file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_svg = Path(self.temp_dir) / "test.svg"
        self.test_svg.write_text('<svg><rect width="100" height="100"/></svg>')

    def teardown_method(self):
        """Clean up test environment."""
        # Clear cache
        clear_cache()

        # Remove temporary files
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_cached_miss(self):
        """Test cache miss behavior."""
        result = get_cached(str(self.test_svg), 100, 100)
        assert result is None

    def test_get_cached_hit(self):
        """Test cache hit behavior."""
        # First call should miss
        result1 = get_cached(str(self.test_svg), 100, 100)
        assert result1 is None

        # Create a fake cached file
        cache_key = _get_cache_key(str(self.test_svg), 100, 100)
        cached_path = _get_cached_path(cache_key)
        cached_path.write_bytes(b"fake_png_data")

        # Second call should hit
        result2 = get_cached(str(self.test_svg), 100, 100)
        assert result2 == str(cached_path)

    def test_cache_stats_empty(self):
        """Test cache statistics when empty."""
        stats = get_cache_stats()
        assert stats["total_files"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["cache_dir"] == str(CACHE_DIR)

    def test_cache_stats_with_files(self):
        """Test cache statistics with files."""
        # Create some fake cached files
        cache_key = _get_cache_key(str(self.test_svg), 100, 100)
        cached_path = _get_cached_path(cache_key)
        cached_path.write_bytes(b"fake_png_data")

        stats = get_cache_stats()
        assert stats["total_files"] == 1
        assert stats["total_size_bytes"] > 0
        assert stats["cache_dir"] == str(CACHE_DIR)


class TestRasterizationMethods:
    """Test different rasterization methods."""

    def setup_method(self):
        """Set up test environment."""
        # Ensure cache directory exists
        CACHE_DIR.mkdir(exist_ok=True)

        # Create a temporary SVG file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_svg = Path(self.temp_dir) / "test.svg"
        self.test_svg.write_text('<svg><rect width="100" height="100"/></svg>')

    def teardown_method(self):
        """Clean up test environment."""
        # Clear cache
        clear_cache()

        # Remove temporary files
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("bin.cutout.raster_cache._rasterize_with_cairosvg")
    def test_rasterize_svg_cairosvg_success(self, mock_cairosvg):
        """Test successful rasterization with cairosvg."""
        mock_cairosvg.return_value = True

        result = rasterize_svg(str(self.test_svg), 100, 100)

        # Should call cairosvg method
        mock_cairosvg.assert_called_once()

        # Should return a path
        assert isinstance(result, str)
        assert result.endswith(".png")

        # Should be in cache directory
        assert "render_cache" in result

    @patch("bin.cutout.raster_cache._rasterize_with_cairosvg")
    @patch("bin.cutout.raster_cache._rasterize_with_rsvg")
    def test_rasterize_svg_fallback_to_rsvg(self, mock_rsvg, mock_cairosvg):
        """Test fallback from cairosvg to rsvg-convert."""
        mock_cairosvg.return_value = False
        mock_rsvg.return_value = True

        result = rasterize_svg(str(self.test_svg), 100, 100)

        # Should try cairosvg first
        mock_cairosvg.assert_called_once()

        # Should fall back to rsvg
        mock_rsvg.assert_called_once()

        # Should return a path
        assert isinstance(result, str)
        assert result.endswith(".png")

    @patch("bin.cutout.raster_cache._rasterize_with_cairosvg")
    @patch("bin.cutout.raster_cache._rasterize_with_rsvg")
    @patch("bin.cutout.raster_cache._rasterize_with_pillow")
    def test_rasterize_svg_fallback_to_pillow(
        self, mock_pillow, mock_rsvg, mock_cairosvg
    ):
        """Test fallback to Pillow when other methods fail."""
        mock_cairosvg.return_value = False
        mock_rsvg.return_value = False
        mock_pillow.return_value = True

        result = rasterize_svg(str(self.test_svg), 100, 100)

        # Should try all methods
        mock_cairosvg.assert_called_once()
        mock_rsvg.assert_called_once()
        mock_pillow.assert_called_once()

        # Should return a path
        assert isinstance(result, str)
        assert result.endswith(".png")

    @patch("bin.cutout.raster_cache._rasterize_with_cairosvg")
    @patch("bin.cutout.raster_cache._rasterize_with_rsvg")
    @patch("bin.cutout.raster_cache._rasterize_with_pillow")
    def test_rasterize_svg_all_methods_fail(
        self, mock_pillow, mock_rsvg, mock_cairosvg
    ):
        """Test error when all rasterization methods fail."""
        mock_cairosvg.return_value = False
        mock_rsvg.return_value = False
        mock_pillow.return_value = False

        with pytest.raises(RuntimeError, match="All rasterization methods failed"):
            rasterize_svg(str(self.test_svg), 100, 100)

    def test_rasterize_svg_file_not_found(self):
        """Test error when SVG file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            rasterize_svg("nonexistent.svg", 100, 100)


class TestCacheReuse:
    """Test that subsequent calls hit the cache."""

    def setup_method(self):
        """Set up test environment."""
        # Ensure cache directory exists
        CACHE_DIR.mkdir(exist_ok=True)

        # Create a temporary SVG file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_svg = Path(self.temp_dir) / "test.svg"
        self.test_svg.write_text('<svg><rect width="100" height="100"/></svg>')

    def teardown_method(self):
        """Clean up test environment."""
        # Clear cache
        clear_cache()

        # Remove temporary files
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_reuse(self):
        """Test that second call hits cache."""
        # Clear cache before test
        clear_cache()

        # Create a simple test SVG
        test_svg_content = '<svg width="100" height="100"><rect width="100" height="100" fill="red"/></svg>'
        test_svg_path = Path(self.temp_dir) / "test_cache.svg"
        test_svg_path.write_text(test_svg_content)

        # First call should rasterize and create cache
        result1 = rasterize_svg(str(test_svg_path), 100, 100)
        assert Path(result1).exists()

        # Get cache stats to verify file was created
        stats_before = get_cache_stats()
        assert stats_before["total_files"] == 1

        # Second call should hit cache (same result)
        result2 = rasterize_svg(str(test_svg_path), 100, 100)

        # Both should return same path
        assert result1 == result2

        # Cache stats should be the same (no new files)
        stats_after = get_cache_stats()
        assert stats_after["total_files"] == 1

    @patch("bin.cutout.raster_cache._rasterize_with_cairosvg")
    def test_cache_invalidation_by_mtime(self, mock_cairosvg):
        """Test that cache is invalidated when file modification time changes."""
        mock_cairosvg.return_value = True

        # First call
        result1 = rasterize_svg(str(self.test_svg), 100, 100)
        assert mock_cairosvg.call_count == 1

        # Modify file modification time
        time.sleep(1.1)  # Ensure mtime changes
        os.utime(self.test_svg, None)

        # Second call should re-rasterize due to mtime change
        result2 = rasterize_svg(str(self.test_svg), 100, 100)
        assert mock_cairosvg.call_count == 2

        # Should return different paths (different cache keys)
        assert result1 != result2


class TestCacheManagement:
    """Test cache management functions."""

    def setup_method(self):
        """Set up test environment."""
        # Ensure cache directory exists
        CACHE_DIR.mkdir(exist_ok=True)

    def teardown_method(self):
        """Clean up test environment."""
        # Clear cache
        clear_cache()

    def test_clear_cache(self):
        """Test cache clearing functionality."""
        # Create some fake cached files
        fake_cache_file = CACHE_DIR / "fake.png"
        fake_cache_file.write_bytes(b"fake_data")

        # Verify file exists
        assert fake_cache_file.exists()

        # Clear cache
        clear_cache()

        # Verify file is gone
        assert not fake_cache_file.exists()

    def test_cache_directory_creation(self):
        """Test that cache directory is created if it doesn't exist."""
        # Remove cache directory
        import shutil

        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)

        # Force recreation by calling a function that uses the cache directory
        from bin.cutout.raster_cache import get_cache_stats

        stats = get_cache_stats()

        # Directory should now exist
        assert CACHE_DIR.exists()
        assert stats["cache_dir"] == str(CACHE_DIR)
