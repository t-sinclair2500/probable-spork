"""
Branded Animatics Pipeline - Cutout Package

This package provides the core SDK for creating branded animatics from SceneScripts.
"""

from .anim_fx import (
    apply_keyframes,
    bg_gradient,
    create_test_animatic,
    entrance,
    exit,
    make_image_clip,
    make_text_clip,
)
from .raster_cache import clear_cache, get_cache_stats, get_cached, rasterize_svg
from .sdk import (  # Constants; Enums; Path helpers; Models; Helper functions
    FPS,
    LINE_HEIGHT,
    MAX_WORDS_PER_CARD,
    SAFE_MARGINS_PX,
    VIDEO_H,
    VIDEO_W,
    AnimType,
    BrandStyle,
    Element,
    Keyframe,
    Paths,
    Scene,
    SceneScript,
    load_scene_script,
    load_style,
    save_scene_script,
    validate_scene_script,
)
from .svg_path_ops import (
    MotifVariantGenerator,
    SVGPathProcessor,
    create_path_processor,
    create_variant_generator,
    generate_motif_variants,
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
    "SVGPathProcessor",
    "MotifVariantGenerator",
    "create_path_processor",
    "create_variant_generator",
    "generate_motif_variants",
    "make_text_clip",
    "make_image_clip",
    "bg_gradient",
    "apply_keyframes",
    "entrance",
    "exit",
    "create_test_animatic",
]
