#!/usr/bin/env python3
"""
Asset Library Manifest Generator

This script creates and maintains a comprehensive manifest of all SVG assets
in the design system, including brand assets and procedurally generated content.
It generates thumbnails, validates palette compliance, and tracks usage metadata.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import xml.etree.ElementTree as ET

# Simple logging setup for standalone operation
def get_logger(name="asset_manifest"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger

log = get_logger("asset_manifest")

# Design language colors for palette validation
DESIGN_COLORS = {
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

# Allowed color values (including hex and named colors)
ALLOWED_COLORS = set(DESIGN_COLORS.values()) | {
    "#000000", "#FFFFFF", "#000", "#FFF",  # Common variations
    "black", "white", "none", "transparent"  # Named colors
}


class AssetManifest:
    """Manages the asset library manifest and thumbnail generation."""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.assets_dir = self.base_dir / "assets"
        self.thumbnails_dir = self.assets_dir / "thumbnails"
        self.manifest_path = self.base_dir / "data" / "library_manifest.json"
        
        # Ensure directories exist
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Asset source directories
        self.brand_dirs = [
            self.assets_dir / "design" / "svg",
            self.assets_dir / "brand"
        ]
        self.generated_dir = self.assets_dir / "generated"
        
        # Load existing manifest if it exists
        self.manifest = self._load_existing_manifest()
    
    def _load_existing_manifest(self) -> Dict[str, Any]:
        """Load existing manifest or create new one."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r') as f:
                    data = json.load(f)
                    log.info(f"Loaded existing manifest with {len(data.get('assets', {}))} assets")
                    return data
            except (json.JSONDecodeError, IOError) as e:
                log.warning(f"Failed to load existing manifest: {e}")
        
        # Create new manifest structure
        return {
            "version": "1.0",
            "generated_at": None,
            "total_assets": 0,
            "assets": {},
            "violations": [],
            "palette_stats": {
                "total_colors": 0,
                "compliant_colors": 0,
                "violation_count": 0
            }
        }
    
    def _extract_svg_metadata(self, svg_path: Path) -> Dict[str, Any]:
        """Extract metadata from SVG file."""
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
            
            # Extract viewBox and dimensions
            viewbox = root.get('viewBox')
            width = root.get('width')
            height = root.get('height')
            
            # Parse viewBox if present
            w, h = None, None
            if viewbox:
                parts = viewbox.split()
                if len(parts) == 4:
                    w = float(parts[2])
                    h = float(parts[3])
            elif width and height:
                w = float(width)
                h = float(height)
            
            # Extract colors from SVG
            colors = self._extract_colors_from_svg(root)
            
            # Generate content hash
            content_hash = self._generate_content_hash(svg_path)
            
            # Determine provenance
            provenance = self._determine_provenance(svg_path)
            
            return {
                "path": str(svg_path.relative_to(self.base_dir)),
                "tags": self._extract_tags(svg_path),
                "palette": colors,
                "w": w,
                "h": h,
                "viewBox": viewbox,
                "hash": content_hash,
                "provenance": provenance,
                "usage_count": 0,
                "last_used": None
            }
            
        except Exception as e:
            log.error(f"Failed to extract metadata from {svg_path}: {e}")
            return None
    
    def _extract_colors_from_svg(self, root: ET.Element) -> List[str]:
        """Extract all colors used in SVG."""
        colors = set()
        
        # Check fill and stroke attributes
        for elem in root.iter():
            fill = elem.get('fill')
            stroke = elem.get('stroke')
            
            if fill and fill != 'none':
                colors.add(fill)
            if stroke and stroke != 'none':
                colors.add(stroke)
        
        return list(colors)
    
    def _generate_content_hash(self, svg_path: Path) -> str:
        """Generate SHA1 hash of SVG content."""
        try:
            with open(svg_path, 'rb') as f:
                content = f.read()
                return hashlib.sha1(content).hexdigest()
        except Exception as e:
            log.error(f"Failed to generate hash for {svg_path}: {e}")
            return ""
    
    def _determine_provenance(self, svg_path: Path) -> Dict[str, Any]:
        """Determine the provenance of an asset."""
        if "generated" in str(svg_path):
            # Extract seed from filename if present
            seed_match = re.search(r'(\d{10})', svg_path.name)
            seed = int(seed_match.group(1)) if seed_match else None
            
            return {
                "source": "generated",
                "seed": seed,
                "generator_params": {}
            }
        else:
            return {
                "source": "brand",
                "seed": None,
                "generator_params": {}
            }
    
    def _extract_tags(self, svg_path: Path) -> List[str]:
        """Extract tags based on file path and name."""
        tags = []
        
        # Add directory-based tags
        path_parts = svg_path.parts
        if "backgrounds" in path_parts:
            tags.append("background")
        if "characters" in path_parts:
            tags.append("character")
        if "objects" in path_parts:
            tags.append("object")
        if "props" in path_parts:
            tags.append("prop")
        
        # Add source-based tags
        if "generated" in path_parts:
            tags.append("procedural")
        else:
            tags.append("brand")
        
        # Add filename-based tags
        name = svg_path.stem.lower()
        if "missing" in name:
            tags.append("placeholder")
        if "bg_" in name:
            tags.append("background")
        if "char_" in name:
            tags.append("character")
        if "prop_" in name:
            tags.append("prop")
        
        return tags
    
    def _validate_palette_compliance(self, colors: List[str]) -> Tuple[bool, List[str]]:
        """Validate that colors are in the allowed palette."""
        violations = []
        compliant = True
        
        for color in colors:
            if color not in ALLOWED_COLORS:
                violations.append(color)
                compliant = False
        
        return compliant, violations
    
    def _generate_thumbnail(self, svg_path: Path) -> bool:
        """Generate PNG thumbnail for SVG asset."""
        try:
            thumbnail_path = self.thumbnails_dir / f"{svg_path.stem}.png"
            
            # Skip if thumbnail already exists and is newer than SVG
            if thumbnail_path.exists():
                svg_mtime = svg_path.stat().st_mtime
                thumb_mtime = thumbnail_path.stat().st_mtime
                if thumb_mtime > svg_mtime:
                    return True
            
            # Use rsvg-convert if available (better SVG rendering)
            if self._has_rsvg_convert():
                cmd = [
                    "rsvg-convert", 
                    "-w", "128", 
                    "-h", "128", 
                    "-f", "png",
                    str(svg_path),
                    "-o", str(thumbnail_path)
                ]
            else:
                # Fallback to ImageMagick
                cmd = [
                    "convert", 
                    "-background", "transparent",
                    "-resize", "128x128",
                    str(svg_path),
                    str(thumbnail_path)
                ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                log.debug(f"Generated thumbnail for {svg_path.name}")
                return True
            else:
                log.warning(f"Failed to generate thumbnail for {svg_path.name}: {result.stderr}")
                return False
                
        except Exception as e:
            log.error(f"Error generating thumbnail for {svg_path}: {e}")
            return False
    
    def _has_rsvg_convert(self) -> bool:
        """Check if rsvg-convert is available."""
        try:
            subprocess.run(["rsvg-convert", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _scan_assets(self) -> List[Path]:
        """Scan all asset directories for SVG files."""
        svg_files = []
        
        # Scan brand directories
        for brand_dir in self.brand_dirs:
            if brand_dir.exists():
                svg_files.extend(brand_dir.rglob("*.svg"))
        
        # Scan generated directory
        if self.generated_dir.exists():
            svg_files.extend(self.generated_dir.rglob("*.svg"))
        
        log.info(f"Found {len(svg_files)} SVG files")
        return svg_files
    
    def rebuild_manifest(self, filter_palette_only: bool = False) -> Dict[str, Any]:
        """Rebuild the complete asset manifest."""
        log.info("[manifest] Starting manifest rebuild")
        
        svg_files = self._scan_assets()
        new_assets = {}
        violations = []
        palette_stats = {
            "total_colors": 0,
            "compliant_colors": 0,
            "violation_count": 0
        }
        
        # Process each SVG file
        for svg_path in svg_files:
            log.debug(f"Processing {svg_path.name}")
            
            # Extract metadata
            metadata = self._extract_svg_metadata(svg_path)
            if not metadata:
                continue
            
            # Generate thumbnail
            self._generate_thumbnail(svg_path)
            
            # Validate palette compliance
            is_compliant, color_violations = self._validate_palette_compliance(metadata["palette"])
            
            if not is_compliant:
                violations.append({
                    "asset": metadata["path"],
                    "violations": color_violations,
                    "type": "palette_violation"
                })
                log.warning(f"Palette violations in {svg_path.name}: {color_violations}")
            
            # Update palette stats
            palette_stats["total_colors"] += len(metadata["palette"])
            if is_compliant:
                palette_stats["compliant_colors"] += len(metadata["palette"])
            palette_stats["violation_count"] += len(color_violations)
            
            # Use hash as key to avoid duplicates
            new_assets[metadata["hash"]] = metadata
        
        # Preserve usage counts from existing manifest
        for hash_key, asset in new_assets.items():
            if hash_key in self.manifest.get("assets", {}):
                existing = self.manifest["assets"][hash_key]
                asset["usage_count"] = existing.get("usage_count", 0)
                asset["last_used"] = existing.get("last_used")
        
        # Update manifest
        self.manifest["assets"] = new_assets
        self.manifest["violations"] = violations
        self.manifest["palette_stats"] = palette_stats
        self.manifest["total_assets"] = len(new_assets)
        self.manifest["generated_at"] = self._get_timestamp()
        
        # Save manifest
        self._save_manifest()
        
        log.info(f"[manifest] Manifest rebuilt: {len(new_assets)} assets, {len(violations)} violations")
        return self.manifest
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
    
    def _save_manifest(self):
        """Save manifest to file."""
        try:
            with open(self.manifest_path, 'w') as f:
                json.dump(self.manifest, f, indent=2)
            log.info(f"Manifest saved to {self.manifest_path}")
        except Exception as e:
            log.error(f"Failed to save manifest: {e}")
    
    def get_manifest_summary(self) -> Dict[str, Any]:
        """Get summary statistics of the manifest."""
        assets = self.manifest.get("assets", {})
        
        # Count by source
        brand_count = sum(1 for a in assets.values() if a["provenance"]["source"] == "brand")
        generated_count = sum(1 for a in assets.values() if a["provenance"]["source"] == "generated")
        
        # Count by tags
        tag_counts = {}
        for asset in assets.values():
            for tag in asset.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        return {
            "total_assets": len(assets),
            "brand_assets": brand_count,
            "generated_count": generated_count,
            "tag_distribution": tag_counts,
            "palette_stats": self.manifest.get("palette_stats", {}),
            "violations": len(self.manifest.get("violations", []))
        }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Asset Library Manifest Generator")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the complete manifest")
    parser.add_argument("--filter", choices=["palette-only"], help="Filter mode for violations")
    parser.add_argument("--summary", action="store_true", help="Show manifest summary")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize manifest
    manifest = AssetManifest()
    
    if args.rebuild:
        log.info("Rebuilding asset manifest...")
        result = manifest.rebuild_manifest()
        
        if args.filter == "palette-only":
            violations = result.get("violations", [])
            if violations:
                print(f"\nPalette violations found: {len(violations)}")
                for violation in violations[:5]:  # Show first 5
                    print(f"  {violation['asset']}: {violation['violations']}")
                if len(violations) > 5:
                    print(f"  ... and {len(violations) - 5} more")
            else:
                print("No palette violations found")
    
    if args.summary or not args.rebuild:
        summary = manifest.get_manifest_summary()
        print("\nAsset Manifest Summary:")
        print(f"  Total assets: {summary['total_assets']}")
        print(f"  Brand assets: {summary['brand_assets']}")
        print(f"  Generated assets: {summary['generated_count']}")
        print(f"  Palette violations: {summary['violations']}")
        print(f"  Tag distribution: {dict(list(summary['tag_distribution'].items())[:5])}")
    
    if not args.rebuild and not args.summary:
        parser.print_help()


if __name__ == "__main__":
    main()
