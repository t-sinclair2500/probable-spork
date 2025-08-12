#!/usr/bin/env python3
"""
Core SDK for Branded Animatics Pipeline

This module provides the single source of truth for types, constants, paths, and naming.
All animatics modules must import from this file to avoid drift.
"""

import json
import os
import pathlib
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


# ============================================================================
# CONSTANTS
# ============================================================================

VIDEO_W = 1280
VIDEO_H = 720
FPS = 30
SAFE_MARGINS_PX = 64
MAX_WORDS_PER_CARD = 12
LINE_HEIGHT = 1.1

# Animation types for keyframes and transitions
class AnimType(str, Enum):
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"
    POP = "pop"
    SLOW_ZOOM = "slow_zoom"
    SLOW_PAN = "slow_pan"


# ============================================================================
# PATH HELPERS
# ============================================================================

class Paths:
    """Centralized path management for animatics pipeline."""
    
    @staticmethod
    def slug_root(slug: str) -> Path:
        """Get the root directory for a specific slug."""
        return Path("scripts") / slug
    
    @staticmethod
    def anim_dir(slug: str) -> Path:
        """Get the animatics directory for a specific slug."""
        return Path("assets") / f"{slug}_animatics"
    
    @staticmethod
    def scene_script(slug: str) -> Path:
        """Get the SceneScript file path for a specific slug."""
        return Path("scenescripts") / f"{slug}.json"
    
    @staticmethod
    def brand_style() -> Path:
        """Get the brand style configuration path."""
        return Path("assets/brand/style.yaml")


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class BrandStyle(BaseModel):
    """Brand style configuration for consistent visual identity."""
    
    colors: Dict[str, str] = Field(..., description="Brand color palette")
    fonts: Dict[str, str] = Field(..., description="Font family mappings")
    font_sizes: Dict[str, int] = Field(..., description="Font size mappings")
    safe_margins_px: int = Field(default=SAFE_MARGINS_PX, description="Safe margins in pixels")
    corner_radius: int = Field(default=8, description="Default corner radius")
    stroke: Dict[str, Union[str, int]] = Field(default_factory=dict, description="Stroke properties")
    shadow: Dict[str, Union[str, int]] = Field(default_factory=dict, description="Shadow properties")
    backgrounds: List[str] = Field(default_factory=list, description="Background options")
    icon_palette: List[str] = Field(default_factory=list, description="Icon color options")
    
    @validator('font_sizes')
    def validate_font_sizes(cls, v):
        required_keys = {'hook', 'body', 'lower_third'}
        if not all(key in v for key in required_keys):
            raise ValueError(f"font_sizes must include: {required_keys}")
        return v


class Keyframe(BaseModel):
    """Keyframe for element animation."""
    
    t: int = Field(..., description="Time in milliseconds")
    x: Optional[float] = Field(None, description="X position")
    y: Optional[float] = Field(None, description="Y position")
    scale: Optional[float] = Field(None, description="Scale factor")
    rotate: Optional[float] = Field(None, description="Rotation in degrees")
    opacity: Optional[float] = Field(None, description="Opacity 0.0-1.0")
    
    @validator('opacity')
    def validate_opacity(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Opacity must be between 0.0 and 1.0")
        return v


class Element(BaseModel):
    """Visual element in a scene."""
    
    id: str = Field(..., description="Unique element identifier")
    type: str = Field(..., description="Element type")
    content: Optional[str] = Field(None, description="Text or content")
    x: float = Field(default=0.0, description="X position")
    y: float = Field(default=0.0, description="Y position")
    width: Optional[float] = Field(None, description="Width")
    height: Optional[float] = Field(None, description="Height")
    keyframes: List[Keyframe] = Field(default_factory=list, description="Animation keyframes")
    style: Optional[Dict[str, Union[str, int, float]]] = Field(None, description="Element-specific style")
    
    @validator('type')
    def validate_type(cls, v):
        valid_types = {"text", "prop", "character", "list_step", "shape", "lower_third", "counter"}
        if v not in valid_types:
            raise ValueError(f"Element type must be one of: {valid_types}")
        return v


class Scene(BaseModel):
    """Scene within a SceneScript."""
    
    id: str = Field(..., description="Unique scene identifier")
    duration_ms: int = Field(..., description="Scene duration in milliseconds")
    bg: Optional[str] = Field(None, description="Background identifier")
    audio_cue: Optional[str] = Field(None, description="Audio cue identifier")
    elements: List[Element] = Field(default_factory=list, description="Scene elements")
    
    @validator('duration_ms')
    def validate_duration(cls, v):
        if v <= 0:
            raise ValueError("Scene duration must be positive")
        return v


class SceneScript(BaseModel):
    """Complete SceneScript for animatics generation."""
    
    slug: str = Field(..., description="Content slug identifier")
    fps: int = Field(default=FPS, description="Target frame rate")
    scenes: List[Scene] = Field(..., description="Scene sequence")
    metadata: Optional[Dict[str, Union[str, int, float]]] = Field(None, description="Additional metadata")
    
    @validator('fps')
    def validate_fps(cls, v):
        if v <= 0:
            raise ValueError("FPS must be positive")
        return v


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_style(path: Optional[str] = None) -> BrandStyle:
    """Load brand style configuration from YAML file with validation and defaults."""
    if path is None:
        path = Paths.brand_style()
    
    # Default style configuration
    default_style = {
        "colors": {
            "primary": "#2563eb",
            "secondary": "#7c3aed", 
            "accent": "#f59e0b",
            "success": "#10b981",
            "warning": "#f59e0b",
            "error": "#ef4444",
            "neutral": "#6b7280",
            "white": "#ffffff",
            "black": "#111827",
            "background": "#f9fafb",
            "text_primary": "#111827",
            "text_secondary": "#6b7280"
        },
        "fonts": {
            "primary": "Inter",
            "secondary": "Georgia",
            "monospace": "JetBrains Mono",
            "display": "Poppins",
            "fallback": "Arial, sans-serif"
        },
        "font_sizes": {
            "hook": 48,
            "body": 24,
            "lower_third": 32,
            "caption": 18,
            "tiny": 14
        },
        "safe_margins_px": 64,
        "corner_radius": 8,
        "stroke": {
            "width": 2,
            "color": "#e5e7eb",
            "style": "solid"
        },
        "shadow": {
            "x_offset": 0,
            "y_offset": 4,
            "blur": 12,
            "color": "rgba(0, 0, 0, 0.1)",
            "spread": 0
        },
        "backgrounds": ["gradient1", "paper", "solid_white", "solid_black"],
        "icon_palette": ["#2563eb", "#7c3aed", "#f59e0b", "#10b981", "#6b7280", "#ffffff", "#111827"]
    }
    
    try:
        import yaml
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Merge user data with defaults
        merged_data = default_style.copy()
        if data:
            # Deep merge for nested dictionaries
            for key, value in data.items():
                if key in merged_data and isinstance(merged_data[key], dict) and isinstance(value, dict):
                    merged_data[key].update(value)
                else:
                    merged_data[key] = value
        
        # Validate required font_sizes
        required_font_sizes = {'hook', 'body', 'lower_third'}
        if not all(key in merged_data.get('font_sizes', {}) for key in required_font_sizes):
            missing = required_font_sizes - set(merged_data.get('font_sizes', {}).keys())
            raise ValueError(f"Missing required font_sizes: {missing}")
        
        return BrandStyle(**merged_data)
        
    except ImportError:
        raise ImportError("PyYAML is required to load brand style configuration")
    except FileNotFoundError:
        # Return default style if file doesn't exist
        return BrandStyle(**default_style)
    except Exception as e:
        raise ValueError(f"Failed to load brand style from {path}: {e}")


def validate_scene_script(data: Union[Dict, SceneScript]) -> SceneScript:
    """Validate and return a SceneScript instance."""
    if isinstance(data, dict):
        return SceneScript(**data)
    elif isinstance(data, SceneScript):
        return data
    else:
        raise TypeError("Data must be a dict or SceneScript instance")


def save_scene_script(scene_script: SceneScript, path: Optional[Path] = None) -> None:
    """Save SceneScript to JSON file."""
    if path is None:
        path = Paths.scene_script(scene_script.slug)
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(scene_script.dict(), f, indent=2)


def load_scene_script(path: Union[str, Path]) -> SceneScript:
    """Load SceneScript from JSON file."""
    with open(path, 'r') as f:
        data = json.load(f)
    return SceneScript(**data)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Constants
    'VIDEO_W', 'VIDEO_H', 'FPS', 'SAFE_MARGINS_PX', 'MAX_WORDS_PER_CARD', 'LINE_HEIGHT',
    
    # Enums
    'AnimType',
    
    # Path helpers
    'Paths',
    
    # Models
    'BrandStyle', 'Keyframe', 'Element', 'Scene', 'SceneScript',
    
    # Helper functions
    'load_style', 'validate_scene_script', 'save_scene_script', 'load_scene_script',
]
