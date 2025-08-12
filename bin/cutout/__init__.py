"""
Branded Animatics Pipeline - Cutout Package

This package provides the core SDK for creating branded animatics from SceneScripts.
"""

from .sdk import (
    # Constants
    VIDEO_W,
    VIDEO_H,
    FPS,
    SAFE_MARGINS_PX,
    MAX_WORDS_PER_CARD,
    LINE_HEIGHT,
    
    # Enums
    AnimType,
    
    # Path helpers
    Paths,
    
    # Models
    BrandStyle,
    Keyframe,
    Element,
    Scene,
    SceneScript,
    
    # Helper functions
    load_style,
    validate_scene_script,
    save_scene_script,
    load_scene_script,
)

from .raster_cache import (
    rasterize_svg,
    get_cached,
    clear_cache,
    get_cache_stats,
)

from .anim_fx import (
    make_text_clip,
    make_image_clip,
    bg_gradient,
    apply_keyframes,
    entrance,
    exit,
    create_test_animatic,
)

__version__ = "0.1.0"
__all__ = [
    "VIDEO_W",
    "VIDEO_H", 
    "FPS",
    "SAFE_MARGINS_PX",
    "MAX_WORDS_PER_CARD",
    "LINE_HEIGHT",
    "AnimType",
    "Paths",
    "BrandStyle",
    "Keyframe",
    "Element",
    "Scene",
    "SceneScript",
    "load_style",
    "validate_scene_script",
    "save_scene_script",
    "load_scene_script",
    "rasterize_svg",
    "get_cached",
    "clear_cache",
    "get_cache_stats",
    "make_text_clip",
    "make_image_clip",
    "bg_gradient",
    "apply_keyframes",
    "entrance",
    "exit",
    "create_test_animatic",
]
