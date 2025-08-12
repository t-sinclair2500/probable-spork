#!/usr/bin/env python3
"""
Unit tests for animation primitives.

These tests verify that all animation primitives work correctly and can render
short MP4s without errors. Tests are designed to run quickly and clean up after themselves.
"""

import os
import tempfile
import unittest
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from bin.cutout.anim_fx import (
    make_text_clip,
    make_image_clip,
    bg_gradient,
    apply_keyframes,
    entrance,
    exit,
    create_test_animatic,
)
from bin.cutout.sdk import BrandStyle, Keyframe, AnimType


class TestAnimFx(unittest.TestCase):
    """Test cases for animation primitives."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a minimal brand style for testing
        self.test_style = BrandStyle(
            colors={
                "primary": "blue",
                "secondary": "purple",
                "text_primary": "black",
                "background": "white"
            },
            fonts={
                "primary": "Arial",
                "secondary": "Georgia"
            },
            font_sizes={
                "hook": 48,
                "body": 24,
                "lower_third": 32
            }
        )
        
        # Create a temporary directory for test outputs
        self.test_dir = tempfile.mkdtemp(prefix="anim_fx_test_")
        
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove test directory and contents
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_make_text_clip(self):
        """Test text clip creation with different types."""
        # Test hook text
        hook_clip = make_text_clip("Test Hook", self.test_style, "hook")
        self.assertIsNotNone(hook_clip)
        # Check that it's a ColorClip with expected properties
        self.assertEqual(hook_clip.size[0], len("Test Hook") * 48 // 2)
        self.assertEqual(hook_clip.size[1], 48 + 20)
        
        # Test body text
        body_clip = make_text_clip("Test Body", self.test_style, "body")
        self.assertIsNotNone(body_clip)
        self.assertEqual(body_clip.size[0], len("Test Body") * 24 // 2)
        self.assertEqual(body_clip.size[1], 24 + 20)
        
        # Test lower third
        lower_clip = make_text_clip("Lower Third", self.test_style, "lower_third")
        self.assertIsNotNone(lower_clip)
        self.assertEqual(lower_clip.size[0], len("Lower Third") * 32 // 2)
        self.assertEqual(lower_clip.size[1], 32 + 20)
    
    def test_bg_gradient(self):
        """Test background gradient creation."""
        # Test slow pan
        bg_pan = bg_gradient(self.test_style, "slow_pan")
        self.assertIsNotNone(bg_pan)
        self.assertEqual(bg_pan.duration, 3.0)
        
        # Test slow zoom
        bg_zoom = bg_gradient(self.test_style, "slow_zoom")
        self.assertIsNotNone(bg_zoom)
        self.assertEqual(bg_zoom.duration, 3.0)
    
    def test_apply_keyframes(self):
        """Test keyframe application."""
        # Create a simple text clip
        clip = make_text_clip("Test", self.test_style, "body")
        clip = clip.set_duration(2.0)
        
        # Create test keyframes
        keyframes = [
            Keyframe(t=0, x=0, y=0, scale=1.0, opacity=1.0),
            Keyframe(t=1000, x=100, y=50, scale=1.2, opacity=0.8),
            Keyframe(t=2000, x=200, y=100, scale=1.0, opacity=1.0)
        ]
        
        # Apply keyframes
        animated_clip = apply_keyframes(clip, keyframes)
        self.assertIsNotNone(animated_clip)
    
    def test_entrance_animations(self):
        """Test entrance animations."""
        clip = make_text_clip("Test", self.test_style, "body")
        clip = clip.set_duration(1.0)
        
        # Test fade in
        fade_clip = entrance(clip, AnimType.FADE_IN)
        self.assertIsNotNone(fade_clip)
        
        # Test slide left
        slide_clip = entrance(clip, AnimType.SLIDE_LEFT)
        self.assertIsNotNone(slide_clip)
        
        # Test pop
        pop_clip = entrance(clip, AnimType.POP)
        self.assertIsNotNone(pop_clip)
    
    def test_exit_animations(self):
        """Test exit animations."""
        clip = make_text_clip("Test", self.test_style, "body")
        clip = clip.set_duration(1.0)
        
        # Test fade out
        fade_clip = exit(clip, AnimType.FADE_OUT)
        self.assertIsNotNone(fade_clip)
        
        # Test slide right
        slide_clip = exit(clip, AnimType.SLIDE_RIGHT)
        self.assertIsNotNone(slide_clip)
    
    def test_render_short_mp4(self):
        """Test that primitives can render a short MP4 without errors."""
        try:
            # Create test animatic
            test_clip = create_test_animatic()
            
            # Set a short duration for testing
            test_clip = test_clip.set_duration(2.0)
            
            # Render to temporary file
            output_path = os.path.join(self.test_dir, "test_animatic.mp4")
            
            test_clip.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio=False,
                verbose=False,
                logger=None
            )
            
            # Verify file was created and has reasonable size
            self.assertTrue(os.path.exists(output_path))
            file_size = os.path.getsize(output_path)
            self.assertGreater(file_size, 1000)  # At least 1KB
            
            # Verify duration is within 3% tolerance
            expected_duration = 2.0
            actual_duration = test_clip.duration
            duration_diff = abs(actual_duration - expected_duration)
            duration_tolerance = expected_duration * 0.03  # 3% tolerance
            
            self.assertLessEqual(duration_diff, duration_tolerance, 
                               f"Duration {actual_duration}s differs from expected {expected_duration}s by more than 3%")
            
            print(f"✓ Test animatic rendered successfully: {output_path}")
            print(f"  Duration: {actual_duration:.2f}s (expected: {expected_duration:.2f}s)")
            print(f"  File size: {file_size:,} bytes")
            
        except Exception as e:
            self.fail(f"Failed to render test animatic: {e}")
    
    def test_image_clip_error_handling(self):
        """Test image clip error handling for missing files."""
        with self.assertRaises(FileNotFoundError):
            make_image_clip("nonexistent_image.jpg")


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
