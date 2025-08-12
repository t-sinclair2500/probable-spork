#!/usr/bin/env python3
"""
Test script for the Storyboard Asset Loop functionality.

This script tests the asset loop by creating a simple storyboard and running
the asset loop to ensure it identifies requirements, matches existing assets,
and generates missing ones.
"""

import json
import logging
import sys
from pathlib import Path

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.cutout.sdk import SceneScript, Scene, Element, BrandStyle, load_style
from bin.cutout.asset_loop import StoryboardAssetLoop, analyze_asset_requirements

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)


def create_test_storyboard() -> SceneScript:
    """Create a test storyboard with various asset requirements."""
    # Create test scenes with different asset needs
    scenes = []
    
    # Scene 1: Background + text
    scene1 = Scene(
        id="scene_001",
        duration_ms=5000,
        bg="gradient1",  # This should match existing brand asset
        elements=[
            Element(
                id="text_001",
                type="text",
                content="Welcome to the test",
                x=640,
                y=360
            )
        ]
    )
    scenes.append(scene1)
    
    # Scene 2: Character + prop
    scene2 = Scene(
        id="scene_002",
        duration_ms=4000,
        bg="paper",  # This should match existing brand asset
        elements=[
            Element(
                id="character_001",
                type="character",
                content="narrator",  # This should match existing brand asset
                x=400,
                y=300
            ),
            Element(
                id="prop_001",
                type="prop",
                content="phone",  # This should be generated
                x=800,
                y=300
            )
        ]
    )
    scenes.append(scene2)
    
    # Scene 3: Missing assets
    scene3 = Scene(
        id="scene_003",
        duration_ms=3000,
        bg="missing_bg",  # This should be generated
        elements=[
            Element(
                id="character_002",
                type="character",
                content="missing_character",  # This should be generated
                x=640,
                y=360
            )
        ]
    )
    scenes.append(scene3)
    
    return SceneScript(
        slug="test_asset_loop",
        fps=30,
        scenes=scenes
    )


def test_asset_analysis():
    """Test asset requirement analysis."""
    log.info("=== Testing Asset Requirement Analysis ===")
    
    storyboard = create_test_storyboard()
    requirements = analyze_asset_requirements(storyboard)
    
    log.info(f"Identified {len(requirements)} asset requirements:")
    for req in requirements:
        log.info(f"  - {req}")
    
    # Verify we have the expected requirements
    expected_types = {"background", "character", "prop"}
    actual_types = {req.asset_type for req in requirements}
    
    if expected_types == actual_types:
        log.info("✓ Asset type analysis correct")
    else:
        log.error(f"✗ Asset type analysis failed. Expected: {expected_types}, Got: {actual_types}")
        return False
    
    return True


def test_asset_library():
    """Test asset library functionality."""
    log.info("=== Testing Asset Library ===")
    
    try:
        brand_style = load_style()
        asset_library = StoryboardAssetLoop("test", brand_style).asset_library
        
        stats = asset_library.get_coverage_stats()
        log.info(f"Asset library stats: {stats}")
        
        # Test finding existing assets
        bg_path = asset_library.find_asset("background", "gradient1")
        if bg_path:
            log.info(f"✓ Found existing background: {bg_path}")
        else:
            log.warning("⚠ No existing background found for 'gradient1'")
        
        char_path = asset_library.find_asset("character", "narrator")
        if char_path:
            log.info(f"✓ Found existing character: {char_path}")
        else:
            log.warning("⚠ No existing character found for 'narrator'")
        
        return True
        
    except Exception as e:
        log.error(f"✗ Asset library test failed: {e}")
        return False


def test_asset_generation():
    """Test procedural asset generation."""
    log.info("=== Testing Asset Generation ===")
    
    try:
        brand_style = load_style()
        generator = StoryboardAssetLoop("test", brand_style).asset_generator
        
        # Test generating a background
        from bin.cutout.asset_loop import AssetRequirement
        bg_req = AssetRequirement("background", "test_bg", "test_element", "test_scene")
        
        generated_path = generator.generate_asset(bg_req)
        if generated_path and Path(generated_path).exists():
            log.info(f"✓ Generated background asset: {generated_path}")
            # Clean up test file
            Path(generated_path).unlink()
        else:
            log.error("✗ Failed to generate background asset")
            return False
        
        # Test generating a prop
        prop_req = AssetRequirement("prop", "test_prop", "test_element", "test_scene")
        
        generated_path = generator.generate_asset(prop_req)
        if generated_path and Path(generated_path).exists():
            log.info(f"✓ Generated prop asset: {generated_path}")
            # Clean up test file
            Path(generated_path).unlink()
        else:
            log.error("✗ Failed to generate prop asset")
            return False
        
        return True
        
    except Exception as e:
        log.error(f"✗ Asset generation test failed: {e}")
        return False


def test_full_asset_loop():
    """Test the complete asset loop."""
    log.info("=== Testing Full Asset Loop ===")
    
    try:
        brand_style = load_style()
        storyboard = create_test_storyboard()
        
        # Run the asset loop
        loop = StoryboardAssetLoop("test_asset_loop", brand_style, seed=42)
        updated_storyboard, coverage_results = loop.run_asset_loop(storyboard, max_iterations=2)
        
        log.info(f"Asset loop completed with coverage: {coverage_results['coverage_pct']:.1f}%")
        log.info(f"Requirements: {coverage_results['covered_requirements']}/{coverage_results['total_requirements']}")
        
        # Check if we achieved good coverage
        if coverage_results['coverage_pct'] >= 80.0:
            log.info("✓ Asset loop achieved good coverage")
            return True
        else:
            log.warning(f"⚠ Asset loop achieved only {coverage_results['coverage_pct']:.1f}% coverage")
            return False
        
    except Exception as e:
        log.error(f"✗ Full asset loop test failed: {e}")
        return False


def main():
    """Run all asset loop tests."""
    log.info("Starting Asset Loop Tests")
    
    tests = [
        ("Asset Analysis", test_asset_analysis),
        ("Asset Library", test_asset_library),
        ("Asset Generation", test_asset_generation),
        ("Full Asset Loop", test_full_asset_loop)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        log.info(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed += 1
                log.info(f"✓ {test_name} PASSED")
            else:
                log.error(f"✗ {test_name} FAILED")
        except Exception as e:
            log.error(f"✗ {test_name} ERROR: {e}")
    
    log.info(f"\n=== Test Results ===")
    log.info(f"Passed: {passed}/{total}")
    
    if passed == total:
        log.info("🎉 All tests passed!")
        return 0
    else:
        log.error("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
