#!/usr/bin/env python3
"""
Storyboard Reflow with Concrete Assets + QA

This module takes resolved asset plans and reflows storyboards with concrete asset sizes,
applying layout constraints and running QA checks for collisions and contrast.
"""

import json
import logging
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bin.core import get_logger
from bin.cutout.sdk import (
    SceneScript, Scene, Element, VIDEO_W, VIDEO_H, SAFE_MARGINS_PX,
    load_scene_script, save_scene_script
)
from bin.cutout.layout_engine import LayoutEngine
from bin.cutout.qa_gates import check_collisions, check_contrast, QAResult

log = get_logger("storyboard_reflow")


class StoryboardReflow:
    """Handles storyboard reflow with concrete assets and QA validation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize reflow engine with configuration."""
        self.config = config or {}
        
        # Default configuration
        self.max_attempts = self.config.get("max_attempts", 3)
        self.max_scale_reduction = self.config.get("max_scale_reduction", 0.1)  # 10%
        self.max_nudge_distance = self.config.get("max_nudge_distance", 12)  # 12px
        self.min_spacing = self.config.get("min_spacing", 64)  # 64px
        
        # Layout engine
        self.layout_engine = LayoutEngine()
    
    def _get_asset_dimensions(self, asset_path: str) -> Tuple[float, float]:
        """
        Get actual dimensions of an SVG asset.
        
        Args:
            asset_path: Path to the SVG asset
            
        Returns:
            Tuple of (width, height) in pixels
        """
        try:
            # Try to parse SVG to get viewBox or dimensions
            with open(asset_path, 'r') as f:
                content = f.read()
            
            # Look for viewBox attribute
            if 'viewBox=' in content:
                import re
                viewbox_match = re.search(r'viewBox=["\']([^"\']+)["\']', content)
                if viewbox_match:
                    viewbox = viewbox_match.group(1).split()
                    if len(viewbox) >= 4:
                        w = float(viewbox[2])
                        h = float(viewbox[3])
                        return w, h
            
            # Look for width/height attributes
            width_match = re.search(r'width=["\']([^"\']+)["\']', content)
            height_match = re.search(r'height=["\']([^"\']+)["\']', content)
            
            if width_match and height_match:
                w = float(width_match.group(1))
                h = float(height_match.group(1))
                return w, h
            
            # Default dimensions if parsing fails
            log.warning(f"Could not parse dimensions from {asset_path}, using defaults")
            return 200.0, 200.0
            
        except Exception as e:
            log.warning(f"Failed to get dimensions for {asset_path}: {e}, using defaults")
            return 200.0, 200.0
    
    def _apply_asset_dimensions(self, scene: Dict[str, Any], asset_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace placeholder dimensions with concrete asset dimensions.
        
        Args:
            scene: Scene dictionary
            asset_plan: Resolved asset plan
            
        Returns:
            Scene with updated element dimensions
        """
        updated_scene = scene.copy()
        updated_elements = []
        
        # Create lookup for asset plan
        asset_lookup = {}
        for item in asset_plan.get("resolved", []):
            element_id = item["element_id"]
            asset_lookup[element_id] = item
        
        for element in scene.get("elements", []):
            element_id = element.get("id")
            updated_element = element.copy()
            
            # Check if this element has a resolved asset
            if element_id in asset_lookup:
                asset_item = asset_lookup[element_id]
                asset_path = asset_item["asset"]
                
                # Get actual asset dimensions
                width, height = self._get_asset_dimensions(asset_path)
                
                # Apply scale from asset plan
                scale = asset_item.get("scale", 1.0)
                width *= scale
                height *= scale
                
                # Update element with concrete dimensions
                updated_element["width"] = width
                updated_element["height"] = height
                updated_element["asset_path"] = asset_path
                updated_element["asset_hash"] = asset_item.get("asset_hash", "")
                
                log.debug(f"[reflow] Element {element_id}: {width:.1f}x{height:.1f} (scale: {scale})")
            
            updated_elements.append(updated_element)
        
        updated_scene["elements"] = updated_elements
        return updated_scene
    
    def _check_element_collisions(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Check for collisions between elements.
        
        Args:
            elements: List of scene elements
            
        Returns:
            List of collision pairs
        """
        collisions = []
        
        for i, elem1 in enumerate(elements):
            if "width" not in elem1 or "height" not in elem1:
                continue
                
            x1, y1 = elem1.get("x", 0), elem1.get("y", 0)
            w1, h1 = elem1["width"], elem1["height"]
            
            # Skip elements without valid dimensions
            if w1 is None or h1 is None:
                continue
            
            # Calculate bounding box
            left1, right1 = x1 - w1/2, x1 + w1/2
            top1, bottom1 = y1 - h1/2, y1 + h1/2
            
            for j, elem2 in enumerate(elements[i+1:], i+1):
                if "width" not in elem2 or "height" not in elem2:
                    continue
                    
                x2, y2 = elem2.get("x", 0), elem2.get("y", 0)
                w2, h2 = elem2["width"], elem2["height"]
                
                # Skip elements without valid dimensions
                if w2 is None or h2 is None:
                    continue
                
                # Calculate bounding box
                left2, right2 = x2 - w2/2, x2 + w2/2
                top2, bottom2 = y2 - h2/2, y2 + h2/2
                
                # Check for overlap
                if not (right1 < left2 or left1 > right2 or bottom1 < top2 or top1 > bottom2):
                    # Collision detected
                    collision = {
                        "element1": elem1.get("id", f"element_{i}"),
                        "element2": elem2.get("id", f"element_{j}"),
                        "overlap": {
                            "x": max(left1, left2) - min(right1, right2),
                            "y": max(top1, top2) - min(bottom1, bottom2)
                        }
                    }
                    collisions.append(collision)
        
        return collisions
    
    def _apply_layout_constraints(self, scene: Dict[str, Any], seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Apply layout constraints to resolve collisions and respect safe margins.
        
        Args:
            scene: Scene with elements
            seed: Random seed for deterministic layout
            
        Returns:
            Scene with updated element positions
        """
        if seed is not None:
            random.seed(seed)
        
        updated_scene = scene.copy()
        elements = updated_scene["elements"]
        
        # Separate elements by type
        text_elements = [e for e in elements if e.get("type") == "text"]
        asset_elements = [e for e in elements if e.get("type") in ["prop", "character", "shape"]]
        
        # Apply constraints to asset elements first
        if asset_elements:
            self._constrain_asset_elements(asset_elements, seed)
        
        # Apply constraints to text elements
        if text_elements:
            self._constrain_text_elements(text_elements, asset_elements)
        
        # Reset random seed
        if seed is not None:
            random.seed()
        
        return updated_scene
    
    def _constrain_asset_elements(self, elements: List[Dict[str, Any]], seed: Optional[int] = None):
        """Apply constraints to asset elements to avoid collisions."""
        attempts = 0
        max_attempts = 10
        
        while attempts < max_attempts:
            collisions = self._check_element_collisions(elements)
            if not collisions:
                break
            
            log.debug(f"[reflow] Attempt {attempts + 1}: {len(collisions)} collisions detected")
            
            # Try to resolve collisions
            for collision in collisions:
                elem1_id = collision["element1"]
                elem2_id = collision["element2"]
                
                elem1 = next((e for e in elements if e.get("id") == elem1_id), None)
                elem2 = next((e for e in elements if e.get("id") == elem2_id), None)
                
                if elem1 and elem2:
                    self._resolve_collision(elem1, elem2, seed)
            
            attempts += 1
        
        if attempts >= max_attempts:
            log.warning(f"[reflow] Failed to resolve all collisions after {max_attempts} attempts")
    
    def _resolve_collision(self, elem1: Dict[str, Any], elem2: Dict[str, Any], seed: Optional[int] = None):
        """Resolve collision between two elements."""
        # Calculate separation vector
        dx = elem2.get("x", 0) - elem1.get("x", 0)
        dy = elem2.get("y", 0) - elem1.get("y", 0)
        
        # Calculate required separation
        w1, h1 = elem1.get("width", 100), elem1.get("height", 100)
        w2, h2 = elem2.get("width", 100), elem2.get("height", 100)
        
        required_sep_x = (w1 + w2) / 2 + self.min_spacing
        required_sep_y = (h1 + h2) / 2 + self.min_spacing
        
        # Calculate current separation
        current_sep_x = abs(dx)
        current_sep_y = abs(dy)
        
        # Determine which direction to move
        if current_sep_x < required_sep_x:
            # Move horizontally
            move_distance = required_sep_x - current_sep_x
            if dx > 0:
                # elem2 is to the right, move it further right
                elem2["x"] += move_distance
            else:
                # elem2 is to the left, move it further left
                elem2["x"] -= move_distance
        
        if current_sep_y < required_sep_y:
            # Move vertically
            move_distance = required_sep_y - current_sep_y
            if dy > 0:
                # elem2 is below, move it further down
                elem2["y"] += move_distance
            else:
                # elem2 is above, move it further up
                elem2["y"] -= move_distance
        
        # Ensure elements stay within safe margins
        self._constrain_to_safe_area(elem2)
    
    def _constrain_to_safe_area(self, element: Dict[str, Any]):
        """Ensure element stays within safe margins."""
        x, y = element.get("x", 0), element.get("y", 0)
        w, h = element.get("width", 100), element.get("height", 100)
        
        # Calculate bounds
        left = x - w/2
        right = x + w/2
        top = y - h/2
        bottom = y + h/2
        
        # Constrain to safe area
        if left < SAFE_MARGINS_PX:
            element["x"] = SAFE_MARGINS_PX + w/2
        elif right > VIDEO_W - SAFE_MARGINS_PX:
            element["x"] = VIDEO_W - SAFE_MARGINS_PX - w/2
        
        if top < SAFE_MARGINS_PX:
            element["y"] = SAFE_MARGINS_PX + h/2
        elif bottom > VIDEO_H - SAFE_MARGINS_PX:
            element["y"] = VIDEO_H - SAFE_MARGINS_PX - h/2
    
    def _constrain_text_elements(self, text_elements: List[Dict[str, Any]], asset_elements: List[Dict[str, Any]]):
        """Apply constraints to text elements to avoid assets."""
        for text_elem in text_elements:
            # Ensure text doesn't overlap with assets
            for asset_elem in asset_elements:
                if self._elements_overlap(text_elem, asset_elem):
                    # Move text element to avoid overlap
                    self._move_text_away_from_asset(text_elem, asset_elem)
    
    def _elements_overlap(self, elem1: Dict[str, Any], elem2: Dict[str, Any]) -> bool:
        """Check if two elements overlap."""
        x1, y1 = elem1.get("x", 0), elem1.get("y", 0)
        w1, h1 = elem1.get("width", 100), elem1.get("height", 100)
        
        x2, y2 = elem2.get("x", 0), elem2.get("y", 0)
        w2, h2 = elem2.get("width", 100), elem2.get("height", 100)
        
        # Skip elements without valid dimensions
        if w1 is None or h1 is None or w2 is None or h2 is None:
            return False
        
        # Calculate bounding boxes
        left1, right1 = x1 - w1/2, x1 + w1/2
        top1, bottom1 = y1 - h1/2, y1 + h1/2
        
        left2, right2 = x2 - w2/2, x2 + w2/2
        top2, bottom2 = y2 - h2/2, y2 + h2/2
        
        # Check for overlap
        return not (right1 < left2 or left1 > right2 or bottom1 < top2 or top1 > bottom2)
    
    def _move_text_away_from_asset(self, text_elem: Dict[str, Any], asset_elem: Dict[str, Any]):
        """Move text element away from asset to avoid overlap."""
        # Simple strategy: move text to opposite side of asset
        asset_x, asset_y = asset_elem.get("x", 0), asset_elem.get("y", 0)
        text_x, text_y = text_elem.get("x", 0), text_elem.get("y", 0)
        
        # Calculate direction vector
        dx = text_x - asset_x
        dy = text_y - asset_y
        
        # Normalize and scale
        length = math.sqrt(dx*dx + dy*dy)
        if length > 0:
            dx = dx / length * 100  # Move 100px away
            dy = dy / length * 100
            
            text_elem["x"] = asset_x + dx
            text_elem["y"] = asset_y + dy
            
            # Ensure text stays within safe area
            self._constrain_to_safe_area(text_elem)
    
    def _run_qa_checks(self, scene: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run QA checks on the reflowed scene.
        
        Args:
            scene: Scene to check
            
        Returns:
            QA results dictionary
        """
        qa_results = {
            "collisions": [],
            "contrast": {},
            "safe_margins": {},
            "overall_status": "pass"
        }
        
        # Check for collisions
        elements = scene.get("elements", [])
        collisions = self._check_element_collisions(elements)
        qa_results["collisions"] = collisions
        
        if collisions:
            qa_results["overall_status"] = "fail"
            log.warning(f"[qa-assets] {len(collisions)} collisions detected in scene {scene.get('id', 'unknown')}")
        
        # Check safe margins
        margin_violations = []
        for element in elements:
            x, y = element.get("x", 0), element.get("y", 0)
            w, h = element.get("width", 100), element.get("height", 100)
            
            # Skip elements without valid dimensions
            if w is None or h is None:
                continue
            
            left = x - w/2
            right = x + w/2
            top = y - h/2
            bottom = y + h/2
            
            if (left < SAFE_MARGINS_PX or right > VIDEO_W - SAFE_MARGINS_PX or 
                top < SAFE_MARGINS_PX or bottom > VIDEO_H - SAFE_MARGINS_PX):
                margin_violations.append({
                    "element_id": element.get("id", "unknown"),
                    "bounds": {"left": left, "right": right, "top": top, "bottom": bottom},
                    "safe_area": {"left": SAFE_MARGINS_PX, "right": VIDEO_W - SAFE_MARGINS_PX, 
                                 "top": SAFE_MARGINS_PX, "bottom": VIDEO_H - SAFE_MARGINS_PX}
                })
        
        qa_results["safe_margins"] = {
            "violations": margin_violations,
            "status": "pass" if not margin_violations else "fail"
        }
        
        if margin_violations:
            qa_results["overall_status"] = "fail"
            log.warning(f"[qa-assets] {len(margin_violations)} margin violations in scene {scene.get('id', 'unknown')}")
        
        # Note: Contrast checking would require more complex color analysis
        # For now, we'll mark it as not implemented
        qa_results["contrast"] = {
            "status": "not_implemented",
            "note": "Contrast checking requires color analysis of assets"
        }
        
        return qa_results
    
    def reflow_with_assets(self, scenescript: Union[str, Dict], asset_plan: Union[str, Dict], 
                          config: Optional[Dict[str, Any]] = None, 
                          seed: Optional[int] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Reflow storyboard with concrete assets and run QA checks.
        
        Args:
            scenescript: SceneScript file path or dictionary
            asset_plan: Asset plan file path or dictionary
            config: Configuration dictionary
            seed: Random seed for deterministic reflow
            
        Returns:
            Tuple of (updated_scenescript, reflow_summary)
        """
        log.info(f"[reflow] Starting storyboard reflow with seed {seed}")
        
        # Load scenescript
        if isinstance(scenescript, str):
            scenescript_path = Path(scenescript)
            if not scenescript_path.exists():
                raise FileNotFoundError(f"SceneScript not found: {scenescript}")
            scenescript_data = load_scene_script(scenescript_path)
        else:
            scenescript_data = scenescript
        
        # Load asset plan
        if isinstance(asset_plan, str):
            asset_plan_path = Path(asset_plan)
            if not asset_plan_path.exists():
                raise FileNotFoundError(f"Asset plan not found: {asset_plan}")
            with open(asset_plan_path, 'r') as f:
                asset_plan_data = json.load(f)
        else:
            asset_plan_data = asset_plan
        
        # Update configuration
        if config:
            self.config.update(config)
        
        # Process each scene
        updated_scenes = []
        reflow_summary = {
            "slug": getattr(scenescript_data, "slug", "unknown"),
            "scenes": [],
            "overall_status": "pass",
            "total_collisions": 0,
            "total_margin_violations": 0
        }
        
        for scene in getattr(scenescript_data, "scenes", []):
            scene_id = getattr(scene, "id", "unknown")
            log.info(f"[reflow] Processing scene: {scene_id}")
            
            # Store original scene state
            original_elements = getattr(scene, "elements", [])
            original_bboxes = []
            for elem in original_elements:
                original_bboxes.append({
                    "element_id": getattr(elem, "id", "unknown"),
                    "x": getattr(elem, "x", 0),
                    "y": getattr(elem, "y", 0),
                    "width": getattr(elem, "width", 100),
                    "height": getattr(elem, "height", 100)
                })
            
            # Convert scene to dict for processing
            scene_dict = scene.dict()
            
            # Apply asset dimensions
            updated_scene = self._apply_asset_dimensions(scene_dict, asset_plan_data)
            
            # Apply layout constraints
            updated_scene = self._apply_layout_constraints(updated_scene, seed)
            
            # Run QA checks
            qa_results = self._run_qa_checks(updated_scene)
            
            # Store final scene state
            final_elements = updated_scene.get("elements", [])
            final_bboxes = []
            for elem in final_elements:
                final_bboxes.append({
                    "element_id": elem.get("id", "unknown"),
                    "x": elem.get("x", 0),
                    "y": elem.get("y", 0),
                    "width": elem.get("width", 100),
                    "height": elem.get("height", 100)
                })
            
            # Create scene summary
            scene_summary = {
                "scene_id": scene_id,
                "original_bboxes": original_bboxes,
                "final_bboxes": final_bboxes,
                "qa_results": qa_results,
                "status": qa_results["overall_status"]
            }
            
            reflow_summary["scenes"].append(scene_summary)
            
            # Update overall status
            if qa_results["overall_status"] == "fail":
                reflow_summary["overall_status"] = "fail"
            
            # Count violations
            reflow_summary["total_collisions"] += len(qa_results["collisions"])
            reflow_summary["total_margin_violations"] += len(qa_results["safe_margins"]["violations"])
            
            updated_scenes.append(updated_scene)
        
        # Create updated scenescript
        updated_scenescript = scenescript_data.dict()
        updated_scenescript["scenes"] = updated_scenes
        
        log.info(f"[reflow] Reflow completed. Overall status: {reflow_summary['overall_status']}")
        log.info(f"[reflow] Total collisions: {reflow_summary['total_collisions']}")
        log.info(f"[reflow] Total margin violations: {reflow_summary['total_margin_violations']}")
        
        return updated_scenescript, reflow_summary


def main():
    """Main CLI entry point for storyboard reflow."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Reflow storyboard with concrete assets")
    parser.add_argument("--slug", required=True, help="Slug of the content to reflow")
    parser.add_argument("--output", help="Output path for updated SceneScript")
    parser.add_argument("--summary", help="Output path for reflow summary")
    parser.add_argument("--seed", type=int, help="Random seed for deterministic reflow")
    parser.add_argument("--config", help="Path to configuration JSON")
    
    args = parser.parse_args()
    
    try:
        # Auto-detect paths based on slug
        scenescript_path = Path("scenescripts") / f"{args.slug}.json"
        asset_plan_path = Path("runs") / args.slug / "asset_plan.json"
        
        if not scenescript_path.exists():
            log.error(f"Scenescript not found: {scenescript_path}")
            sys.exit(1)
        
        if not asset_plan_path.exists():
            log.error(f"Asset plan not found: {asset_plan_path}")
            sys.exit(1)
        
        # Load configuration
        config = {}
        if args.config:
            with open(args.config, 'r') as f:
                config = json.load(f)
        
        # Initialize reflow engine
        reflow_engine = StoryboardReflow(config)
        
        # Run reflow
        updated_scenescript, reflow_summary = reflow_engine.reflow_with_assets(
            str(scenescript_path), str(asset_plan_path), config, args.seed
        )
        
        # Save updated scenescript
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(updated_scenescript, f, indent=2)
            print(f"Updated SceneScript saved to: {output_path}")
        else:
            # Save to runs directory
            runs_dir = Path("runs") / args.slug
            runs_dir.mkdir(parents=True, exist_ok=True)
            output_path = runs_dir / f"{args.slug}_reflowed.json"
            with open(output_path, 'w') as f:
                json.dump(updated_scenescript, f, indent=2)
            print(f"Updated SceneScript saved to: {output_path}")
        
        # Save reflow summary
        if args.summary:
            summary_path = Path(args.summary)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            with open(summary_path, 'w') as f:
                json.dump(reflow_summary, f, indent=2)
            print(f"Reflow summary saved to: {summary_path}")
        else:
            # Save to runs directory
            runs_dir = Path("runs") / args.slug
            runs_dir.mkdir(parents=True, exist_ok=True)
            summary_path = runs_dir / "reflow_summary.json"
            with open(summary_path, 'w') as f:
                json.dump(reflow_summary, f, indent=2)
            print(f"Reflow summary saved to: {summary_path}")
        
        # Print summary
        print(f"\nReflow Summary:")
        print(f"  Overall Status: {reflow_summary['overall_status']}")
        print(f"  Total Collisions: {reflow_summary['total_collisions']}")
        print(f"  Total Margin Violations: {reflow_summary['total_margin_violations']}")
        
        if reflow_summary['overall_status'] == 'pass':
            print("All QA checks passed!")
        else:
            print("Some QA checks failed. Check the summary for details.")
            
    except Exception as e:
        log.error(f"Storyboard reflow failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
