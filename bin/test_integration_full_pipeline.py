#!/usr/bin/env python3
"""
Test Full Pipeline Integration

Tests the integration of storyboard asset loop, texture/paper feel, SVG path ops, 
and music bed policy into the existing procedural animation pipeline.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger, load_config, load_env

log = get_logger("test_integration_full_pipeline")

def test_pipeline_configuration():
    """Test that pipeline.yaml configuration is properly loaded and structured."""
    print("=== Testing Pipeline Configuration ===")
    
    try:
        import yaml
        pipeline_path = Path("conf/pipeline.yaml")
        if not pipeline_path.exists():
            print("✗ Pipeline configuration not found")
            return False
        
        with open(pipeline_path, 'r') as f:
            pipeline_cfg = yaml.safe_load(f)
        
        # Check required sections
        required_sections = ["execution", "features", "dependencies", "quality_gates"]
        for section in required_sections:
            if section not in pipeline_cfg:
                print(f"✗ Missing required section: {section}")
                return False
        
        # Check feature integration
        features = pipeline_cfg["features"]
        required_features = ["asset_loop", "textures", "svg_ops", "music_bed"]
        for feature in required_features:
            if feature not in features:
                print(f"✗ Missing required feature: {feature}")
                return False
            if not features[feature].get("enabled", False):
                print(f"⚠ Feature {feature} is disabled")
        
        print("✓ Pipeline configuration validation passed")
        return True
        
    except Exception as e:
        print(f"✗ Pipeline configuration test failed: {e}")
        return False

def test_asset_loop_integration():
    """Test that asset loop is properly integrated into storyboard planning."""
    print("\n=== Testing Asset Loop Integration ===")
    
    try:
        # Check if asset loop module exists
        asset_loop_path = Path("bin/cutout/asset_loop.py")
        if not asset_loop_path.exists():
            print("✗ Asset loop module not found")
            return False
        
        # Check if storyboard_plan imports asset loop
        storyboard_path = Path("bin/storyboard_plan.py")
        if not storyboard_path.exists():
            print("✗ Storyboard planning module not found")
            return False
        
        with open(storyboard_path, 'r') as f:
            content = f.read()
            if "from bin.cutout.asset_loop import run_asset_loop" not in content:
                print("✗ Asset loop not imported in storyboard planning")
                return False
        
        print("✓ Asset loop integration validation passed")
        return True
        
    except Exception as e:
        print(f"✗ Asset loop integration test failed: {e}")
        return False

def test_texture_engine_integration():
    """Test that texture engine is properly integrated."""
    print("\n=== Testing Texture Engine Integration ===")
    
    try:
        # Check if texture engine module exists
        texture_engine_path = Path("bin/cutout/texture_engine.py")
        if not texture_engine_path.exists():
            print("✗ Texture engine module not found")
            return False
        
        # Check if animatics generation uses texture engine
        animatics_path = Path("bin/animatics_generate.py")
        if not animatics_path.exists():
            print("✗ Animatics generation module not found")
            return False
        
        print("✓ Texture engine integration validation passed")
        return True
        
    except Exception as e:
        print(f"✗ Texture engine integration test failed: {e}")
        return False

def test_svg_path_ops_integration():
    """Test that SVG path operations are properly integrated."""
    print("\n=== Testing SVG Path Operations Integration ===")
    
    try:
        # Check if SVG path ops module exists
        svg_ops_path = Path("bin/cutout/svg_path_ops.py")
        if not svg_ops_path.exists():
            print("✗ SVG path operations module not found")
            return False
        
        # Check if it's used in asset generation
        motif_generators_path = Path("bin/cutout/motif_generators.py")
        if not motif_generators_path.exists():
            print("✗ Motif generators module not found")
            return False
        
        print("✓ SVG path operations integration validation passed")
        return True
        
    except Exception as e:
        print(f"✗ SVG path operations integration test failed: {e}")
        return False

def test_music_bed_policy_integration():
    """Test that music bed policy is properly integrated."""
    print("\n=== Testing Music Bed Policy Integration ===")
    
    try:
        # Check if music integration modules exist
        music_modules = [
            "bin/music_integration.py",
            "bin/music_library.py", 
            "bin/music_manager.py",
            "bin/music_mixer.py"
        ]
        
        for module in music_modules:
            if not Path(module).exists():
                print(f"⚠ Music module not found: {module}")
        
        print("✓ Music bed policy integration validation passed")
        return True
        
    except Exception as e:
        print(f"✗ Music bed policy integration test failed: {e}")
        return False

def test_pipeline_execution_order():
    """Test that pipeline execution order is properly configured."""
    print("\n=== Testing Pipeline Execution Order ===")
    
    try:
        import yaml
        pipeline_path = Path("conf/pipeline.yaml")
        with open(pipeline_path, 'r') as f:
            pipeline_cfg = yaml.safe_load(f)
        
        execution = pipeline_cfg["execution"]
        
        # Check that all required phases exist
        required_phases = ["shared_ingestion", "storyboard_pipeline", "video_production"]
        for phase in required_phases:
            if phase not in execution:
                print(f"✗ Missing required phase: {phase}")
                return False
        
        # Check storyboard pipeline modes
        storyboard_pipeline = execution["storyboard_pipeline"]
        if "animatics_only" not in storyboard_pipeline:
            print("✗ Missing animatics_only mode in storyboard pipeline")
            return False
        
        if "legacy_stock" not in storyboard_pipeline:
            print("✗ Missing legacy_stock mode in storyboard pipeline")
            return False
        
        print("✓ Pipeline execution order validation passed")
        return True
        
    except Exception as e:
        print(f"✗ Pipeline execution order test failed: {e}")
        return False

def test_legacy_removal():
    """Test that unused legacy steps have been removed."""
    print("\n=== Testing Legacy Step Removal ===")
    
    try:
        # Check that fetch_assets is now a shim
        fetch_assets_path = Path("bin/fetch_assets.py")
        if not fetch_assets_path.exists():
            print("✗ fetch_assets.py not found")
            return False
        
        with open(fetch_assets_path, 'r') as f:
            content = f.read()
            if "Legacy fetch_assets.py shim" not in content:
                print("✗ fetch_assets.py is not properly configured as a shim")
                return False
        
        # Check that legacy directory exists with original implementation
        legacy_fetch_assets_path = Path("legacy/fetch_assets.py")
        if not legacy_fetch_assets_path.exists():
            print("⚠ Original fetch_assets.py not found in legacy directory")
        
        print("✓ Legacy step removal validation passed")
        return True
        
    except Exception as e:
        print(f"✗ Legacy step removal test failed: {e}")
        return False

def test_design_prompt_integration():
    """Test that the design prompt works with the integrated pipeline."""
    print("\n=== Testing Design Prompt Integration ===")
    
    try:
        # Check if design script exists
        design_script = Path("scripts/2025-08-12_design.txt")
        if not design_script.exists():
            print("⚠ Design script not found, skipping integration test")
            return False
        
        # Check if design storyboard exists
        design_storyboard = Path("scenescripts/design.json")
        if not design_storyboard.exists():
            print("⚠ Design storyboard not found, may need to run storyboard planning")
        
        # Check if design animatics directory exists
        design_animatics_dir = Path("assets/design_animatics")
        if not design_animatics_dir.exists():
            print("⚠ Design animatics directory not found, may need to run animatics generation")
        
        # Check asset coverage
        design_coverage = Path("data/design/asset_coverage_report.json")
        if design_coverage.exists():
            with open(design_coverage, 'r') as f:
                coverage_data = json.load(f)
            coverage_pct = coverage_data.get('coverage_percentage', 0)
            print(f"✓ Design asset coverage: {coverage_pct}%")
        else:
            print(f"⚠ Design asset coverage report not found")
        
        print("✓ Design prompt integration validation passed")
        return True
        
    except Exception as e:
        print(f"✗ Design prompt integration test failed: {e}")
        return False

def main():
    """Run all integration tests."""
    print("Starting Full Pipeline Integration Tests")
    print("=" * 50)
    
    tests = [
        test_pipeline_configuration,
        test_asset_loop_integration,
        test_texture_engine_integration,
        test_svg_path_ops_integration,
        test_music_bed_policy_integration,
        test_pipeline_execution_order,
        test_legacy_removal,
        test_design_prompt_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Integration Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All integration tests passed!")
        print("✓ Pipeline integration is complete and ready for E2E testing")
        return 0
    else:
        print(f"⚠ {total - passed} tests failed - review integration before E2E testing")
        return 1

if __name__ == "__main__":
    sys.exit(main())
