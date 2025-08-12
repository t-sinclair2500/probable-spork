#!/usr/bin/env python3
"""
Asset Generator for Procedural Gap Filling

This module generates procedural SVG assets to fill gaps in asset plans,
using motif generators and ensuring palette compliance with the design system.
All generation is deterministic given the same seed parameters.
"""

import argparse
import hashlib
import json
import logging
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import xml.etree.ElementTree as ET

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bin.core import get_logger
from bin.cutout.motif_generators import (
    generate_background_motif,
    generate_prop_motif,
    generate_character_motif,
    make_starburst,
    make_boomerang,
    make_cutout_collage
)
from bin.asset_manifest import AssetManifest

log = get_logger("asset_generator")


class AssetGenerator:
    """Generates procedural SVG assets to fill gaps in asset plans."""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.assets_dir = self.base_dir / "assets"
        self.generated_dir = self.assets_dir / "generated"
        self.thumbnails_dir = self.assets_dir / "thumbnails"
        
        # Ensure directories exist
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)
        
        # Load design language colors
        self.design_colors = self._load_design_colors()
        
        # Generation caps from config
        self.max_assets_per_run = 20  # Default cap
        
    def _load_design_colors(self) -> Dict[str, str]:
        """Load colors from design language configuration."""
        try:
            design_path = self.base_dir / "design" / "design_language.json"
            if design_path.exists():
                with open(design_path, "r") as f:
                    data = json.load(f)
                    return data.get("colors", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log.warning(f"Failed to load design language: {e}")
        
        # Fallback to core palette
        return {
            "primary_blue": "#1C4FA1",
            "primary_red": "#D62828", 
            "primary_yellow": "#F6BE00",
            "secondary_orange": "#F28C28",
            "secondary_green": "#4E9F3D",
            "accent_teal": "#008080",
            "accent_brown": "#8B5E3C",
            "accent_black": "#1A1A1A",
            "accent_white": "#FFFFFF",
            "accent_cream": "#F8F1E5",
            "accent_pink": "#FF6F91"
        }
    
    def _validate_palette(self, palette: List[str]) -> List[str]:
        """Validate and filter palette to only include design system colors."""
        allowed_colors = set(self.design_colors.values())
        valid_colors = []
        
        for color in palette:
            if color in allowed_colors:
                valid_colors.append(color)
            else:
                log.warning(f"Color {color} not in design palette, skipping")
        
        # Ensure we have at least one valid color
        if not valid_colors:
            log.warning("No valid colors in palette, using default")
            valid_colors = ["#1C4FA1", "#F6BE00"]
        
        return valid_colors
    
    def _generate_asset_filename(self, spec: Dict[str, Any], seed: int) -> str:
        """Generate a deterministic filename for the asset."""
        # Create a hash from spec and seed for consistent naming
        spec_str = json.dumps(spec, sort_keys=True) + str(seed)
        spec_hash = hashlib.sha1(spec_str.encode()).hexdigest()[:8]
        
        category = spec.get("category", "unknown")
        style = spec.get("style", "default")
        
        return f"{category}_{style}_{spec_hash}.svg"
    
    def _add_metadata(self, svg_content: str, spec: Dict[str, Any], seed: int, generator_params: Dict[str, Any]) -> str:
        """Add metadata to SVG including generator info and seed."""
        # Parse SVG to add metadata
        try:
            root = ET.fromstring(svg_content)
            
            # Add or update desc element
            desc = root.find(".//desc")
            if desc is None:
                desc = ET.SubElement(root, "desc")
            
            # Create metadata description
            metadata = {
                "generator": "asset_generator.py",
                "seed": seed,
                "category": spec.get("category", "unknown"),
                "style": spec.get("style", "default"),
                "palette": spec.get("palette", []),
                "generator_params": generator_params,
                "notes": spec.get("notes", "")
            }
            
            desc.text = f"Procedurally generated {spec.get('category', 'asset')} using seed {seed}. Parameters: {json.dumps(generator_params)}"
            
            # Add metadata as comment for easy extraction
            metadata_comment = f"<!-- METADATA: {json.dumps(metadata)} -->"
            
            # Insert comment after XML declaration
            if svg_content.startswith("<?xml"):
                xml_end = svg_content.find("?>") + 2
                return svg_content[:xml_end] + "\n" + metadata_comment + "\n" + svg_content[xml_end:]
            else:
                return metadata_comment + "\n" + svg_content
                
        except ET.ParseError as e:
            log.warning(f"Failed to parse SVG for metadata: {e}")
            return svg_content
    
    def _create_thumbnail(self, svg_path: str, out_dir: str) -> str:
        """Create a PNG thumbnail from SVG using rsvg-convert or similar."""
        svg_path_obj = Path(svg_path)
        thumbnail_name = svg_path_obj.stem + "_thumb.png"
        thumbnail_path = Path(out_dir) / thumbnail_name
        
        try:
            # Try rsvg-convert first (best quality)
            cmd = [
                "rsvg-convert", "-w", "128", "-h", "128",
                str(svg_path), "-o", str(thumbnail_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and thumbnail_path.exists():
                log.info(f"Created thumbnail: {thumbnail_path}")
                return str(thumbnail_path)
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        try:
            # Fallback to ImageMagick
            cmd = [
                "convert", str(svg_path), "-resize", "128x128",
                str(thumbnail_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and thumbnail_path.exists():
                log.info(f"Created thumbnail with ImageMagick: {thumbnail_path}")
                return str(thumbnail_path)
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        log.warning(f"Could not create thumbnail for {svg_path}")
        return ""
    
    def generate_from_spec(self, spec: Dict[str, Any], out_dir: str, seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a single asset from specification.
        
        Args:
            spec: Asset specification with category, style, palette, etc.
            out_dir: Output directory for generated assets
            seed: Random seed for deterministic generation
            
        Returns:
            Dict with path, palette, seed, and generator parameters
        """
        if seed is None:
            seed = random.randint(1, 1000000)
        
        log.info(f"Generating asset: {spec.get('element_id', 'unknown')} with seed {seed}")
        
        # Validate and filter palette
        palette = spec.get("palette", [])
        valid_palette = self._validate_palette(palette)
        
        # Determine asset dimensions based on category
        category = spec.get("category", "prop")
        if category == "background":
            width, height = 1920, 1080
        else:
            width, height = 200, 200
        
        # Generate asset based on category and style
        svg_content = None
        generator_params = {}
        
        try:
            if category == "background":
                style = spec.get("style", "starburst")
                # Handle specific background styles
                if style in ["starburst", "boomerang", "cutout_collage"]:
                    svg_content = generate_background_motif(
                        motif_type=style,
                        colors=valid_palette,
                        seed=seed,
                        width=width,
                        height=height
                    )
                else:
                    # Fallback to starburst for unknown styles
                    svg_content = generate_background_motif(
                        motif_type="starburst",
                        colors=valid_palette,
                        seed=seed,
                        width=width,
                        height=height
                    )
                    style = "starburst"  # Update style to reflect actual generation
                
                generator_params = {
                    "motif_type": style,
                    "width": width,
                    "height": height
                }
                
            elif category == "prop":
                style = spec.get("style", "geometric")
                # Handle specific prop styles that have dedicated generators
                if style in ["clock", "phone", "chair", "book", "notebook"]:
                    svg_content = generate_prop_motif(
                        prop_type=style,
                        colors=valid_palette,
                        seed=seed,
                        width=width,
                        height=height
                    )
                elif style == "nelson_sunburst":
                    # Use starburst motif for Nelson clock style
                    svg_content = make_starburst(
                        cx=width//2, cy=height//2,
                        color_spokes=valid_palette[0],
                        color_knobs=valid_palette[1] if len(valid_palette) > 1 else valid_palette[0],
                        spokes=12, inner=12, outer=48, knob_radius=3,
                        seed=seed
                    )
                else:
                    # Fallback to geometric prop for unknown styles
                    svg_content = generate_prop_motif(
                        prop_type="geometric",
                        colors=valid_palette,
                        seed=seed,
                        width=width,
                        height=height
                    )
                    style = "geometric"  # Update style to reflect actual generation
                
                generator_params = {
                    "prop_type": style,
                    "width": width,
                    "height": height
                }
                
            elif category == "character":
                style = spec.get("style", "generic")
                svg_content = generate_character_motif(
                    character_type=style,
                    colors=valid_palette,
                    seed=seed,
                    width=width,
                    height=height
                )
                generator_params = {
                    "character_type": style,
                    "width": width,
                    "height": height
                }
                
            else:
                # Default to geometric prop
                svg_content = generate_prop_motif(
                    prop_type="geometric",
                    colors=valid_palette,
                    seed=seed,
                    width=width,
                    height=height
                )
                generator_params = {
                    "prop_type": "geometric",
                    "width": width,
                    "height": height
                }
            
            if not svg_content:
                raise ValueError(f"Failed to generate {category} asset with style {spec.get('style', 'default')}")
            
            # Add metadata
            svg_content = self._add_metadata(svg_content, spec, seed, generator_params)
            
            # Generate filename and save
            filename = self._generate_asset_filename(spec, seed)
            svg_path = Path(out_dir) / filename
            
            with open(svg_path, "w") as f:
                f.write(svg_content)
            
            # Create thumbnail
            thumbnail_path = self._create_thumbnail(str(svg_path), str(self.thumbnails_dir))
            
            # Calculate asset hash
            with open(svg_path, "rb") as f:
                asset_hash = hashlib.sha1(f.read()).hexdigest()
            
            result = {
                "path": str(svg_path),
                "palette": valid_palette,
                "seed": seed,
                "generator_params": generator_params,
                "thumbnail": thumbnail_path,
                "asset_hash": asset_hash,
                "category": category,
                "style": spec.get("style", "default")
            }
            
            log.info(f"Generated asset: {svg_path}")
            return result
            
        except Exception as e:
            log.error(f"Failed to generate asset: {e}")
            raise
    
    def fill_gaps(self, plan_path: str, manifest_path: str, seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Fill all gaps in an asset plan by generating missing assets.
        
        Args:
            plan_path: Path to asset plan JSON
            manifest_path: Path to asset manifest JSON
            seed: Random seed for deterministic generation
            
        Returns:
            Dict with generation report and updated plan
        """
        log.info(f"[generator] Filling gaps in asset plan: {plan_path}")
        
        # Load asset plan
        with open(plan_path, "r") as f:
            asset_plan = json.load(f)
        
        gaps = asset_plan.get("gaps", [])
        if not gaps:
            log.info("[generator] No gaps to fill")
            return {"generated": [], "plan_updated": False}
        
        # Check generation cap
        if len(gaps) > self.max_assets_per_run:
            log.warning(f"Gap count {len(gaps)} exceeds cap {self.max_assets_per_run}")
            gaps = gaps[:self.max_assets_per_run]
        
        # Generate assets for each gap
        generated_assets = []
        out_dir = self.generated_dir
        
        for i, gap in enumerate(gaps):
            try:
                # Use sequential seeds for deterministic generation
                gap_seed = seed + i if seed is not None else None
                
                asset_result = self.generate_from_spec(
                    gap["spec"], 
                    str(out_dir), 
                    gap_seed
                )
                
                # Add element_id to result
                asset_result["element_id"] = gap["element_id"]
                generated_assets.append(asset_result)
                
                log.info(f"[generator] Generated asset {i+1}/{len(gaps)}: {gap['element_id']}")
                
            except Exception as e:
                log.error(f"Failed to generate asset for {gap['element_id']}: {e}")
                continue
        
        # Update asset plan: move generated assets from gaps to resolved
        if generated_assets:
            # Add generated assets to resolved list
            for asset in generated_assets:
                resolved_item = {
                    "element_id": asset["element_id"],
                    "asset": asset["path"],
                    "scale": 1.0,
                    "variant": "default",
                    "asset_hash": asset["asset_hash"],
                    "reuse_type": "generated"
                }
                asset_plan["resolved"].append(resolved_item)
            
            # Remove filled gaps
            asset_plan["gaps"] = []
            asset_plan["resolved_count"] = len(asset_plan["resolved"])
            asset_plan["gaps_count"] = 0
            
            # Update reuse ratio
            total_placeholders = asset_plan["total_placeholders"]
            existing_assets = sum(1 for item in asset_plan["resolved"] if item["reuse_type"] == "existing")
            asset_plan["reuse_ratio"] = existing_assets / total_placeholders if total_placeholders > 0 else 0
            
            # Save updated plan
            with open(plan_path, "w") as f:
                json.dump(asset_plan, f, indent=2)
            
            log.info(f"[generator] Updated asset plan: {len(generated_assets)} assets generated")
        
        # Create generation report
        generation_report = {
            "slug": asset_plan.get("slug", "unknown"),
            "generated_at": asset_plan.get("generated_at"),
            "total_gaps": len(gaps),
            "assets_generated": len(generated_assets),
            "generated_assets": generated_assets,
            "generation_params": {
                "seed": seed,
                "max_assets_per_run": self.max_assets_per_run,
                "out_dir": str(out_dir)
            }
        }
        
        # Save generation report
        report_path = Path(plan_path).parent / "asset_generation_report.json"
        with open(report_path, "w") as f:
            json.dump(generation_report, f, indent=2)
        
        # Refresh manifest if it exists
        if Path(manifest_path).exists():
            try:
                manifest = AssetManifest(str(self.base_dir))
                manifest.rebuild_manifest()
                log.info("[generator] Refreshed asset manifest")
            except Exception as e:
                log.warning(f"Failed to refresh manifest: {e}")
        
        return {
            "generated": generated_assets,
            "plan_updated": len(generated_assets) > 0,
            "generation_report": str(report_path)
        }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate procedural assets to fill gaps")
    parser.add_argument("--plan", required=True, help="Path to asset plan JSON")
    parser.add_argument("--seed", type=int, help="Random seed for deterministic generation")
    parser.add_argument("--base-dir", default=".", help="Base directory for assets")
    
    args = parser.parse_args()
    
    try:
        generator = AssetGenerator(args.base_dir)
        
        # Auto-detect manifest path
        plan_path = Path(args.plan)
        manifest_path = Path("data/library_manifest.json")
        
        if not plan_path.exists():
            log.error(f"Asset plan not found: {plan_path}")
            sys.exit(1)
        
        if not manifest_path.exists():
            log.error(f"Asset manifest not found: {manifest_path}")
            sys.exit(1)
        
        result = generator.fill_gaps(str(plan_path), str(manifest_path), args.seed)
        
        if result["plan_updated"]:
            print(f"Successfully generated {len(result['generated'])} assets")
            print(f"Generation report: {result['generation_report']}")
        else:
            print("No assets were generated")
            
    except Exception as e:
        log.error(f"Asset generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
