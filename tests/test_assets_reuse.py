"""
Test asset fetching in REUSE mode.

These tests verify that:
- No network calls are made
- Fixtures are properly used
- Synthetic assets are generated when needed
- License files are created correctly
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from bin.fetch_assets import (
    copy_fixtures,
    create_fixture_license,
    generate_synthetic_assets,
    main_reuse_mode,
)


@pytest.mark.reuse
class TestAssetReuse:
    """Test asset reuse functionality"""
    
    def test_copy_fixtures_basic(self, temp_fixtures_dir):
        """Test basic fixture copying"""
        # Create some test fixtures
        generic_dir = os.path.join(temp_fixtures_dir, "_generic")
        test_files = [
            "test1.jpg", "test2.png", "test3.mp4", 
            "license.json", "sources_used.txt"  # Should be skipped
        ]
        
        for filename in test_files:
            filepath = os.path.join(generic_dir, filename)
            with open(filepath, 'w') as f:
                f.write(f"test content for {filename}")
        
        # Test copying
        with tempfile.TemporaryDirectory() as dest_dir:
            copied = copy_fixtures(generic_dir, dest_dir, 5)
            
            # Should copy 3 media files, skip 2 metadata files
            assert copied == 3
            
            # Verify files were copied
            dest_files = os.listdir(dest_dir)
            assert "test1.jpg" in dest_files
            assert "test2.png" in dest_files
            assert "test3.mp4" in dest_files
            assert "license.json" not in dest_files
            assert "sources_used.txt" not in dest_files
    
    def test_copy_fixtures_max_count(self, temp_fixtures_dir):
        """Test max count enforcement in fixture copying"""
        generic_dir = os.path.join(temp_fixtures_dir, "_generic")
        
        # Create 5 test files
        for i in range(5):
            filepath = os.path.join(generic_dir, f"test{i}.jpg")
            with open(filepath, 'w') as f:
                f.write(f"test content {i}")
        
        with tempfile.TemporaryDirectory() as dest_dir:
            # Request only 3 files
            copied = copy_fixtures(generic_dir, dest_dir, 3)
            
            assert copied == 3
            assert len(os.listdir(dest_dir)) == 3
    
    def test_generate_synthetic_assets(self):
        """Test synthetic asset generation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            count = 3
            slug = "test-topic"
            
            generated = generate_synthetic_assets(temp_dir, count, slug)
            
            assert generated == count
            
            # Check files were created
            files = os.listdir(temp_dir)
            assert len(files) == count
            
            # Check filenames
            for i in range(count):
                expected_name = f"synthetic_{slug}_{i+1:03d}.jpg"
                assert expected_name in files
                
                # Verify file exists and has content
                filepath = os.path.join(temp_dir, expected_name)
                assert os.path.getsize(filepath) > 1000  # Should be decent size image
    
    def test_create_fixture_license(self):
        """Test fixture license creation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test asset files
            test_files = ["test1.jpg", "synthetic_test_001.jpg", "test2.mp4"]
            for filename in test_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    f.write("test content")
            
            slug = "test-slug"
            asset_count = len(test_files)
            
            create_fixture_license(temp_dir, slug, asset_count)
            
            # Check license.json was created
            license_path = os.path.join(temp_dir, "license.json")
            assert os.path.exists(license_path)
            
            with open(license_path, 'r') as f:
                license_data = json.load(f)
            
            assert license_data["source"] == "fixtures"
            assert license_data["topic_slug"] == slug
            assert license_data["asset_count"] == asset_count
            assert license_data["mode"] == "reuse"
            assert len(license_data["items"]) == asset_count
            
            # Check sources_used.txt was created
            sources_path = os.path.join(temp_dir, "sources_used.txt")
            assert os.path.exists(sources_path)
    
    def test_main_reuse_mode_no_script(self, reuse_mode_env, test_config):
        """Test reuse mode when no script is available"""
        # This should exit gracefully without error
        result = main_reuse_mode(test_config, reuse_mode_env)
        # Should return None (no script found)
        assert result is None
    
    @pytest.mark.skip(reason="Requires more complex test setup with actual script files")
    def test_main_reuse_mode_with_fixtures(self, reuse_mode_env, test_config):
        """Test full reuse mode with fixtures"""
        # This test would require setting up:
        # - A test script file
        # - Fixture directories
        # - Mocking the script discovery
        pass
    
    def test_no_network_calls_in_reuse_mode(self, reuse_mode_env):
        """Test that network calls are blocked in reuse mode"""
        import requests
        
        # This should raise RuntimeError due to monkeypatch
        with pytest.raises(RuntimeError, match="Network request attempted in REUSE mode"):
            requests.get("https://example.com")
        
        with pytest.raises(RuntimeError, match="Network request attempted in REUSE mode"):
            requests.post("https://example.com")


@pytest.mark.reuse
def test_fixture_directory_structure(temp_fixtures_dir):
    """Test that fixture directory structure is correct"""
    # Generic fixtures directory should exist
    generic_dir = os.path.join(temp_fixtures_dir, "_generic")
    assert os.path.exists(generic_dir)
    assert os.path.isdir(generic_dir)


@pytest.mark.reuse 
def test_asset_file_extensions():
    """Test that only valid asset file extensions are processed"""
    from bin.fetch_assets import copy_fixtures
    
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dest_dir:
        # Create files with various extensions
        test_files = [
            "image.jpg", "image.jpeg", "image.png", "image.gif",  # Valid images
            "video.mp4", "video.mov", "video.avi",  # Valid videos
            "document.txt", "data.json", "readme.md",  # Invalid
            "license.json", "sources_used.txt"  # Metadata (should skip)
        ]
        
        for filename in test_files:
            filepath = os.path.join(src_dir, filename)
            with open(filepath, 'w') as f:
                f.write("test content")
        
        copied = copy_fixtures(src_dir, dest_dir, 20)
        
        # Should copy 7 valid media files, skip 5 others
        assert copied == 7
        
        dest_files = set(os.listdir(dest_dir))
        # Check valid files were copied
        assert "image.jpg" in dest_files
        assert "video.mp4" in dest_files
        
        # Check invalid files were skipped
        assert "document.txt" not in dest_files
        assert "license.json" not in dest_files
