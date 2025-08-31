#!/usr/bin/env python3
"""
Integration Test for Storyboard Asset Loop

This script tests the complete integration of the asset loop in the pipeline,
verifying that it works seamlessly between storyboard planning and animatics generation.
"""

import json
import logging
import sys
import time
from pathlib import Path

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.cutout.sdk import load_scene_script, Paths
from bin.cutout.asset_loop import analyze_asset_requirements

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)


def test_design_pipeline_integration():
    """Test the complete design pipeline integration."""
    log.info("=== Testing Design Pipeline Integration ===")
    
    # Load scenescript
    scenescript_path = Paths.scene_script("test_slug")
    if not scenescript_path.exists():
        log.warning("SceneScript not found, skipping test")
        return False
    
    # Load scenescript data
    with open(scenescript_path, 'r') as f:
        scenescript = json.load(f)
    
    # Validate scenescript structure
    validation_errors = validate_scenescript(scenescript)
    if validation_errors:
        log.error(f"SceneScript validation failed: {validation_errors}")
        return False
    
    log.info("✓ SceneScript validation passed")
    
    # Check asset coverage
    coverage_report_path = Path("data/test_slug/asset_coverage_report.json")
    if coverage_report_path.exists():
        with open(coverage_report_path, 'r') as f:
            coverage_data = json.load(f)
        
        coverage_pct = coverage_data.get('coverage_percentage', 0)
        if coverage_pct >= 80:
            log.info(f"✓ Asset coverage: {coverage_pct}%")
        else:
            log.warning(f"⚠ Asset coverage below threshold: {coverage_pct}%")
    else:
        log.warning("⚠ Asset coverage report not found")
    
    # Check animatics directory
    animatics_dir = Path("assets/test_slug_animatics")
    if animatics_dir.exists():
        animatic_files = list(animatics_dir.glob("*.mp4"))
        if animatic_files:
            log.info(f"✓ Found {len(animatic_files)} animatic files")
        else:
            log.warning("⚠ Animatics directory exists but no MP4 files found")
    else:
        log.warning("⚠ Animatics directory not found")
    
    log.info("✓ Design pipeline integration test completed")
    return True


def test_asset_loop_workflow():
    """Test the asset loop workflow with a simple storyboard."""
    log.info("=== Testing Asset Loop Workflow ===")
    
    # Create a simple test storyboard
    from bin.cutout.sdk import SceneScript, Scene, Element, BrandStyle, load_style
    from bin.cutout.asset_loop import StoryboardAssetLoop
    
    try:
        # Create test storyboard with missing assets
        scenes = [
            Scene(
                id="test_scene",
                duration_ms=5000,
                bg="missing_background",  # This should be generated
                elements=[
                    Element(
                        id="test_element",
                        type="prop",
                        content="missing_prop",  # This should be generated
                        x=640,
                        y=360
                    )
                ]
            )
        ]
        
        test_script = SceneScript(
            slug="test_integration",
            fps=30,
            scenes=scenes
        )
        
        # Run asset loop
        brand_style = load_style()
        loop = StoryboardAssetLoop("test_integration", brand_style, seed=42)
        updated_script, coverage_results = loop.run_asset_loop(test_script, max_iterations=2)
        
        log.info(f"✓ Asset loop completed with {coverage_results['coverage_pct']:.1f}% coverage")
        
        # Verify that assets were generated
        if coverage_results['is_fully_covered']:
            log.info("✓ Asset loop achieved 100% coverage")
            return True
        else:
            log.warning(f"⚠ Asset loop achieved only {coverage_results['coverage_pct']:.1f}% coverage")
            return False
        
    except Exception as e:
        log.error(f"✗ Asset loop workflow test failed: {e}")
        return False


def main():
    """Run all integration tests."""
    log.info("Starting Storyboard Asset Loop Integration Tests")
    
    tests = [
        ("Design Pipeline Integration", test_design_pipeline_integration),
        ("Asset Loop Workflow", test_asset_loop_workflow)
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
    
    log.info(f"\n=== Integration Test Results ===")
    log.info(f"Passed: {passed}/{total}")
    
    if passed == total:
        log.info("🎉 All integration tests passed!")
        log.info("The Storyboard Asset Loop is fully integrated and working!")
        return 0
    else:
        log.error("❌ Some integration tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
