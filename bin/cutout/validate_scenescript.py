#!/usr/bin/env python3
"""
SceneScript Validator - Validate SceneScript files against schema

Validates SceneScript JSON files against the schema and provides detailed feedback.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Union

# Ensure repo root on path
ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.cutout.sdk import validate_scene_script, SceneScript


def validate_schema(data: Dict) -> List[str]:
    """Validate data against SceneScript schema."""
    errors = []
    
    # Basic structure checks
    required_fields = ["slug", "fps", "scenes"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    if errors:
        return errors
    
    # Type checks
    if not isinstance(data["slug"], str):
        errors.append("slug must be a string")
    
    if not isinstance(data["fps"], int) or data["fps"] <= 0:
        errors.append("fps must be a positive integer")
    
    if not isinstance(data["scenes"], list) or len(data["scenes"]) == 0:
        errors.append("scenes must be a non-empty array")
    
    # Scene validation
    for i, scene in enumerate(data["scenes"]):
        if not isinstance(scene, dict):
            errors.append(f"Scene {i} must be an object")
            continue
        
        scene_errors = validate_scene(scene, i)
        errors.extend(scene_errors)
    
    return errors


def validate_scene(scene: Dict, scene_index: int) -> List[str]:
    """Validate a single scene."""
    errors = []
    
    # Required scene fields
    required_fields = ["id", "duration_ms", "bg", "elements"]
    for field in required_fields:
        if field not in scene:
            errors.append(f"Scene {scene_index}: Missing required field: {field}")
    
    if errors:
        return errors
    
    # Type checks
    if not isinstance(scene["id"], str):
        errors.append(f"Scene {scene_index}: id must be a string")
    
    if not isinstance(scene["duration_ms"], int) or scene["duration_ms"] <= 0:
        errors.append(f"Scene {scene_index}: duration_ms must be a positive integer")
    
    if not isinstance(scene["bg"], str):
        errors.append(f"Scene {scene_index}: bg must be a string")
    
    if not isinstance(scene["elements"], list):
        errors.append(f"Scene {scene_index}: elements must be an array")
    
    # Duration bounds check using configurable timing
    try:
        from bin.core import load_modules_cfg
        timing_config = load_modules_cfg().get('timing', {})
        min_scene_ms = timing_config.get('min_scene_ms', 2500)
        max_scene_ms = timing_config.get('max_scene_ms', 30000)
    except Exception:
        # Fallback to reasonable defaults
        min_scene_ms = 2500
        max_scene_ms = 30000
    
    duration_sec = scene["duration_ms"] / 1000
    if scene["duration_ms"] < min_scene_ms or scene["duration_ms"] > max_scene_ms:
        errors.append(f"Scene {scene_index}: duration {duration_sec:.1f}s outside {min_scene_ms/1000:.1f}-{max_scene_ms/1000:.1f}s bounds")
    
    # Element validation
    for j, element in enumerate(scene["elements"]):
        if not isinstance(element, dict):
            errors.append(f"Scene {scene_index}, Element {j}: Must be an object")
            continue
        
        element_errors = validate_element(element, scene_index, j)
        errors.extend(element_errors)
    
    return errors


def validate_element(element: Dict, scene_index: int, element_index: int) -> List[str]:
    """Validate a single element."""
    errors = []
    
    # Required element fields
    required_fields = ["id", "type"]
    for field in required_fields:
        if field not in element:
            errors.append(f"Scene {scene_index}, Element {element_index}: Missing required field: {field}")
    
    if errors:
        return errors
    
    # Type checks
    if not isinstance(element["id"], str):
        errors.append(f"Scene {scene_index}, Element {element_index}: id must be a string")
    
    valid_types = ["text", "prop", "character", "list_step", "shape", "lower_third", "counter"]
    if element["type"] not in valid_types:
        errors.append(f"Scene {scene_index}, Element {element_index}: type must be one of {valid_types}")
    
    # Text content validation
    if element["type"] == "text" and "content" in element:
        content = element["content"]
        if content and isinstance(content, str):
            word_count = len(content.split())
            if word_count > 12:  # MAX_WORDS_PER_CARD
                errors.append(f"Scene {scene_index}, Element {element_index}: Text has {word_count} words, exceeds 12 word limit")
    
    # Position validation
    if "x" in element and not isinstance(element["x"], (int, float)):
        errors.append(f"Scene {scene_index}, Element {element_index}: x must be a number")
    
    if "y" in element and not isinstance(element["y"], (int, float)):
        errors.append(f"Scene {scene_index}, Element {element_index}: y must be a number")
    
    # Keyframe validation
    if "keyframes" in element:
        keyframes = element["keyframes"]
        if not isinstance(keyframes, list):
            errors.append(f"Scene {scene_index}, Element {element_index}: keyframes must be an array")
        else:
            for k, keyframe in enumerate(keyframes):
                if not isinstance(keyframe, dict):
                    errors.append(f"Scene {scene_index}, Element {element_index}, Keyframe {k}: Must be an object")
                    continue
                
                keyframe_errors = validate_keyframe(keyframe, scene_index, element_index, k)
                errors.extend(keyframe_errors)
    
    return errors


def validate_keyframe(keyframe: Dict, scene_index: int, element_index: int, keyframe_index: int) -> List[str]:
    """Validate a single keyframe."""
    errors = []
    
    # Required keyframe fields
    if "t" not in keyframe:
        errors.append(f"Scene {scene_index}, Element {element_index}, Keyframe {keyframe_index}: Missing required field: t")
        return errors
    
    # Type checks
    if not isinstance(keyframe["t"], int) or keyframe["t"] < 0:
        errors.append(f"Scene {scene_index}, Element {element_index}, Keyframe {keyframe_index}: t must be a non-negative integer")
    
    # Opacity validation
    if "opacity" in keyframe:
        opacity = keyframe["opacity"]
        if not isinstance(opacity, (int, float)) or opacity < 0 or opacity > 1:
            errors.append(f"Scene {scene_index}, Element {element_index}, Keyframe {keyframe_index}: opacity must be between 0.0 and 1.0")
    
    # Scale validation
    if "scale" in keyframe and keyframe["scale"] is not None:
        scale = keyframe["scale"]
        if not isinstance(scale, (int, float)) or scale < 0:
            errors.append(f"Scene {scene_index}, Element {element_index}, Keyframe {keyframe_index}: scale must be non-negative")
    
    return errors


def main():
    """Main entry point for SceneScript validation."""
    parser = argparse.ArgumentParser(description="Validate SceneScript files")
    parser.add_argument("--in", dest="input_file", required=True, help="Input SceneScript JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    try:
        with open(input_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {input_path}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to read {input_path}: {e}")
        sys.exit(1)
    
    print(f"Validating SceneScript: {input_path}")
    
    # Validate against schema
    schema_errors = validate_schema(data)
    
    if schema_errors:
        print(f"\n❌ Schema validation failed with {len(schema_errors)} errors:")
        for error in schema_errors:
            print(f"  - {error}")
        sys.exit(1)
    
    # Validate using SDK
    try:
        scene_script = validate_scene_script(data)
        print(f"\n✅ Schema validation passed")
        
        if args.verbose:
            print(f"\nSceneScript details:")
            print(f"  Slug: {scene_script.slug}")
            print(f"  FPS: {scene_script.fps}")
            print(f"  Scenes: {len(scene_script.scenes)}")
            
            total_duration = sum(scene.duration_ms for scene in scene_script.scenes) / 1000
            print(f"  Total duration: {total_duration:.1f}s")
            
            # Duration compliance metrics using configurable bounds
            try:
                from bin.core import load_config
                cfg = load_config()
                timing_config = getattr(cfg, 'timing', {})
                min_scene_ms = timing_config.get('min_scene_ms', 2500)
                max_scene_ms = timing_config.get('max_scene_ms', 12000)
            except Exception:
                # Fallback to reasonable defaults
                min_scene_ms = 2500
                max_scene_ms = 12000
            
            scenes_within_bounds = sum(1 for s in scene_script.scenes if min_scene_ms <= s.duration_ms <= max_scene_ms)
            compliance_percent = (scenes_within_bounds / len(scene_script.scenes) * 100) if scene_script.scenes else 0
            print(f"  Duration compliance: {compliance_percent:.1f}% within {min_scene_ms}-{max_scene_ms}ms bounds")
            
            # Check for scenes outside bounds
            out_of_bounds = []
            for scene in scene_script.scenes:
                if scene.duration_ms < min_scene_ms or scene.duration_ms > max_scene_ms:
                    out_of_bounds.append(f"{scene.id}: {scene.duration_ms}ms")
            
            if out_of_bounds:
                print(f"  Out of bounds scenes: {', '.join(out_of_bounds)}")
            
            # Text truncation check
            truncation_count = 0
            for scene in scene_script.scenes:
                for element in scene.elements:
                    if element.type == "text" and element.content:
                        word_count = len(element.content.split())
                        if word_count > 12:
                            truncation_count += 1
            
            if truncation_count > 0:
                print(f"  Text truncations: {truncation_count} elements exceed 12 word limit")
            else:
                print(f"  Text compliance: All elements within 12 word limit")
        
    except Exception as e:
        print(f"\n❌ SDK validation failed: {e}")
        sys.exit(1)
    
    print("\n🎉 SceneScript validation completed successfully!")


if __name__ == "__main__":
    main()
