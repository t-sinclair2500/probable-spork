#!/usr/bin/env python3
"""
Asset Librarian Resolver - Reuse-First Mapping to Concrete Assets

This module resolves storyboard placeholders into concrete asset files using the manifest.
Applies reuse-first policy, palette compliance, and size/pose constraints to produce
an asset plan with resolved assets and identified gaps.
"""

import argparse
import json
import logging
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.asset_manifest import AssetManifest

# Simple logging setup for standalone operation
def get_logger(name="asset_librarian"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger

log = get_logger("asset_librarian")


class AssetLibrarian:
    """Resolves storyboard placeholders into concrete asset files using the manifest."""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.manifest_path = self.base_dir / "data" / "library_manifest.json"
        self.runs_dir = self.base_dir / "runs"
        self.videos_dir = self.base_dir / "videos"
        
        # Ensure directories exist
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        
        # Load manifest
        self.manifest = self._load_manifest()
        
        # Load design language for palette validation
        self.design_language = self._load_design_language()
        
        # Load modules config for thresholds
        self.modules_config = self._load_modules_config()
    
    def _load_manifest(self) -> Dict[str, Any]:
        """Load the asset library manifest."""
        if not self.manifest_path.exists():
            log.error(f"Manifest not found: {self.manifest_path}")
            log.info("Run 'python bin/asset_manifest.py --rebuild' first")
            return {"assets": {}}
        
        try:
            with open(self.manifest_path, 'r') as f:
                manifest = json.load(f)
                log.info(f"[librarian] Loaded manifest with {len(manifest.get('assets', {}))} assets")
                return manifest
        except Exception as e:
            log.error(f"Failed to load manifest: {e}")
            return {"assets": {}}
    
    def _load_design_language(self) -> Dict[str, Any]:
        """Load design language configuration."""
        design_path = self.base_dir / "design" / "design_language.json"
        if not design_path.exists():
            log.warning(f"Design language not found: {design_path}")
            return {"colors": {}}
        
        try:
            with open(design_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load design language: {e}")
            return {"colors": {}}
    
    def _load_modules_config(self) -> Dict[str, Any]:
        """Load modules configuration."""
        # For now, return default values since we don't have complex config loading
        return {
            "reuse_threshold": 0.7,
            "generation_caps": {
                "max_new_assets": 10,
                "max_per_section": 3
            }
        }
    
    def _get_palette_colors(self) -> List[str]:
        """Get approved palette colors from design language."""
        colors = self.design_language.get("colors", {})
        return list(colors.values())
    
    def _is_palette_compliant(self, asset_colors: List[str]) -> bool:
        """Check if asset colors are palette compliant."""
        approved_colors = self._get_palette_colors()
        for color in asset_colors:
            if color not in approved_colors:
                return False
        return True
    
    def _find_matching_assets(
        self, 
        asset_type: str, 
        category: str, 
        style: Optional[str] = None,
        palette: Optional[List[str]] = None,
        size_constraints: Optional[Dict[str, float]] = None
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Find matching assets based on type, category, style, and constraints."""
        matches = []
        assets = self.manifest.get("assets", {})
        
        for asset_hash, asset in assets.items():
            # Check type match
            if asset_type not in asset.get("tags", []):
                continue
            
            # Check category match (in path or tags)
            asset_path = asset.get("path", "")
            if category.lower() not in asset_path.lower() and category.lower() not in str(asset.get("tags", [])).lower():
                continue
            
            # Check style match if specified
            if style and style.lower() not in asset_path.lower():
                continue
            
            # Check palette compliance if specified
            if palette:
                asset_colors = asset.get("palette", [])
                if not self._is_palette_compliant(asset_colors):
                    continue
            
            # Check size constraints if specified
            if size_constraints:
                asset_w = asset.get("w", 0)
                asset_h = asset.get("h", 0)
                if asset_w and asset_h:
                    # Check aspect ratio within ±20%
                    asset_aspect = asset_w / asset_h
                    target_aspect = size_constraints.get("w", 1) / size_constraints.get("h", 1)
                    if abs(asset_aspect - target_aspect) / target_aspect > 0.2:
                        continue
            
            # Calculate match score (lower is better)
            score = asset.get("usage_count", 0)  # Prefer less-used assets
            
            matches.append((asset_hash, asset, score))
        
        # Sort by score (lowest first) and return top matches
        matches.sort(key=lambda x: x[2])
        return [(hash_key, asset) for hash_key, asset, _ in matches]
    
    def _select_variant(self, asset: Dict[str, Any], requested_variants: Optional[List[str]] = None) -> str:
        """Select a variant for the asset based on requested variants."""
        if not requested_variants:
            return "default"
        
        # Check if asset has variant-specific tags
        asset_tags = asset.get("tags", [])
        for variant in requested_variants:
            if variant.lower() in str(asset_tags).lower():
                return variant
        
        # Default to first requested variant or "default"
        return requested_variants[0] if requested_variants else "default"
    
    def _calculate_scale(self, asset: Dict[str, Any], size_constraints: Optional[Dict[str, float]] = None) -> float:
        """Calculate appropriate scale for the asset."""
        if not size_constraints:
            return 1.0
        
        asset_w = asset.get("w", 0)
        asset_h = asset.get("h", 0)
        target_w = size_constraints.get("w", 0)
        target_h = size_constraints.get("h", 0)
        
        if not (asset_w and asset_h and target_w and target_h):
            return 1.0
        
        # Calculate scale to fit within constraints while maintaining aspect ratio
        scale_w = target_w / asset_w
        scale_h = target_h / asset_h
        scale = min(scale_w, scale_h)
        
        # Clamp scale to reasonable bounds
        return max(0.5, min(2.0, scale))
    
    def resolve_assets(
        self, 
        scenescript: Dict[str, Any], 
        manifest: Optional[Dict[str, Any]] = None,
        policy: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Resolve storyboard placeholders into concrete assets."""
        if manifest:
            self.manifest = manifest
        
        slug = scenescript.get("slug", "unknown")
        log.info(f"[librarian] Resolving assets for {slug}")
        
        # Create runs directory for this slug
        run_dir = self.runs_dir / slug
        run_dir.mkdir(parents=True, exist_ok=True)
        
        resolved = []
        gaps = []
        total_placeholders = 0
        
        # Process each scene
        for scene in scenescript.get("scenes", []):
            scene_id = scene.get("id", "unknown")
            
            # Check for background requirement
            bg_id = scene.get("bg")
            if bg_id:
                total_placeholders += 1
                bg_result = self._resolve_background(bg_id, scene_id)
                if bg_result:
                    resolved.append(bg_result)
                else:
                    gaps.append({
                        "element_id": f"{scene_id}_bg",
                        "spec": {
                            "category": "background",
                            "style": bg_id,
                            "palette": self._get_palette_colors()[:3],  # Limit to 3 colors
                            "notes": f"Background for scene {scene_id}"
                        }
                    })
            
            # Process scene elements
            for element in scene.get("elements", []):
                element_id = element.get("id", "unknown")
                element_type = element.get("type", "")
                
                if element_type in ["prop", "character"]:
                    total_placeholders += 1
                    element_result = self._resolve_element(element, scene_id)
                    if element_result:
                        resolved.append(element_result)
                    else:
                        gaps.append({
                            "element_id": element_id,
                            "spec": {
                                "category": element_type,
                                "style": element.get("style", "default"),
                                "palette": self._get_palette_colors()[:3],
                                "notes": f"{element_type.title()} for {element_id}"
                            }
                        })
        
        # Calculate reuse ratio
        reuse_ratio = len(resolved) / total_placeholders if total_placeholders > 0 else 0.0
        
        # Create asset plan
        asset_plan = {
            "slug": slug,
            "resolved": resolved,
            "gaps": gaps,
            "reuse_ratio": reuse_ratio,
            "total_placeholders": total_placeholders,
            "resolved_count": len(resolved),
            "gaps_count": len(gaps),
            "manifest_version": self.manifest.get("version", "unknown"),
            "generated_at": self._get_timestamp()
        }
        
        # Save asset plan
        plan_path = run_dir / "asset_plan.json"
        with open(plan_path, 'w') as f:
            json.dump(asset_plan, f, indent=2)
        
        log.info(f"[librarian] Asset plan saved to {plan_path}")
        log.info(f"[librarian] Resolved {len(resolved)}/{total_placeholders} assets (reuse ratio: {reuse_ratio:.2%})")
        
        # Update video metadata if it exists
        self._update_video_metadata(slug, asset_plan)
        
        return asset_plan
    
    def _resolve_background(self, bg_id: str, scene_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a background requirement."""
        log.debug(f"[librarian] Resolving background {bg_id} for scene {scene_id}")
        
        # Look for background assets
        matches = self._find_matching_assets("background", bg_id)
        
        if matches:
            asset_hash, asset = matches[0]
            variant = self._select_variant(asset)
            scale = self._calculate_scale(asset)
            
            # Update usage count
            asset["usage_count"] = asset.get("usage_count", 0) + 1
            asset["last_used"] = self._get_timestamp()
            
            log.info(f"[librarian] Reused background {asset['path']} for {bg_id}")
            
            return {
                "element_id": f"{scene_id}_bg",
                "asset": asset["path"],
                "scale": scale,
                "variant": variant,
                "asset_hash": asset_hash,
                "reuse_type": "existing"
            }
        
        return None
    
    def _resolve_element(self, element: Dict[str, Any], scene_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a prop or character element."""
        element_id = element.get("id", "unknown")
        element_type = element.get("type", "")
        
        log.debug(f"[librarian] Resolving {element_type} {element_id} for scene {scene_id}")
        
        # Extract style information from element
        style = element.get("style", {})
        if isinstance(style, dict):
            # Look for style hints in element metadata
            style_hints = []
            for key, value in style.items():
                if isinstance(value, str) and value.lower() in ["nelson", "eames", "midcentury", "atomic"]:
                    style_hints.append(value.lower())
        else:
            style_hints = [str(style).lower()]
        
        # Look for matching assets
        for style_hint in style_hints:
            matches = self._find_matching_assets(element_type, element_type, style_hint)
            if matches:
                asset_hash, asset = matches[0]
                variant = self._select_variant(asset)
                scale = self._calculate_scale(asset)
                
                # Update usage count
                asset["usage_count"] = asset.get("usage_count", 0) + 1
                asset["last_used"] = self._get_timestamp()
                
                log.info(f"[librarian] Reused {element_type} {asset['path']} for {element_id}")
                
                return {
                    "element_id": element_id,
                    "asset": asset["path"],
                    "scale": scale,
                    "variant": variant,
                    "asset_hash": asset_hash,
                    "reuse_type": "existing"
                }
        
        return None
    
    def _update_video_metadata(self, slug: str, asset_plan: Dict[str, Any]):
        """Update video metadata with asset information."""
        metadata_path = self.videos_dir / f"{slug}.metadata.json"
        
        if not metadata_path.exists():
            log.debug(f"Video metadata not found: {metadata_path}")
            return
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Add or update assets section
            metadata["assets"] = {
                "reuse_ratio": asset_plan["reuse_ratio"],
                "total_placeholders": asset_plan["total_placeholders"],
                "resolved_count": asset_plan["resolved_count"],
                "gaps_count": asset_plan["gaps_count"],
                "manifest_version": asset_plan["manifest_version"],
                "last_updated": self._get_timestamp()
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            log.info(f"[librarian] Updated video metadata: {metadata_path}")
            
        except Exception as e:
            log.warning(f"Failed to update video metadata: {e}")
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Asset Librarian Resolver")
    parser.add_argument("--slug", required=True, help="Slug of the content to resolve")
    parser.add_argument("--scenescript", help="Path to scenescript JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize librarian
    librarian = AssetLibrarian()
    
    # Load scenescript
    if args.scenescript:
        scenescript_path = Path(args.scenescript)
    else:
        scenescript_path = Path("scenescripts") / f"{args.slug}.json"
    
    if not scenescript_path.exists():
        log.error(f"Scenescript not found: {scenescript_path}")
        sys.exit(1)
    
    try:
        with open(scenescript_path, 'r') as f:
            scenescript = json.load(f)
    except Exception as e:
        log.error(f"Failed to load scenescript: {e}")
        sys.exit(1)
    
    # Resolve assets
    try:
        asset_plan = librarian.resolve_assets(scenescript)
        
        print(f"\nAsset Resolution Complete for {args.slug}")
        print(f"  Resolved: {asset_plan['resolved_count']}/{asset_plan['total_placeholders']}")
        print(f"  Reuse ratio: {asset_plan['reuse_ratio']:.2%}")
        print(f"  Gaps: {asset_plan['gaps_count']}")
        
        if asset_plan['gaps']:
            print(f"\nGaps identified:")
            for gap in asset_plan['gaps'][:5]:  # Show first 5
                print(f"  {gap['element_id']}: {gap['spec']['category']} - {gap['spec']['style']}")
            if len(asset_plan['gaps']) > 5:
                print(f"  ... and {len(asset_plan['gaps']) - 5} more")
        
        print(f"\nAsset plan saved to: runs/{args.slug}/asset_plan.json")
        
    except Exception as e:
        log.error(f"Asset resolution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
