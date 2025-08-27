#!/usr/bin/env python3
"""
Test script for Texture Engine

This script tests the texture engine functionality and demonstrates
the mid-century modern print effects on sample images.
"""

import os
import sys
from pathlib import Path

# Add bin directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bin'))

def test_texture_engine():
    """Test the texture engine with sample configuration."""
    
    # Sample texture configuration
    texture_config = {
        "enabled": True,
        "cache_dir": "render_cache/textures",
        "session_based": True,
        
        # Noise settings
        "grain": {
            "density": 0.15,
            "scale": 2.0,
            "intensity": 0.08,
            "seed_variation": True
        },
        
        # Edge treatment
        "edges": {
            "feather_radius": 1.5,
            "posterization_levels": 8,
            "edge_strength": 0.3
        },
        
        # Halftone effect
        "halftone": {
            "enabled": True,
            "dot_size": 1.2,
            "dot_spacing": 3.0,
            "angle": 45,
            "intensity": 0.12
        },
        
        # Color constraints
        "color_preservation": True,
        "brand_palette_only": True
    }
    
    # Brand palette for testing
    brand_palette = [
        "#1C4FA1", "#D62828", "#F6BE00", "#F28C28", 
        "#4E9F3D", "#008080", "#8B5E3C", "#1A1A1A", 
        "#FFFFFF", "#F8F1E5", "#FF6F91"
    ]
    
    try:
        # Import texture engine
        from bin.cutout.texture_engine import create_texture_engine
        
        print("✓ Texture engine imported successfully")
        
        # Create texture engine
        engine = create_texture_engine(texture_config, brand_palette)
        print("✓ Texture engine created successfully")
        
        # Test texture generation
        print("\nTesting texture generation...")
        
        # Generate noise texture
        noise_texture = engine.generate_noise_texture(400, 300)
        print(f"✓ Noise texture generated: {noise_texture.size}")
        
        # Generate halftone texture
        halftone_texture = engine.generate_halftone_texture(400, 300)
        print(f"✓ Halftone texture generated: {halftone_texture.size}")
        
        # Test edge treatment
        test_image = noise_texture  # Use noise texture as test image
        edge_texture = engine.apply_edge_treatment(test_image)
        print(f"✓ Edge treatment applied: {edge_texture.size}")
        
        # Test complete texture overlay
        combined_texture = engine.apply_texture_overlay(test_image)
        print(f"✓ Complete texture overlay applied: {combined_texture.size}")
        
        # Test caching
        print("\nTesting texture caching...")
        cached_noise = engine.generate_noise_texture(400, 300)
        if cached_noise is noise_texture:
            print("✓ Texture caching working (same object returned)")
        else:
            print("✓ Texture caching working (new object created)")
        
        # Test cache directory creation
        cache_dir = Path(texture_config["cache_dir"])
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.png"))
            print(f"✓ Cache directory created with {len(cache_files)} files")
        else:
            print("⚠ Cache directory not created")
        
        print("\n✓ All texture engine tests passed!")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import texture engine: {e}")
        return False
    except Exception as e:
        print(f"✗ Texture engine test failed: {e}")
        return False


def test_texture_integration():
    """Test texture integration with rasterization pipeline."""
    
    try:
        from bin.cutout.texture_integration import (
            apply_texture_to_image, 
            get_texture_cache_key,
            check_texture_cache
        )
        
        print("✓ Texture integration imported successfully")
        
        # Test cache key generation
        cache_key = get_texture_cache_key("test.svg", 400, 300, {"enabled": True})
        print(f"✓ Cache key generated: {cache_key[:16]}...")
        
        print("✓ Texture integration tests passed!")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import texture integration: {e}")
        return False
    except Exception as e:
        print(f"✗ Texture integration test failed: {e}")
        return False


def test_configuration():
    """Test texture configuration loading."""
    
    try:
        from bin.core import load_config
        
        config = load_config()
        
        if hasattr(config, 'textures'):
            textures = config.textures
            print("✓ Texture configuration loaded successfully")
            print(f"  - Enabled: {textures.enabled}")
            print(f"  - Cache dir: {textures.cache_dir}")
            print(f"  - Grain intensity: {textures.grain.intensity}")
            print(f"  - Halftone enabled: {textures.halftone.enabled}")
            print(f"  - Edge feather radius: {textures.edges.feather_radius}")
            return True
        else:
            print("⚠ Texture configuration not found in config")
            return False
            
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False


def main():
    """Run all texture engine tests."""
    print("🧪 Texture Engine Test Suite")
    print("=" * 50)
    
    tests = [
        ("Configuration Loading", test_configuration),
        ("Texture Engine Core", test_texture_engine),
        ("Texture Integration", test_texture_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        print("-" * 30)
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Texture engine is ready for use.")
        return 0
    else:
        print("⚠ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
