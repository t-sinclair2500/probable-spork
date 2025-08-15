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

# Try to import Pillow for thumbnail generation fallback
try:
    from PIL import Image, ImageDraw
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import cairosvg
    CAIRO_AVAILABLE = True
except (ImportError, OSError):
    CAIRO_AVAILABLE = False

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

# Color distance threshold for ΔE calculation (CIEDE2000)
PALETTE_THRESHOLD = 4.0


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c + c for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_lab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert RGB to CIE Lab color space."""
    # Convert sRGB to linear RGB
    def to_linear(c):
        c = c / 255.0
        if c <= 0.04045:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4
    
    r_lin = to_linear(r)
    g_lin = to_linear(g)
    b_lin = to_linear(b)
    
    # Convert to XYZ (D65 illuminant)
    x = r_lin * 0.4124 + g_lin * 0.3576 + b_lin * 0.1805
    y = r_lin * 0.2126 + g_lin * 0.7152 + b_lin * 0.0722
    z = r_lin * 0.0193 + g_lin * 0.1192 + b_lin * 0.9505
    
    # Convert to Lab
    def xyz_to_lab(x, y, z):
        # Normalize by D65 white point
        x /= 0.95047
        y /= 1.00000
        z /= 1.08883
        
        def transform(c):
            if c > 0.008856:
                return c ** (1/3)
            return (7.787 * c) + (16/116)
        
        l = (116 * transform(y)) - 16
        a = 500 * (transform(x) - transform(y))
        b = 200 * (transform(y) - transform(z))
        
        return l, a, b
    
    return xyz_to_lab(x, y, z)


def calculate_color_distance(color1: str, color2: str) -> float:
    """Calculate CIEDE2000 color distance between two hex colors."""
    try:
        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)
        
        lab1 = rgb_to_lab(*rgb1)
        lab2 = rgb_to_lab(*rgb2)
        
        # Simplified Euclidean distance in Lab space
        # For production, consider using colormath library for CIEDE2000
        delta_l = lab1[0] - lab2[0]
        delta_a = lab1[1] - lab2[1]
        delta_b = lab1[2] - lab2[2]
        
        distance = (delta_l**2 + delta_a**2 + delta_b**2)**0.5
        return distance
        
    except Exception as e:
        log.warning(f"Failed to calculate color distance between {color1} and {color2}: {e}")
        return 999.0  # Return high distance on error


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
                "violation_count": 0,
                "delta_e_violations": 0
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
            
            # Validate palette compliance with ΔE calculation
            palette_ok, delta_e_violations = self._validate_palette_compliance_delta_e(colors)
            
            return {
                "path": str(svg_path.relative_to(self.base_dir)),
                "tags": self._extract_tags(svg_path),
                "palette": colors,
                "w": w,
                "h": h,
                "viewBox": viewbox,
                "hash": content_hash,
                "provenance": provenance,
                "palette_ok": palette_ok,
                "delta_e_violations": delta_e_violations,
                "usage_count": 0,
                "last_used": None,
                "created_at": self._get_file_timestamp(svg_path),
                "license": self._determine_license(svg_path)
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
                "generator_params": {},
                "generator": "asset_generator.py"
            }
        else:
            return {
                "source": "brand",
                "seed": None,
                "generator_params": {},
                "generator": None
            }
    
    def _determine_license(self, svg_path: Path) -> str:
        """Determine the license for an asset."""
        if "generated" in str(svg_path):
            return "MIT"  # Generated assets use MIT license
        else:
            return "Brand"  # Brand assets are proprietary
    
    def _get_file_timestamp(self, svg_path: Path) -> str:
        """Get file creation timestamp."""
        try:
            stat = svg_path.stat()
            # Use modification time as creation time approximation
            from datetime import datetime
            return datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z"
        except Exception:
            return self._get_timestamp()
    
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
    
    def _validate_palette_compliance_delta_e(self, colors: List[str]) -> Tuple[bool, List[Dict[str, Any]]]:
        """Validate that colors are palette compliant using ΔE distance calculation."""
        violations = []
        compliant = True
        
        for color in colors:
            if color in ALLOWED_COLORS:
                continue  # Exact match
            
            # Check if color is close enough to any palette color
            min_distance = float('inf')
            closest_palette_color = None
            
            for palette_color in DESIGN_COLORS.values():
                distance = calculate_color_distance(color, palette_color)
                if distance < min_distance:
                    min_distance = distance
                    closest_palette_color = palette_color
            
            if min_distance > PALETTE_THRESHOLD:
                violations.append({
                    "color": color,
                    "closest_palette": closest_palette_color,
                    "delta_e": min_distance,
                    "threshold": PALETTE_THRESHOLD
                })
                compliant = False
        
        return compliant, violations
    
    def _validate_palette_compliance(self, colors: List[str]) -> Tuple[bool, List[str]]:
        """Legacy palette validation method."""
        violations = []
        compliant = True
        
        for color in colors:
            if color not in ALLOWED_COLORS:
                violations.append(color)
                compliant = False
        
        return compliant, violations
    
    def _generate_thumbnail_pillow(self, svg_path: Path, thumbnail_path: Path) -> bool:
        """Generate PNG thumbnail using Pillow and CairoSVG fallback."""
        try:
            if CAIRO_AVAILABLE:
                # Use CairoSVG for high-quality SVG rendering
                import cairosvg
                cairosvg.svg2png(
                    url=str(svg_path),
                    write_to=str(thumbnail_path),
                    output_width=128,
                    output_height=128
                )
                return True
            elif PILLOW_AVAILABLE:
                # Fallback to Pillow with basic SVG parsing
                # This is a simplified approach - for production, consider using svglib
                log.warning(f"Using basic Pillow fallback for {svg_path.name}")
                
                # Create a simple colored square as fallback
                img = Image.new('RGBA', (128, 128), (255, 255, 255, 0))
                draw = ImageDraw.Draw(img)
                
                # Draw a colored border to indicate it's a fallback
                draw.rectangle([0, 0, 127, 127], outline=(100, 100, 100, 128), width=2)
                
                # Add text label
                try:
                    from PIL import ImageFont
                    font = ImageFont.load_default()
                    draw.text((64, 64), "SVG", fill=(100, 100, 100, 128), anchor="mm", font=font)
                except:
                    pass
                
                img.save(thumbnail_path, 'PNG')
                return True
            else:
                return False
                
        except Exception as e:
            log.warning(f"Pillow/Cairo thumbnail generation failed for {svg_path.name}: {e}")
            return False
    
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
            
            # Try Pillow/CairoSVG first (no external dependencies)
            if PILLOW_AVAILABLE or CAIRO_AVAILABLE:
                if self._generate_thumbnail_pillow(svg_path, thumbnail_path):
                    log.debug(f"Generated thumbnail with Pillow/Cairo for {svg_path.name}")
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
            "violation_count": 0,
            "delta_e_violations": 0
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
            is_compliant, color_violations = self._validate_palette_compliance_delta_e(metadata["palette"])
            
            if not is_compliant:
                violations.append({
                    "asset": metadata["path"],
                    "violations": metadata["delta_e_violations"],
                    "type": "palette_violation"
                })
                log.warning(f"Palette violations in {svg_path.name}: {len(metadata['delta_e_violations'])} violations")
            
            # Update palette stats
            palette_stats["total_colors"] += len(metadata["palette"])
            if is_compliant:
                palette_stats["compliant_colors"] += len(metadata["palette"])
            palette_stats["violation_count"] += len(color_violations)
            palette_stats["delta_e_violations"] += len(metadata["delta_e_violations"])
            
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
        
        # Count palette compliance
        palette_ok_count = sum(1 for a in assets.values() if a.get("palette_ok", False))
        
        return {
            "total_assets": len(assets),
            "brand_assets": brand_count,
            "generated_count": generated_count,
            "tag_distribution": tag_counts,
            "palette_stats": self.manifest.get("palette_stats", {}),
            "palette_ok_count": palette_ok_count,
            "palette_violations": len(self.manifest.get("violations", [])),
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
                    print(f"  {violation['asset']}: {len(violation['violations'])} violations")
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
        print(f"  Palette compliant: {summary['palette_ok_count']}")
        print(f"  Palette violations: {summary['palette_violations']}")
        print(f"  Tag distribution: {dict(list(summary['tag_distribution'].items())[:5])}")
    
    if not args.rebuild and not args.summary:
        parser.print_help()


if __name__ == "__main__":
    main()
