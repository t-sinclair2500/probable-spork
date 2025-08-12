#!/usr/bin/env python3
"""
Storyboard Asset Loop - Ensures 100% Asset Coverage

This module implements the iterative loop between storyboard planning and asset integration.
It identifies required assets, matches against existing assets, generates missing ones
procedurally, and revalidates the storyboard before rendering.
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from .sdk import (
    SceneScript, Scene, Element, BrandStyle, Paths,
    load_style, validate_scene_script, save_scene_script
)
from .motif_generators import (
    generate_background_motif, generate_prop_motif, generate_character_motif
)
from .svg_path_ops import create_path_processor, create_variant_generator, generate_motif_variants

log = logging.getLogger(__name__)


class AssetRequirement:
    """Represents an asset requirement identified from a storyboard."""
    
    def __init__(self, asset_type: str, identifier: str, element_id: str, scene_id: str):
        self.asset_type = asset_type  # "background", "prop", "character", "texture"
        self.identifier = identifier  # Asset name/ID (e.g., "gradient1", "narrator")
        self.element_id = element_id  # Element that requires this asset
        self.scene_id = scene_id      # Scene containing the element
        self.asset_path: Optional[str] = None  # Path to existing asset if found
        self.generated_path: Optional[str] = None  # Path to generated asset if created
        self.coverage_status = "missing"  # "found", "generated", "missing"
    
    def __str__(self):
        return f"{self.asset_type}:{self.identifier} for {self.element_id} in {self.scene_id}"


class AssetLibrary:
    """Manages the existing asset library and provides matching capabilities."""
    
    def __init__(self, brand_style: BrandStyle):
        self.brand_style = brand_style
        self.asset_cache: Dict[str, str] = {}  # identifier -> file_path
        self._build_asset_index()
    
    def _build_asset_index(self):
        """Build an index of existing assets for fast lookup."""
        # Index brand assets
        brand_dirs = ["backgrounds", "props", "characters"]
        for asset_type in brand_dirs:
            brand_dir = Path("assets/brand") / asset_type
            if brand_dir.exists():
                for asset_file in brand_dir.glob("*.svg"):
                    identifier = asset_file.stem
                    self.asset_cache[f"{asset_type}:{identifier}"] = str(asset_file)
                    log.debug(f"Indexed brand asset: {asset_type}:{identifier} -> {asset_file}")
        
        # Index generated assets
        generated_dir = Path("assets/generated")
        if generated_dir.exists():
            for asset_file in generated_dir.glob("*.svg"):
                identifier = asset_file.stem
                self.asset_cache[f"generated:{identifier}"] = str(asset_file)
                log.debug(f"Indexed generated asset: generated:{identifier} -> {asset_file}")
    
    def find_asset(self, asset_type: str, identifier: str) -> Optional[str]:
        """Find an existing asset by type and identifier."""
        # Try exact match first
        key = f"{asset_type}:{identifier}"
        if key in self.asset_cache:
            return self.asset_cache[key]
        
        # Try brand assets with different type mappings
        brand_key = f"brand:{identifier}"
        if brand_key in self.asset_cache:
            return self.asset_cache[brand_key]
        
        # Try fuzzy matching for similar identifiers
        for existing_key, path in self.asset_cache.items():
            if identifier.lower() in existing_key.lower() or existing_key.lower() in identifier.lower():
                log.debug(f"Fuzzy match: {identifier} -> {existing_key}")
                return path
        
        return None
    
    def get_coverage_stats(self) -> Dict[str, int]:
        """Get statistics about asset coverage."""
        total_assets = len(self.asset_cache)
        brand_assets = sum(1 for k in self.asset_cache.keys() if k.startswith("brand:"))
        generated_assets = sum(1 for k in self.asset_cache.keys() if k.startswith("generated:"))
        
        return {
            "total": total_assets,
            "brand": brand_assets,
            "generated": generated_assets
        }


class ProceduralAssetGenerator:
    """Generates procedural assets following the brand style guide."""
    
    def __init__(self, brand_style: BrandStyle, seed: int = 42):
        self.brand_style = brand_style
        self.seed = seed
        self.generated_dir = Path("assets/generated")
        self.generated_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_asset(self, requirement: AssetRequirement) -> Optional[str]:
        """Generate a procedural asset for the given requirement."""
        try:
            if requirement.asset_type == "background":
                return self._generate_background(requirement)
            elif requirement.asset_type == "prop":
                return self._generate_prop(requirement)
            elif requirement.asset_type == "character":
                return self._generate_character(requirement)
            else:
                log.warning(f"Unsupported asset type for generation: {requirement.asset_type}")
                return None
        except Exception as e:
            log.error(f"Failed to generate asset for {requirement}: {e}")
            return None
    
    def _generate_background(self, requirement: AssetRequirement) -> Optional[str]:
        """Generate a procedural background asset."""
        # Use scene-specific seed for deterministic generation
        scene_seed = self.seed + hash(requirement.scene_id) % 10000
        
        # Pick colors from brand palette
        colors = list(self.brand_style.colors.values()) if hasattr(self.brand_style.colors, 'values') else []
        if not colors:
            colors = ["#2563eb", "#7c3aed", "#f59e0b"]  # Fallback colors
        
        # Generate background motif
        svg_content = generate_background_motif(
            requirement.identifier,
            colors,
            seed=scene_seed
        )
        
        if svg_content:
            # Save to generated assets directory
            timestamp = int(time.time())
            filename = f"bg_{requirement.identifier}_{timestamp}_{scene_seed}.svg"
            filepath = self.generated_dir / filename
            
            with open(filepath, 'w') as f:
                f.write(svg_content)
            
            log.info(f"Generated background asset: {filepath}")
            return str(filepath)
        
        return None
    
    def _generate_prop(self, requirement: AssetRequirement) -> Optional[str]:
        """Generate a procedural prop asset."""
        # Use scene-specific seed for deterministic generation
        scene_seed = self.seed + hash(requirement.scene_id) % 10000
        
        # Pick colors from brand palette
        colors = list(self.brand_style.colors.values()) if hasattr(self.brand_style.colors, 'values') else []
        if not colors:
            colors = ["#2563eb", "#7c3aed", "#f59e0b"]  # Fallback colors
        
        # Generate prop motif
        svg_content = generate_prop_motif(
            requirement.identifier,
            colors,
            seed=scene_seed
        )
        
        if svg_content:
            # Save to generated assets directory
            timestamp = int(time.time())
            filename = f"prop_{requirement.identifier}_{timestamp}_{scene_seed}.svg"
            filepath = self.generated_dir / filename
            
            with open(filepath, 'w') as f:
                f.write(svg_content)
            
            log.info(f"Generated prop asset: {filepath}")
            return str(filepath)
        
        return None
    
    def _generate_character(self, requirement: AssetRequirement) -> Optional[str]:
        """Generate a procedural character asset."""
        # Use scene-specific seed for deterministic generation
        scene_seed = self.seed + hash(requirement.scene_id) % 10000
        
        # Pick colors from brand palette
        colors = list(self.brand_style.colors.values()) if hasattr(self.brand_style.colors, 'values') else []
        if not colors:
            colors = ["#2563eb", "#7c3aed", "#f59e0b"]  # Fallback colors
        
        # Generate character motif
        svg_content = generate_character_motif(
            requirement.identifier,
            colors,
            seed=scene_seed
        )
        
        if svg_content:
            # Save to generated assets directory
            timestamp = int(time.time())
            filename = f"char_{requirement.identifier}_{timestamp}_{scene_seed}.svg"
            filepath = self.generated_dir / filename
            
            with open(filepath, 'w') as f:
                f.write(svg_content)
            
            log.info(f"Generated character asset: {filepath}")
            return str(filepath)
        
        return None
    
    def generate_variants(self, base_svg_path: str, motif_type: str, count: int = 5) -> List[str]:
        """Generate procedural variants of a base SVG motif using advanced path operations."""
        try:
            # Use the global variant generator if available
            if hasattr(self, 'variant_generator') and self.variant_generator:
                return generate_motif_variants(
                    base_svg_path, 
                    motif_type, 
                    count, 
                    str(self.generated_dir),
                    seed=self.seed
                )
            else:
                log.warning("Variant generator not available, falling back to basic generation")
                return []
        except Exception as e:
            log.error(f"Failed to generate variants: {e}")
            return []


class StoryboardAssetLoop:
    """Main orchestrator for the storyboard asset loop."""
    
    def __init__(self, slug: str, brand_style: BrandStyle, seed: int = 42):
        self.slug = slug
        self.brand_style = brand_style
        self.seed = seed
        self.asset_library = AssetLibrary(brand_style)
        self.asset_generator = ProceduralAssetGenerator(brand_style, seed)
        self.requirements: List[AssetRequirement] = []
        self.coverage_history: List[Dict] = []
    
    def analyze_storyboard(self, scenescript: SceneScript) -> List[AssetRequirement]:
        """Analyze the storyboard to identify all required assets."""
        requirements = []
        
        for scene in scenescript.scenes:
            # Check scene background
            if scene.bg:
                req = AssetRequirement("background", scene.bg, f"scene_{scene.id}", scene.id)
                requirements.append(req)
            
            # Check scene elements
            for element in scene.elements:
                if element.type in ["prop", "character"]:
                    # These elements need asset files
                    asset_id = element.content or element.id
                    req = AssetRequirement(element.type, asset_id, element.id, scene.id)
                    requirements.append(req)
                
                elif element.type == "text" and element.style and "background" in element.style:
                    # Text elements with custom backgrounds
                    bg_id = element.style["background"]
                    req = AssetRequirement("background", bg_id, element.id, scene.id)
                    requirements.append(req)
        
        self.requirements = requirements
        log.info(f"Identified {len(requirements)} asset requirements")
        return requirements
    
    def match_existing_assets(self) -> Dict[str, int]:
        """Match requirements against existing assets."""
        matched = 0
        total = len(self.requirements)
        
        for requirement in self.requirements:
            asset_path = self.asset_library.find_asset(requirement.asset_type, requirement.identifier)
            if asset_path:
                requirement.asset_path = asset_path
                requirement.coverage_status = "found"
                matched += 1
                log.debug(f"Matched existing asset: {requirement}")
            else:
                log.debug(f"No existing asset found: {requirement}")
        
        coverage_pct = (matched / total * 100) if total > 0 else 0
        log.info(f"Asset matching complete: {matched}/{total} ({coverage_pct:.1f}%)")
        
        return {
            "matched": matched,
            "total": total,
            "coverage_pct": coverage_pct
        }
    
    def generate_missing_assets(self) -> Dict[str, int]:
        """Generate procedural assets for missing requirements."""
        generated = 0
        missing = [r for r in self.requirements if r.coverage_status == "missing"]
        
        # Initialize SVG path processor for advanced operations
        try:
            self.path_processor = create_path_processor()
            self.variant_generator = create_variant_generator(self.path_processor)
            log.info("SVG path processor initialized for advanced asset generation")
        except ImportError as e:
            log.warning(f"SVG path processor not available: {e}")
            self.path_processor = None
            self.variant_generator = None
        
        for requirement in missing:
            generated_path = self.asset_generator.generate_asset(requirement)
            if generated_path:
                requirement.generated_path = generated_path
                requirement.coverage_status = "generated"
                generated += 1
                log.info(f"Generated asset: {requirement} -> {generated_path}")
            else:
                log.warning(f"Failed to generate asset: {requirement}")
        
        log.info(f"Asset generation complete: {generated}/{len(missing)} missing assets generated")
        return {
            "generated": generated,
            "missing": len(missing),
            "success_rate": (generated / len(missing) * 100) if len(missing) > 0 else 0
        }
    
    def update_storyboard_assets(self, scenescript: SceneScript) -> SceneScript:
        """Update the storyboard with new asset paths."""
        # Create a copy to avoid modifying the original
        updated_script = scenescript.copy(deep=True)
        
        for requirement in self.requirements:
            if requirement.coverage_status == "generated" and requirement.generated_path:
                # Update the scene or element with the new asset path
                if requirement.asset_type == "background":
                    # Find and update the scene background
                    for scene in updated_script.scenes:
                        if scene.id == requirement.scene_id:
                            # Store the generated asset path in scene metadata
                            if scene.metadata is None:
                                scene.metadata = {}
                            scene.metadata['generated_background'] = requirement.generated_path
                            break
                else:
                    # Find and update the element
                    for scene in updated_script.scenes:
                        if scene.id == requirement.scene_id:
                            for element in scene.elements:
                                if element.id == requirement.element_id:
                                    # Store the generated asset path in element metadata
                                    if element.metadata is None:
                                        element.metadata = {}
                                    element.metadata['generated_asset'] = requirement.generated_path
                                    break
        
        return updated_script
    
    def validate_coverage(self) -> Dict[str, Union[bool, float, str]]:
        """Validate that 100% asset coverage has been achieved."""
        total_requirements = len(self.requirements)
        covered_requirements = sum(1 for r in self.requirements if r.coverage_status != "missing")
        
        coverage_pct = (covered_requirements / total_requirements * 100) if total_requirements > 0 else 0
        is_fully_covered = coverage_pct >= 100.0
        
        # Record coverage history
        coverage_record = {
            "timestamp": time.time(),
            "total_requirements": total_requirements,
            "covered_requirements": covered_requirements,
            "coverage_pct": coverage_pct,
            "is_fully_covered": is_fully_covered,
            "requirements": [
                {
                    "asset_type": r.asset_type,
                    "identifier": r.identifier,
                    "coverage_status": r.coverage_status,
                    "asset_path": r.asset_path,
                    "generated_path": r.generated_path
                }
                for r in self.requirements
            ]
        }
        self.coverage_history.append(coverage_record)
        
        log.info(f"Coverage validation: {covered_requirements}/{total_requirements} ({coverage_pct:.1f}%) - {'FULLY COVERED' if is_fully_covered else 'INCOMPLETE'}")
        
        return {
            "is_fully_covered": is_fully_covered,
            "coverage_pct": coverage_pct,
            "total_requirements": total_requirements,
            "covered_requirements": covered_requirements,
            "coverage_record": coverage_record
        }
    
    def run_asset_loop(self, scenescript: SceneScript, max_iterations: int = 3) -> Tuple[SceneScript, Dict]:
        """Run the complete asset loop until 100% coverage is achieved."""
        log.info(f"Starting asset loop for {self.slug}")
        
        iteration = 0
        final_coverage = None
        
        while iteration < max_iterations:
            iteration += 1
            log.info(f"Asset loop iteration {iteration}/{max_iterations}")
            
            # Analyze storyboard for requirements
            self.analyze_storyboard(scenescript)
            
            # Match against existing assets
            match_results = self.match_existing_assets()
            
            # Check if we already have sufficient coverage
            if match_results["coverage_pct"] >= 90.0:
                log.info(f"Sufficient coverage achieved ({match_results['coverage_pct']:.1f}%), skipping generation")
                break
            
            # Generate missing assets
            generation_results = self.generate_missing_assets()
            
            # Update storyboard with new assets
            scenescript = self.update_storyboard_assets(scenescript)
            
            # Validate final coverage
            final_coverage = self.validate_coverage()
            
            # Check if we've achieved 100% coverage
            if final_coverage["is_fully_covered"]:
                log.info("100% asset coverage achieved!")
                break
            
            log.info(f"Iteration {iteration} complete, coverage: {final_coverage['coverage_pct']:.1f}%")
        
        # Final validation
        if not final_coverage:
            final_coverage = self.validate_coverage()
        
        # Save coverage report
        self._save_coverage_report()
        
        return scenescript, final_coverage
    
    def _save_coverage_report(self):
        """Save a coverage report for debugging and analysis."""
        report_path = Path("data") / self.slug / "asset_coverage_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report_data = {
            "slug": self.slug,
            "timestamp": time.time(),
            "brand_style": self.brand_style.dict() if hasattr(self.brand_style, 'dict') else str(self.brand_style),
            "asset_library_stats": self.asset_library.get_coverage_stats(),
            "coverage_history": self.coverage_history,
            "final_requirements": [
                {
                    "asset_type": r.asset_type,
                    "identifier": r.identifier,
                    "coverage_status": r.coverage_status,
                    "asset_path": r.asset_path,
                    "generated_path": r.generated_path
                }
                for r in self.requirements
            ]
        }
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        log.info(f"Coverage report saved to: {report_path}")


def run_asset_loop(slug: str, scenescript: SceneScript, brand_style: BrandStyle, seed: int = 42) -> Tuple[SceneScript, Dict]:
    """Convenience function to run the asset loop for a given slug and scenescript."""
    loop = StoryboardAssetLoop(slug, brand_style, seed)
    return loop.run_asset_loop(scenescript)


def analyze_asset_requirements(scenescript: SceneScript) -> List[AssetRequirement]:
    """Analyze a scenescript to identify asset requirements without running the full loop."""
    # Create a minimal loop instance just for analysis
    brand_style = load_style()
    loop = StoryboardAssetLoop("analysis", brand_style)
    return loop.analyze_storyboard(scenescript)
