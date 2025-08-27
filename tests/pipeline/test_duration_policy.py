#!/usr/bin/env python3
"""
Test script for duration policy validation
"""

import json
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent))

from bin.timing_utils import validate_duration_tolerance, compute_scene_durations
from bin.acceptance import AcceptanceValidator

def test_duration_tolerance():
    """Test duration tolerance validation"""
    print("Testing duration tolerance validation...")
    
    # Test case 1: Within tolerance
    is_valid, deviation, message = validate_duration_tolerance(90000, 90000, 5.0)
    print(f"Test 1 - Exact match: {is_valid} (deviation: {deviation:.1f}%) - {message}")
    
    # Test case 2: Within tolerance
    is_valid, deviation, message = validate_duration_tolerance(94500, 90000, 5.0)
    print(f"Test 2 - Within 5%: {is_valid} (deviation: {deviation:.1f}%) - {message}")
    
    # Test case 3: Outside tolerance
    is_valid, deviation, message = validate_duration_tolerance(99000, 90000, 5.0)
    print(f"Test 3 - Outside 5%: {is_valid} (deviation: {deviation:.1f}%) - {message}")
    
    print()

def test_scene_duration_computation():
    """Test scene duration computation"""
    print("Testing scene duration computation...")
    
    # Load the test SceneScript
    scenescript_path = Path("scenescripts/test_slug.json")
    if not scenescript_path.exists():
        print("SceneScript not found, skipping test")
        return
    
    with open(scenescript_path, 'r') as f:
        scenescript_data = json.load(f)
    
    # Load timing configuration
    from bin.core import load_modules_cfg
    timing_config = load_modules_cfg().get('timing', {})
    print(f"Timing config: {timing_config}")
    
    # Load brief
    from bin.core import load_brief
    brief = load_brief()
    print(f"Brief target: {brief.get('video', {}).get('target_length_min', 'unknown')} minutes")
    
    # Load grounded beats
    beats_path = Path("data/test_slug/grounded_beats.json")
    if beats_path.exists():
        with open(beats_path, 'r') as f:
            beats = json.load(f)
        
        print(f"Loaded {len(beats)} beats")
        for i, beat in enumerate(beats):
            duration_ms = beat.get('duration_ms', 0)
            print(f"  Beat {i}: {duration_ms}ms ({duration_ms/1000:.1f}s)")
        
        # Test duration computation
        durations, strategy, rationale = compute_scene_durations(beats, brief, timing_config, "test_slug")
        print(f"\nComputed durations: {durations}")
        print(f"Strategy: {strategy}")
        print(f"Rationale: {rationale}")
        
        total_ms = sum(durations)
        print(f"Total duration: {total_ms}ms ({total_ms/1000:.1f}s)")
        
        # Test tolerance validation
        target_min = brief.get('video', {}).get('target_length_min', 1.5)
        target_max = brief.get('video', {}).get('target_length_max', target_min)
        target_sec = target_min if target_min == target_max else (target_min + target_max) / 2
        target_ms = int(target_sec * 60 * 1000)
        
        is_valid, deviation, message = validate_duration_tolerance(total_ms, target_ms, 5.0)
        print(f"Tolerance validation: {is_valid} (deviation: {deviation:.1f}%) - {message}")
    
    print()

def test_acceptance_duration_validation():
    """Test acceptance duration validation"""
    print("Testing acceptance duration validation...")
    
    # Load the test SceneScript
    scenescript_path = Path("scenescripts/test_slug.json")
    if not scenescript_path.exists():
        print("SceneScript not found, skipping test")
        return
    
    with open(scenescript_path, 'r') as f:
        scenescript_data = json.load(f)
    
    # Create a mock acceptance validator
    from bin.core import load_config, load_blog_cfg
    cfg = load_config()
    blog_cfg = load_blog_cfg()
    
    validator = AcceptanceValidator(cfg, blog_cfg)
    
    # Test duration policy validation
    duration_result = validator._validate_duration_policy(scenescript_data)
    
    print(f"Duration validation result:")
    print(f"  Pass: {duration_result.get('pass', False)}")
    print(f"  Details: {duration_result.get('details', {})}")
    
    if duration_result.get('issues'):
        print(f"  Issues:")
        for issue in duration_result['issues']:
            print(f"    - {issue}")
    
    print()

if __name__ == "__main__":
    print("=== Duration Policy Test Suite ===\n")
    
    test_duration_tolerance()
    test_scene_duration_computation()
    test_acceptance_duration_validation()
    
    print("=== Test Suite Complete ===")
