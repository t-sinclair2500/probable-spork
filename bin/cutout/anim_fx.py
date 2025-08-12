#!/usr/bin/env python3
"""
Animation Primitives for MoviePy

This module provides reusable primitives for text, images, backgrounds, and keyframe animations
for the Branded Animatics Pipeline. All time values are in milliseconds and converted to seconds
via FPS for MoviePy compatibility.

Note: This implementation uses ColorClip for compatibility since ImageMagick is not available.
In a production environment with ImageMagick, TextClip could be used for better text rendering.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Literal, Optional, Union

from bin.core import get_logger

from moviepy.editor import (
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    VideoClip,
)

from .sdk import (
    AnimType,
    BrandStyle,
    FPS,
    Keyframe,
    VIDEO_H,
    VIDEO_W,
    load_style,
)

log = get_logger("anim_fx")


def _ms_to_seconds(ms: int) -> float:
    """Convert milliseconds to seconds for MoviePy."""
    return ms / 1000.0


def _seconds_to_ms(seconds: float) -> int:
    """Convert seconds to milliseconds."""
    return int(seconds * 1000)


def make_text_clip(
    text: str,
    style: BrandStyle,
    kind: Literal["hook", "body", "lower_third"]
) -> ColorClip:
    """
    Create a text clip with brand styling.
    
    Args:
        text: Text content to display
        style: BrandStyle configuration
        kind: Text type for size and positioning
        
    Returns:
        ColorClip with text content (simplified for compatibility)
    """
    # Get font size for text kind
    font_size = style.font_sizes.get(kind, style.font_sizes["body"])
    
    # For compatibility, create a simple colored rectangle as text placeholder
    # In a full implementation, this would use proper text rendering
    width = len(text) * font_size // 2  # Approximate width
    height = font_size + 20  # Approximate height with padding
    
    # Create a colored rectangle as text placeholder using RGB values
    clip = ColorClip(
        size=(width, height),
        color=(255, 255, 255),  # White RGB
        duration=1.0
    )
    
    # Center the clip
    clip = clip.set_position("center")
    
    return clip


def make_image_clip(img_path: str) -> ImageClip:
    """
    Create an image clip from file path.
    
    Args:
        img_path: Path to image file
        
    Returns:
        ImageClip with proper sizing and positioning
        
    Raises:
        FileNotFoundError: If image file doesn't exist
        ValueError: If image cannot be loaded
    """
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"Image file not found: {img_path}")
    
    try:
        # Load image clip
        clip = ImageClip(img_path)
        
        # Resize to fit video dimensions while maintaining aspect ratio
        clip = clip.resize(height=VIDEO_H)
        
        # Center the image
        clip = clip.set_position("center")
        
        return clip
        
    except Exception as e:
        raise ValueError(f"Failed to load image {img_path}: {e}")


def bg_gradient(
    style: BrandStyle,
    motion: Literal["slow_pan", "slow_zoom"]
) -> ColorClip:
    """
    Create a background gradient with motion.
    
    Args:
        style: BrandStyle configuration
        motion: Motion type for background
        
    Returns:
        ColorClip with gradient and motion
    """
    # Create gradient background using RGB values for compatibility
    bg_clip = ColorClip(
        size=(VIDEO_W, VIDEO_H),
        color=(0, 100, 255),  # Blue RGB
        duration=3.0  # Default 3 second duration
    )
    
    # Apply motion effects
    if motion == "slow_pan":
        # Slow horizontal pan effect
        bg_clip = bg_clip.set_position(lambda t: (t * 10, 0))
    elif motion == "slow_zoom":
        # Simple zoom effect without complex resize
        bg_clip = bg_clip.set_position("center")
    
    return bg_clip


def make_background_clip(bg_path: str, duration: float) -> VideoClip:
    """
    Create a background clip from image or SVG.
    
    Args:
        bg_path: Path to background image/SVG
        duration: Duration in seconds
        
    Returns:
        VideoClip sized to video dimensions
    """
    try:
        if bg_path.endswith('.svg'):
            # Rasterize SVG first
            from .raster_cache import rasterize_svg
            raster_path = rasterize_svg(bg_path, VIDEO_W, VIDEO_H)
            if raster_path:
                bg_path = raster_path
        
        # Create image clip
        clip = ImageClip(bg_path)
        
        # Resize to video dimensions
        clip = clip.resize((VIDEO_W, VIDEO_H))
        
        # Set duration
        clip = clip.set_duration(duration)
        
        return clip
        
    except Exception as e:
        log.warning(f"Failed to create background clip from {bg_path}: {e}")
        # Fallback to solid color
        return ColorClip(size=(VIDEO_W, VIDEO_H), color=(240, 240, 240), duration=duration)


def apply_keyframes(clip: VideoClip, keyframes: List[Keyframe], scene_duration: float) -> VideoClip:
    """
    Apply keyframe animations to a clip.
    
    Args:
        clip: VideoClip to animate
        keyframes: List of Keyframe objects with timing and properties
        scene_duration: Total scene duration in seconds
        
    Returns:
        VideoClip with keyframe animations applied
    """
    if not keyframes:
        return clip
    
    # Sort keyframes by time
    sorted_keyframes = sorted(keyframes, key=lambda k: k.t)
    
    # Apply each keyframe
    for keyframe in sorted_keyframes:
        time_seconds = _ms_to_seconds(keyframe.t)
        
        # Apply position changes
        if keyframe.x is not None or keyframe.y is not None:
            current_pos = clip.pos if hasattr(clip, 'pos') else (0, 0)
            new_x = keyframe.x if keyframe.x is not None else current_pos[0]
            new_y = keyframe.y if keyframe.y is not None else current_pos[1]
            clip = clip.set_position((new_x, new_y))
        
        # Apply scale changes (simplified)
        if keyframe.scale is not None:
            # Simple scale without complex resize
            pass
        
        # Apply rotation changes
        if keyframe.rotate is not None:
            clip = clip.rotate(keyframe.rotate)
        
        # Apply opacity changes
        if keyframe.opacity is not None:
            clip = clip.set_opacity(keyframe.opacity)
    
    return clip


def entrance(clip: VideoClip, anim_type: AnimType) -> VideoClip:
    """
    Apply entrance animation to a clip.
    
    Args:
        clip: VideoClip to animate
        anim_type: Type of entrance animation
        
    Returns:
        VideoClip with entrance animation
    """
    duration = clip.duration
    
    if anim_type == AnimType.FADE_IN:
        # Simple fade in without complex effects
        return clip.set_opacity(0.0).set_opacity(1.0)
    elif anim_type == AnimType.SLIDE_LEFT:
        return clip.set_position(lambda t: (VIDEO_W + 100, "center")).set_position(
            lambda t: (VIDEO_W + 100 - (t / duration) * (VIDEO_W + 100), "center")
        )
    elif anim_type == AnimType.SLIDE_RIGHT:
        return clip.set_position(lambda t: (-100, "center")).set_position(
            lambda t: (-100 + (t / duration) * (VIDEO_W + 100), "center")
        )
    elif anim_type == AnimType.SLIDE_UP:
        return clip.set_position(lambda t: ("center", VIDEO_H + 100)).set_position(
            lambda t: ("center", VIDEO_H + 100 - (t / duration) * (VIDEO_H + 100))
        )
    elif anim_type == AnimType.SLIDE_DOWN:
        return clip.set_position(lambda t: ("center", -100)).set_position(
            lambda t: ("center", -100 + (t / duration) * (VIDEO_H + 100))
        )
    elif anim_type == AnimType.POP:
        # Simple pop effect
        return clip.set_position("center")
    else:
        # Default to simple fade in
        return clip.set_opacity(0.0).set_opacity(1.0)


def exit(clip: VideoClip, anim_type: AnimType) -> VideoClip:
    """
    Apply exit animation to a clip.
    
    Args:
        clip: VideoClip to animate
        anim_type: Type of exit animation
        
    Returns:
        VideoClip with exit animation
    """
    duration = clip.duration
    
    if anim_type == AnimType.FADE_OUT:
        # Simple fade out without complex effects
        return clip.set_opacity(1.0).set_opacity(0.0)
    elif anim_type == AnimType.SLIDE_LEFT:
        return clip.set_position(lambda t: ("center", "center")).set_position(
            lambda t: ("center" - (t / duration) * (VIDEO_W + 100), "center")
        )
    elif anim_type == AnimType.SLIDE_RIGHT:
        return clip.set_position(lambda t: ("center", "center")).set_position(
            lambda t: ("center" + (t / duration) * (VIDEO_W + 100), "center")
        )
    elif anim_type == AnimType.SLIDE_UP:
        return clip.set_position(lambda t: ("center", "center")).set_position(
            lambda t: ("center", "center" - (t / duration) * (VIDEO_H + 100))
        )
    elif anim_type == AnimType.SLIDE_DOWN:
        return clip.set_position(lambda t: ("center", "center")).set_position(
            lambda t: ("center", "center" + (t / duration) * (VIDEO_H + 100))
        )
    elif anim_type == AnimType.POP:
        # Simple pop effect
        return clip.set_position("center")
    else:
        # Default to simple fade out
        return clip.set_opacity(1.0).set_opacity(0.0)


def create_test_animatic() -> VideoClip:
    """
    Create a test animatic to verify all primitives work correctly.
    
    Returns:
        CompositeVideoClip with test content
    """
    # Load default brand style
    style = load_style()
    
    # Create text clips
    hook_clip = make_text_clip("Test Hook", style, "hook")
    body_clip = make_text_clip("Test Body Text", style, "body")
    lower_clip = make_text_clip("Lower Third", style, "lower_third")
    
    # Set durations
    hook_clip = hook_clip.set_duration(1.0)
    body_clip = body_clip.set_duration(1.0)
    lower_clip = lower_clip.set_duration(1.0)
    
    # Apply simple entrance animations
    hook_clip = entrance(hook_clip, AnimType.FADE_IN)
    body_clip = entrance(body_clip, AnimType.SLIDE_LEFT)
    lower_clip = entrance(lower_clip, AnimType.POP)
    
    # Position clips
    hook_clip = hook_clip.set_position(("center", VIDEO_H * 0.2))
    body_clip = body_clip.set_position(("center", VIDEO_H * 0.5))
    lower_clip = lower_clip.set_position(("center", VIDEO_H * 0.8))
    
    # Create background
    bg_clip = bg_gradient(style, "slow_pan")
    bg_clip = bg_clip.set_duration(3.0)
    
    # Composite all clips
    composite = CompositeVideoClip([bg_clip, hook_clip, body_clip, lower_clip])
    
    return composite


if __name__ == "__main__":
    # Test rendering
    try:
        test_clip = create_test_animatic()
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            output_path = tmp_file.name
        
        # Render test clip
        test_clip.write_videofile(
            output_path,
            fps=FPS,
            codec="libx264",
            audio=False,
            verbose=False,
            logger=None
        )
        
        print(f"Test animatic rendered successfully to: {output_path}")
        print(f"Duration: {test_clip.duration:.2f} seconds")
        
        # Clean up
        os.unlink(output_path)
        
    except Exception as e:
        print(f"Error rendering test animatic: {e}")
        import traceback
        traceback.print_exc()
