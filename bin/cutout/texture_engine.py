#!/usr/bin/env python3
"""
Texture Engine for Mid-Century Modern Print Aesthetics

This module implements texture overlays and edge styling inspired by 
mid-century modern print techniques. Features include:
- Organic grain using opensimplex/perlin noise
- Edge feathering and posterization
- Halftone dot patterns
- Color-preserving texture application
- Session-based texture caching
"""

import hashlib
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from bin.core import get_logger

log = get_logger("texture_engine")

# Try to import optional dependencies
try:
    import opensimplex
    OPENIMPLEX_AVAILABLE = True
except ImportError:
    OPENIMPLEX_AVAILABLE = False
    log.warning("opensimplex not available, using numpy fallback for noise")

try:
    import skimage
    from skimage import filters, util
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False
    log.warning("scikit-image not available, using Pillow fallback for edge effects")


class TextureEngine:
    """Engine for generating and applying mid-century modern print textures."""
    
    def __init__(self, config: Dict, brand_palette: Optional[List[str]] = None):
        """
        Initialize texture engine.
        
        Args:
            config: Texture configuration from global config
            brand_palette: Brand color palette for color constraints
        """
        self.config = config
        self.brand_palette = brand_palette or []
        self.session_id = self._generate_session_id()
        self.cache_dir = Path(config.get("cache_dir", "render_cache/textures"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize noise generator
        if OPENIMPLEX_AVAILABLE:
            self.noise_gen = opensimplex.OpenSimplex(seed=hash(self.session_id) % 10000)
        else:
            random.seed(hash(self.session_id) % 10000)
        
        log.info(f"Texture engine initialized with session {self.session_id}")
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID for texture caching."""
        timestamp = int(time.time())
        random_val = random.randint(1000, 9999)
        return f"{timestamp}_{random_val}"
    
    def _get_cache_key(self, width: int, height: int, texture_type: str) -> str:
        """Generate cache key for texture."""
        key_data = f"{self.session_id}:{width}x{height}:{texture_type}"
        return hashlib.sha1(key_data.encode()).hexdigest()
    
    def _get_cached_texture(self, width: int, height: int, texture_type: str) -> Optional[Image.Image]:
        """Get cached texture if available."""
        if not self.config.get("session_based", True):
            return None
            
        cache_key = self._get_cache_key(width, height, texture_type)
        cache_path = self.cache_dir / f"{cache_key}.png"
        
        if cache_path.exists():
            try:
                texture = Image.open(cache_path)
                log.debug(f"Loaded cached texture: {cache_path}")
                return texture
            except Exception as e:
                log.warning(f"Failed to load cached texture {cache_path}: {e}")
        
        return None
    
    def _save_cached_texture(self, texture: Image.Image, width: int, height: int, texture_type: str):
        """Save texture to cache."""
        if not self.config.get("session_based", True):
            return
            
        cache_key = self._get_cache_key(width, height, texture_type)
        cache_path = self.cache_dir / f"{cache_key}.png"
        
        try:
            texture.save(cache_path, "PNG")
            log.debug(f"Saved texture to cache: {cache_path}")
        except Exception as e:
            log.warning(f"Failed to save texture to cache {cache_path}: {e}")
    
    def generate_noise_texture(self, width: int, height: int) -> Image.Image:
        """
        Generate organic grain texture using noise.
        
        Args:
            width: Texture width in pixels
            height: Texture height in pixels
            
        Returns:
            PIL Image with noise texture
        """
        # Check cache first
        cached = self._get_cached_texture(width, height, "noise")
        if cached:
            return cached
        
        # Generate noise array
        grain_config = self.config.get("grain", {})
        density = grain_config.get("density", 0.15)
        scale = grain_config.get("scale", 2.0)
        intensity = grain_config.get("intensity", 0.08)
        
        # Create coordinate arrays
        x_coords = np.linspace(0, scale, width)
        y_coords = np.linspace(0, scale, height)
        X, Y = np.meshgrid(x_coords, y_coords)
        
        # Generate noise
        if OPENIMPLEX_AVAILABLE:
            # Use opensimplex for better quality
            noise_array = np.zeros((height, width))
            for y in range(height):
                for x in range(width):
                    noise_array[y, x] = self.noise_gen.noise2(x_coords[x], y_coords[y])
        else:
            # Fallback to numpy random
            noise_array = np.random.rand(height, width) * 2 - 1
        
        # Apply density and intensity
        noise_array = noise_array * density * intensity
        
        # Convert to PIL Image
        noise_array = ((noise_array + 1) * 127.5).astype(np.uint8)
        texture = Image.fromarray(noise_array, mode='L')
        
        # Save to cache
        self._save_cached_texture(texture, width, height, "noise")
        
        return texture
    
    def generate_halftone_texture(self, width: int, height: int) -> Image.Image:
        """
        Generate halftone dot pattern texture.
        
        Args:
            width: Texture width in pixels
            height: Texture height in pixels
            
        Returns:
            PIL Image with halftone texture
        """
        halftone_config = self.config.get("halftone", {})
        if not halftone_config.get("enabled", True):
            # Return blank texture if halftone disabled
            return Image.new('L', (width, height), 255)
        
        # Check cache first
        cached = self._get_cached_texture(width, height, "halftone")
        if cached:
            return cached
        
        dot_size = halftone_config.get("dot_size", 1.2)
        dot_spacing = halftone_config.get("dot_spacing", 3.0)
        angle = halftone_config.get("angle", 45)
        intensity = halftone_config.get("intensity", 0.12)
        
        # Create halftone pattern
        texture = Image.new('L', (width, height), 255)
        
        # Calculate dot positions
        spacing = int(dot_spacing)
        dot_radius = int(dot_size / 2)
        
        # Apply rotation
        cos_a = np.cos(np.radians(angle))
        sin_a = np.sin(np.radians(angle))
        
        for y in range(0, height, spacing):
            for x in range(0, width, spacing):
                # Rotate coordinates
                rx = x * cos_a - y * sin_a
                ry = x * sin_a + y * cos_a
                
                # Check if rotated position is within bounds
                if 0 <= rx < width and 0 <= ry < height:
                    # Create dot
                    dot_intensity = int(255 * (1 - intensity))
                    for dy in range(-dot_radius, dot_radius + 1):
                        for dx in range(-dot_radius, dot_radius + 1):
                            if dx*dx + dy*dy <= dot_radius*dot_radius:
                                px, py = int(rx + dx), int(ry + dy)
                                if 0 <= px < width and 0 <= py < height:
                                    texture.putpixel((px, py), dot_intensity)
        
        # Save to cache
        self._save_cached_texture(texture, width, height, "halftone")
        
        return texture
    
    def apply_edge_treatment(self, image: Image.Image) -> Image.Image:
        """
        Apply edge feathering and posterization.
        
        Args:
            image: Input PIL Image
            
        Returns:
            PIL Image with edge treatment applied
        """
        edges_config = self.config.get("edges", {})
        feather_radius = edges_config.get("feather_radius", 1.5)
        posterization_levels = edges_config.get("posterization_levels", 8)
        edge_strength = edges_config.get("edge_strength", 0.3)
        
        # Apply edge detection if scikit-image available
        if SKIMAGE_AVAILABLE:
            # Convert to numpy array
            img_array = np.array(image)
            
            # Edge detection
            if len(img_array.shape) == 3:
                # Color image - convert to grayscale for edge detection
                gray = np.mean(img_array, axis=2).astype(np.uint8)
            else:
                gray = img_array
            
            # Apply edge detection
            edges = filters.sobel(gray)
            edges = (edges * edge_strength * 255).astype(np.uint8)
            
            # Convert back to PIL
            edge_image = Image.fromarray(edges, mode='L')
        else:
            # Fallback to Pillow edge detection
            edge_image = image.filter(ImageFilter.FIND_EDGES)
            edge_image = edge_image.point(lambda x: int(x * edge_strength))
        
        # Apply feathering
        if feather_radius > 0:
            edge_image = edge_image.filter(ImageFilter.GaussianBlur(radius=feather_radius))
        
        # Apply posterization
        if posterization_levels > 1:
            edge_image = ImageOps.posterize(edge_image, posterization_levels)
        
        return edge_image
    
    def apply_texture_overlay(self, image: Image.Image, preserve_colors: bool = True) -> Image.Image:
        """
        Apply complete texture overlay to image.
        
        Args:
            image: Input PIL Image
            preserve_colors: Whether to preserve original colors
            
        Returns:
            PIL Image with texture applied
        """
        if not self.config.get("enabled", True):
            return image
        
        width, height = image.size
        
        # Generate textures
        noise_texture = self.generate_noise_texture(width, height)
        halftone_texture = self.generate_halftone_texture(width, height)
        
        # Apply edge treatment to original image
        edge_texture = self.apply_edge_treatment(image)
        
        # Combine textures
        combined_texture = Image.new('L', (width, height), 255)
        
        # Blend noise texture
        noise_alpha = self.config.get("grain", {}).get("intensity", 0.08)
        if noise_alpha > 0:
            combined_texture = Image.blend(combined_texture, noise_texture, noise_alpha)
        
        # Blend halftone texture
        halftone_alpha = self.config.get("halftone", {}).get("intensity", 0.12)
        if halftone_alpha > 0:
            combined_texture = Image.blend(combined_texture, halftone_texture, halftone_alpha)
        
        # Blend edge texture
        edge_alpha = self.config.get("edges", {}).get("edge_strength", 0.3)
        if edge_alpha > 0:
            combined_texture = Image.blend(combined_texture, edge_texture, edge_alpha)
        
        # Apply texture overlay
        if preserve_colors:
            # Preserve original colors, apply texture as overlay
            result = image.copy()
            
            # Convert texture to RGBA for blending
            if image.mode == 'RGBA':
                texture_rgba = combined_texture.convert('RGBA')
                # Use texture as alpha mask for subtle overlay
                overlay_alpha = 0.15  # Very subtle overlay
                result = Image.blend(result, texture_rgba, overlay_alpha)
            else:
                # Convert to RGBA for blending
                result = result.convert('RGBA')
                texture_rgba = combined_texture.convert('RGBA')
                overlay_alpha = 0.15
                result = Image.blend(result, texture_rgba, overlay_alpha)
        else:
            # Apply texture more aggressively
            result = Image.composite(image, combined_texture, combined_texture)
        
        return result
    
    def process_image(self, image_path: str, output_path: Optional[str] = None) -> str:
        """
        Process a single image with texture overlay.
        
        Args:
            image_path: Path to input image
            output_path: Path for output image (optional)
            
        Returns:
            Path to processed image
        """
        try:
            # Load image
            image = Image.open(image_path)
            
            # Apply texture overlay
            processed = self.apply_texture_overlay(image)
            
            # Determine output path
            if output_path is None:
                base_path = Path(image_path)
                output_path = str(base_path.parent / f"{base_path.stem}_textured{base_path.suffix}")
            
            # Save processed image
            processed.save(output_path, "PNG")
            log.info(f"Applied texture overlay to {image_path} -> {output_path}")
            
            return output_path
            
        except Exception as e:
            log.error(f"Failed to process image {image_path}: {e}")
            raise
    
    def process_image_batch(self, image_paths: List[str], output_dir: Optional[str] = None) -> List[str]:
        """
        Process multiple images with texture overlay.
        
        Args:
            image_paths: List of input image paths
            output_dir: Output directory (optional)
            
        Returns:
            List of processed image paths
        """
        processed_paths = []
        
        for image_path in image_paths:
            try:
                if output_dir:
                    base_name = Path(image_path).name
                    output_path = os.path.join(output_dir, f"textured_{base_name}")
                else:
                    output_path = None
                
                processed_path = self.process_image(image_path, output_path)
                processed_paths.append(processed_path)
                
            except Exception as e:
                log.error(f"Failed to process {image_path}: {e}")
                # Continue with other images
        
        return processed_paths
    
    def cleanup_cache(self):
        """Clean up texture cache."""
        try:
            if self.cache_dir.exists():
                for cache_file in self.cache_dir.glob("*.png"):
                    cache_file.unlink()
                log.info(f"Cleaned up texture cache: {self.cache_dir}")
        except Exception as e:
            log.warning(f"Failed to cleanup texture cache: {e}")


def create_texture_engine(config: Dict, brand_palette: Optional[List[str]] = None) -> TextureEngine:
    """
    Factory function to create texture engine.
    
    Args:
        config: Texture configuration
        brand_palette: Brand color palette
        
    Returns:
        TextureEngine instance
    """
    return TextureEngine(config, brand_palette)
