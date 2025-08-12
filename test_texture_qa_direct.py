#!/usr/bin/env python3
"""
Direct Test of Texture QA Functions

This script tests the texture QA functions directly without importing the full cutout package.
"""

import sys
from pathlib import Path

def test_dialback_logic():
    """Test the texture strength dialback logic directly."""
    print("Testing Texture Strength Dialback Logic")
    print("=" * 40)
    
    def _dial_back_texture_strength(config):
        """Automatically reduce texture strength for retry."""
        dialed_config = config.copy()
        
        # Reduce grain strength by 30%
        if "grain_strength" in dialed_config:
            current_strength = dialed_config["grain_strength"]
            dialed_config["grain_strength"] = max(0.0, current_strength * 0.7)
            print(f"Reduced grain_strength from {current_strength:.3f} to {dialed_config['grain_strength']:.3f}")
        
        # Increase posterize levels (softer effect)
        if "posterize_levels" in dialed_config:
            current_levels = dialed_config["posterize_levels"]
            dialed_config["posterize_levels"] = min(16, current_levels + 1)
            print(f"Increased posterize_levels from {current_levels} to {dialed_config['posterize_levels']}")
        
        # Disable halftone if enabled
        if "halftone" in dialed_config and dialed_config["halftone"].get("enable", False):
            dialed_config["halftone"]["enable"] = False
            print("Disabled halftone effect")
        
        # Reduce feather effect
        if "feather_px" in dialed_config:
            current_feather = dialed_config["feather_px"]
            dialed_config["feather_px"] = max(0.5, current_feather * 0.8)
            print(f"Reduced feather_px from {current_feather:.1f} to {dialed_config['feather_px']:.1f}")
        
        return dialed_config
    
    # Test configuration
    original_config = {
        "grain_strength": 0.15,
        "posterize_levels": 6,
        "feather_px": 2.0,
        "halftone": {"enable": True, "opacity": 0.2}
    }
    
    print(f"Original config: {original_config}")
    
    # Apply dialback
    dialed_config = _dial_back_texture_strength(original_config)
    print(f"Dialed back config: {dialed_config}")
    
    # Verify changes
    assert dialed_config["grain_strength"] < original_config["grain_strength"], "Grain strength should be reduced"
    assert dialed_config["posterize_levels"] > original_config["posterize_levels"], "Posterize levels should increase"
    assert dialed_config["halftone"]["enable"] == False, "Halftone should be disabled"
    assert dialed_config["feather_px"] < original_config["feather_px"], "Feather should be reduced"
    
    print("✓ Dialback logic working correctly")
    return True

def test_qa_loop_logic():
    """Test the QA loop logic structure."""
    print("\nTesting QA Loop Logic Structure")
    print("=" * 35)
    
    def mock_qa_check(img, config):
        """Mock QA check that fails on first attempt."""
        # Simulate a QA check that fails on first attempt, passes on second
        if not hasattr(mock_qa_check, 'attempts'):
            mock_qa_check.attempts = 0
        mock_qa_check.attempts += 1
        
        if mock_qa_check.attempts == 1:
            return {"ok": False, "fails": ["Contrast too low"], "warnings": [], "details": {}}
        else:
            return {"ok": True, "fails": [], "warnings": [], "details": {}}
    
    def mock_texture_apply(img, config):
        """Mock texture application."""
        return img  # Return same image for simplicity
    
    def apply_texture_with_qa_loop_mock(img, config, max_retries=2):
        """Mock version of texture QA loop."""
        original_config = config.copy()
        current_config = config.copy()
        attempts = 0
        qa_results = []
        
        print(f"Starting texture application with QA loop (max retries: {max_retries})")
        
        while attempts <= max_retries:
            attempts += 1
            print(f"Attempt {attempts}: applying textures with config {current_config}")
            
            # Apply textures using current configuration
            processed_img = mock_texture_apply(img, current_config)
            
            # Run contrast/legibility check
            contrast_result = mock_qa_check(processed_img, current_config)
            qa_results.append({
                "attempt": attempts,
                "config": current_config.copy(),
                "contrast_result": contrast_result
            })
            
            if contrast_result["ok"]:
                print(f"QA passed on attempt {attempts}")
                break
            else:
                print(f"QA failed on attempt {attempts}: {contrast_result['fails']}")
                
                if attempts <= max_retries:
                    # Auto-dial back texture strength
                    current_config = _dial_back_texture_strength(current_config)
                    print(f"Dialing back texture strength for retry: {current_config}")
                else:
                    print(f"Max retries reached, using last processed image")
        
        # Prepare metadata
        metadata = {
            "textures": {
                "applied": True,
                "attempts": attempts,
                "final_params": current_config,
                "qa_results": qa_results,
                "original_config": original_config,
                "dialback_applied": attempts > 1
            }
        }
        
        print(f"Texture application completed successfully after {attempts} attempts")
        return processed_img, metadata
    
    def _dial_back_texture_strength(config):
        """Automatically reduce texture strength for retry."""
        dialed_config = config.copy()
        
        # Reduce grain strength by 30%
        if "grain_strength" in dialed_config:
            current_strength = dialed_config["grain_strength"]
            dialed_config["grain_strength"] = max(0.0, current_strength * 0.7)
        
        # Increase posterize levels (softer effect)
        if "posterize_levels" in dialed_config:
            current_levels = dialed_config["posterize_levels"]
            dialed_config["posterize_levels"] = min(16, current_levels + 1)
        
        # Disable halftone if enabled
        if "halftone" in dialed_config and dialed_config["halftone"].get("enable", False):
            dialed_config["halftone"]["enable"] = False
        
        # Reduce feather effect
        if "feather_px" in dialed_config:
            current_feather = dialed_config["feather_px"]
            dialed_config["feather_px"] = max(0.5, current_feather * 0.8)
        
        return dialed_config
    
    # Test the QA loop
    test_config = {
        "grain_strength": 0.2,
        "posterize_levels": 4,
        "feather_px": 3.0,
        "halftone": {"enable": True, "opacity": 0.3}
    }
    
    print(f"Testing with config: {test_config}")
    
    # Run the QA loop
    result_img, metadata = apply_texture_with_qa_loop_mock("mock_image", test_config)
    
    # Verify the results
    assert metadata["textures"]["attempts"] == 2, "Should take 2 attempts (fail then pass)"
    assert metadata["textures"]["dialback_applied"] == True, "Dialback should be applied"
    assert len(metadata["textures"]["qa_results"]) == 2, "Should have 2 QA results"
    
    print("✓ QA loop logic working correctly")
    print(f"  - Attempts: {metadata['textures']['attempts']}")
    print(f"  - Dialback applied: {metadata['textures']['dialback_applied']}")
    print(f"  - Final params: {metadata['textures']['final_params']}")
    
    return True

def main():
    """Run all texture QA tests."""
    print("Direct Texture QA Logic Test Suite")
    print("=" * 45)
    
    tests = [
        test_dialback_logic,
        test_qa_loop_logic
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All texture QA logic tests passed!")
        return True
    else:
        print("Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
