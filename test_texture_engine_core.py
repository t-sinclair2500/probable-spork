#!/usr/bin/env python3
"""
Basic test for Texture Engine Core (P3-1)
"""

import os
import sys
from pathlib import Path

# Add bin to path
sys.path.insert(0, str(Path(__file__).parent / "bin"))

try:
    from PIL import Image
    import numpy as np
    from cutout.texture_engine import (
        apply_textures_to_frame,
        texture_signature,
        apply_textures_to_clip
    )
    
    def test_texture_signature():
        """Test texture signature generation."""
        cfg1 = {"enable": True, "grain_strength": 0.12}
        cfg2 = {"enable": True, "grain_strength": 0.12}
        cfg3 = {"enable": True, "grain_strength": 0.15}
        
        sig1 = texture_signature(cfg1)
        sig2 = texture_signature(cfg2)
        sig3 = texture_signature(cfg3)
        
        print(f"Config 1 signature: {sig1}")
        print(f"Config 2 signature: {sig2}")
        print(f"Config 3 signature: {sig3}")
        
        assert sig1 == sig2, "Same config should have same signature"
        assert sig1 != sig3, "Different config should have different signature"
        print("✓ Texture signature test passed")
        
    def test_texture_application():
        """Test texture application to a frame."""
        # Create a test image
        test_img = Image.new('RGB', (100, 100), color='white')
        
        # Test configuration
        cfg = {
            "enable": True,
            "grain_strength": 0.1,
            "feather_px": 1.0,
            "posterize_levels": 4,
            "halftone": {
                "enable": True,
                "cell_px": 8,
                "angle_deg": 45,
                "opacity": 0.1
            }
        }
        
        seed = 42
        
        # Apply textures
        textured_img = apply_textures_to_frame(test_img, cfg, seed)
        
        assert textured_img is not None, "Textured image should not be None"
        assert textured_img.size == test_img.size, "Size should be preserved"
        
        # Check that image was modified
        original_array = np.array(test_img)
        textured_array = np.array(textured_img)
        
        # Should be different due to textures
        assert not np.array_equal(original_array, textured_array), "Image should be modified by textures"
        
        print("✓ Texture application test passed")
        
    def test_deterministic_output():
        """Test that same seed + config produces identical output."""
        test_img = Image.new('RGB', (50, 50), color='blue')
        
        cfg = {
            "enable": True,
            "grain_strength": 0.2,
            "feather_px": 0.5,
            "posterize_levels": 3
        }
        
        seed = 123
        
        # Apply textures twice with same parameters
        result1 = apply_textures_to_frame(test_img, cfg, seed)
        result2 = apply_textures_to_frame(test_img, cfg, seed)
        
        # Results should be identical
        array1 = np.array(result1)
        array2 = np.array(result2)
        
        assert np.array_equal(array1, array2), "Same seed + config should produce identical output"
        print("✓ Deterministic output test passed")
        
    def main():
        """Run all tests."""
        print("Testing Texture Engine Core (P3-1)")
        print("=" * 40)
        
        test_texture_signature()
        test_texture_application()
        test_deterministic_output()
        
        print("\n✓ All tests passed!")
        
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you have the required dependencies installed:")
    print("pip install Pillow numpy")
    sys.exit(1)
except Exception as e:
    print(f"Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
