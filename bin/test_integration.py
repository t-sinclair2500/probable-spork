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


def test_eames_pipeline_integration():
    """Test the complete eames pipeline integration."""
    log.info("=== Testing Eames Pipeline Integration ===")
    
    # Test 1: Verify SceneScript was created with asset loop
    scenescript_path = Paths.scene_script("eames")
    if not scenescript_path.exists():
        log.error("✗ SceneScript not found - asset loop may have failed")
        return False
    
    log.info("✓ SceneScript created successfully")
    
    # Test 2: Load and analyze the SceneScript
    try:
        scenescript = load_scene_script(scenescript_path)
        log.info(f"✓ Loaded SceneScript with {len(scenescript.scenes)} scenes")
        
        # Analyze asset requirements
        requirements = analyze_asset_requirements(scenescript)
        log.info(f"✓ Identified {len(requirements)} asset requirements")
        
        # Check that all requirements are covered
        covered = sum(1 for r in requirements if r.asset_type == "background" and r.identifier == "gradient1")
        total = len(requirements)
        
        if covered == total:
            log.info(f"✓ All {total} requirements are covered by existing brand assets")
        else:
            log.warning(f"⚠ Only {covered}/{total} requirements covered by existing assets")
        
    except Exception as e:
        log.error(f"✗ Failed to load/analyze SceneScript: {e}")
        return False
    
    # Test 3: Verify coverage report was generated
    coverage_report_path = Path("data/eames/asset_coverage_report.json")
    if not coverage_report_path.exists():
        log.error("✗ Coverage report not found")
        return False
    
    try:
        with open(coverage_report_path, 'r') as f:
            coverage_data = json.load(f)
        
        coverage_pct = coverage_data.get("coverage_history", [{}])[-1].get("coverage_pct", 0)
        is_fully_covered = coverage_data.get("coverage_history", [{}])[-1].get("is_fully_covered", False)
        
        log.info(f"✓ Coverage report shows {coverage_pct:.1f}% coverage")
        
        if is_fully_covered:
            log.info("✓ Asset loop achieved 100% coverage")
        else:
            log.warning(f"⚠ Asset loop achieved only {coverage_pct:.1f}% coverage")
        
    except Exception as e:
        log.error(f"✗ Failed to read coverage report: {e}")
        return False
    
    # Test 4: Verify animatics can be generated
    animatics_dir = Path("assets/eames_animatics")
    if not animatics_dir.exists():
        log.error("✗ Animatics directory not found")
        return False
    
    scene_files = list(animatics_dir.glob("scene_*.mp4"))
    if len(scene_files) == 0:
        log.error("✗ No animatics found")
        return False
    
    log.info(f"✓ Found {len(scene_files)} animatics files")
    
    # Test 5: Verify generated assets directory exists and contains assets
    generated_dir = Path("assets/generated")
    if not generated_dir.exists():
        log.error("✗ Generated assets directory not found")
        return False
    
    generated_files = list(generated_dir.glob("*.svg"))
    if len(generated_files) == 0:
        log.warning("⚠ No generated assets found (this is OK if all assets were found)")
    else:
        log.info(f"✓ Found {len(generated_files)} generated assets")
    
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
        ("Eames Pipeline Integration", test_eames_pipeline_integration),
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
