#!/usr/bin/env python3
"""
Advanced SVG Path Operations for Procedural Asset Generation

This module provides advanced SVG path manipulation capabilities including:
- Path parsing and manipulation using svgpathtools/svgelements
- Boolean operations (union, intersection, difference)
- Geometric transformations and morphing
- Safe area validation using shapely
- Procedural generation of motif variants

All operations respect brand design constraints and safe margins.
"""

import json
import logging
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, TYPE_CHECKING

from .sdk import SAFE_MARGINS_PX
from bin.core import get_logger

log = get_logger("svg_path_ops")

# Type aliases for optional dependencies
if TYPE_CHECKING:
    try:
        import svgpathtools
        from svgpathtools import Path as SVGPath, Line, CubicBezier, QuadraticBezier, Arc
        SVG_PATHS_AVAILABLE = True
    except ImportError:
        SVG_PATHS_AVAILABLE = False
        SVGPath = Any
        Line = Any
        CubicBezier = Any
        QuadraticBezier = Any
        Arc = Any

try:
    import svgpathtools
    from svgpathtools import Path as SVGPath, Line, CubicBezier, QuadraticBezier, Arc
    SVG_PATHS_AVAILABLE = True
except ImportError:
    SVG_PATHS_AVAILABLE = False
    SVGPath = Any
    Line = Any
    CubicBezier = Any
    QuadraticBezier = Any
    Arc = Any
    log.warning("svgpathtools not available - advanced path operations disabled")

try:
    import svgelements
    from svgelements import SVG, Path as SVGElementPath
    SVG_ELEMENTS_AVAILABLE = True
except ImportError:
    SVG_ELEMENTS_AVAILABLE = False
    SVG = Any
    SVGElementPath = Any
    log.warning("svgelements not available - advanced path operations disabled")

try:
    import shapely
    from shapely.geometry import Polygon, Point, LineString
    from shapely.ops import unary_union
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    Polygon = Any
    Point = Any
    LineString = Any
    unary_union = Any
    log.warning("shapely not available - safe area validation disabled")

try:
    import svgwrite
    SVGWRITE_AVAILABLE = True
except ImportError:
    SVGWRITE_AVAILABLE = False
    svgwrite = Any
    log.warning("svgwrite not available - SVG export disabled")


class SVGPathProcessor:
    """Advanced SVG path processing with boolean operations and transformations."""
    
    def __init__(self, safe_margins: int = SAFE_MARGINS_PX):
        self.safe_margins = safe_margins
        self._validate_dependencies()
    
    def _validate_dependencies(self):
        """Validate that required dependencies are available."""
        if not SVG_PATHS_AVAILABLE:
            raise ImportError("svgpathtools is required for advanced path operations")
        if not SVG_ELEMENTS_AVAILABLE:
            raise ImportError("svgelements is required for advanced path operations")
        if not SHAPELY_AVAILABLE:
            log.warning("shapely not available - safe area validation will be disabled")
        if not SVGWRITE_AVAILABLE:
            log.warning("svgwrite not available - SVG export will be disabled")
    
    def parse_svg_path(self, svg_content: str) -> Optional[SVGPath]:
        """Parse SVG content and extract path data."""
        try:
            # Try parsing with svgelements first
            svg = svgelements.SVG.parse(svg_content)
            paths = list(svg.select("path"))
            if paths:
                # Convert to svgpathtools format
                path_data = paths[0].d
                return svgpathtools.parse_path(path_data)
        except Exception as e:
            log.debug(f"Failed to parse with svgelements: {e}")
        
        try:
            # Fallback to direct path parsing
            if '<path' in svg_content:
                import re
                path_match = re.search(r'd="([^"]+)"', svg_content)
                if path_match:
                    return svgpathtools.parse_path(path_match.group(1))
        except Exception as e:
            log.debug(f"Failed to parse path data: {e}")
        
        return None
    
    def path_to_shapely(self, path: SVGPath) -> Optional[Polygon]:
        """Convert SVG path to shapely Polygon for geometric operations."""
        if not SHAPELY_AVAILABLE:
            return None
        
        try:
            # Sample points along the path
            points = []
            for segment in path:
                if hasattr(segment, 'start'):
                    points.append((segment.start.real, segment.start.imag))
                if hasattr(segment, 'end'):
                    points.append((segment.end.real, segment.end.imag))
            
            if len(points) >= 3:
                return Polygon(points)
        except Exception as e:
            log.debug(f"Failed to convert path to shapely: {e}")
        
        return None
    
    def boolean_operation(self, path1: SVGPath, path2: SVGPath, operation: str) -> Optional[SVGPath]:
        """Perform boolean operations between two paths."""
        if not SHAPELY_AVAILABLE:
            log.warning("Boolean operations require shapely")
            return None
        
        try:
            poly1 = self.path_to_shapely(path1)
            poly2 = self.path_to_shapely(path2)
            
            if not poly1 or not poly2:
                return None
            
            if operation == "union":
                result = poly1.union(poly2)
            elif operation == "intersection":
                result = poly1.intersection(poly2)
            elif operation == "difference":
                result = poly1.difference(poly2)
            elif operation == "symmetric_difference":
                result = poly1.symmetric_difference(poly2)
            else:
                log.error(f"Unknown boolean operation: {operation}")
                return None
            
            # Convert back to SVG path (simplified)
            if result.geom_type == "Polygon":
                coords = list(result.exterior.coords)
                return self._coords_to_path(coords)
            elif result.geom_type == "MultiPolygon":
                # Take the largest polygon
                largest = max(result.geoms, key=lambda p: p.area)
                coords = list(largest.exterior.coords)
                return self._coords_to_path(coords)
        
        except Exception as e:
            log.error(f"Boolean operation failed: {e}")
        
        return None
    
    def _coords_to_path(self, coords: List[Tuple[float, float]]) -> SVGPath:
        """Convert coordinate list back to SVG path."""
        if len(coords) < 3:
            return SVGPath()
        
        segments = []
        for i, (x, y) in enumerate(coords):
            if i == 0:
                segments.append(Line(complex(x, y), complex(x, y)))
            else:
                prev_x, prev_y = coords[i-1]
                segments.append(Line(complex(prev_x, prev_y), complex(x, y)))
        
        return SVGPath(*segments)
    
    def transform_path(self, path: SVGPath, transform_type: str, **kwargs) -> SVGPath:
        """Apply geometric transformations to a path."""
        try:
            if transform_type == "scale":
                scale_x = kwargs.get('scale_x', 1.0)
                scale_y = kwargs.get('scale_y', 1.0)
                return path.scaled(scale_x, scale_y)
            
            elif transform_type == "rotate":
                angle = kwargs.get('angle', 0.0)
                center = kwargs.get('center', complex(0, 0))
                return path.rotated(angle, center)
            
            elif transform_type == "translate":
                dx = kwargs.get('dx', 0.0)
                dy = kwargs.get('dy', 0.0)
                return path.translated(complex(dx, dy))
            
            elif transform_type == "skew":
                skew_x = kwargs.get('skew_x', 0.0)
                skew_y = kwargs.get('skew_y', 0.0)
                # Apply skew transformation
                def skew_transform(z):
                    x, y = z.real, z.imag
                    new_x = x + y * math.tan(math.radians(skew_x))
                    new_y = y + x * math.tan(math.radians(skew_y))
                    return complex(new_x, new_y)
                
                return path.transformed(skew_transform)
            
            else:
                log.error(f"Unknown transform type: {transform_type}")
                return path
        
        except Exception as e:
            log.error(f"Transform failed: {e}")
            return path
    
    def morph_paths(self, path1: SVGPath, path2: SVGPath, t: float) -> SVGPath:
        """Morph between two paths using interpolation parameter t (0.0 to 1.0)."""
        if not (0.0 <= t <= 1.0):
            log.error(f"Interpolation parameter t must be between 0.0 and 1.0, got {t}")
            return path1
        
        try:
            # Simple linear interpolation of path segments
            # This is a basic implementation - more sophisticated morphing could be added
            segments = []
            
            # Get the shorter path length
            min_segments = min(len(path1), len(path2))
            
            for i in range(min_segments):
                seg1 = path1[i] if i < len(path1) else path1[-1]
                seg2 = path2[i] if i < len(path2) else path2[-1]
                
                # Interpolate start and end points
                start = self._interpolate_complex(seg1.start, seg2.start, t)
                end = self._interpolate_complex(seg1.end, seg2.end, t)
                
                # Create a line segment (could be enhanced for curves)
                segments.append(Line(start, end))
            
            return SVGPath(*segments)
        
        except Exception as e:
            log.error(f"Morphing failed: {e}")
            return path1
    
    def _interpolate_complex(self, z1: complex, z2: complex, t: float) -> complex:
        """Interpolate between two complex numbers."""
        return z1 + t * (z2 - z1)
    
    def validate_safe_area(self, path: SVGPath, bounds: Tuple[float, float, float, float]) -> bool:
        """Validate that path stays within safe bounds."""
        if not SHAPELY_AVAILABLE:
            log.warning("Safe area validation requires shapely")
            return True
        
        try:
            poly = self.path_to_shapely(path)
            if not poly:
                return False
            
            # Create safe area bounds
            x_min, y_min, x_max, y_max = bounds
            safe_bounds = Polygon([
                (x_min + self.safe_margins, y_min + self.safe_margins),
                (x_max - self.safe_margins, y_min + self.safe_margins),
                (x_max - self.safe_margins, y_max - self.safe_margins),
                (x_min + self.safe_margins, y_max - self.safe_margins)
            ])
            
            # Check if path is contained within safe bounds
            return safe_bounds.contains(poly)
        
        except Exception as e:
            log.error(f"Safe area validation failed: {e}")
            return False
    
    def export_svg(self, path: SVGPath, filename: str, viewbox: Tuple[float, float, float, float] = None) -> bool:
        """Export path to SVG file."""
        if not SVGWRITE_AVAILABLE:
            log.error("SVG export requires svgwrite")
            return False
        
        try:
            # Create SVG document
            dwg = svgwrite.Drawing(filename, size=('100%', '100%'))
            
            # Set viewBox if provided
            if viewbox:
                dwg.attribs['viewBox'] = ' '.join(map(str, viewbox))
            
            # Convert path to SVG path data
            path_data = path.d()
            
            # Add path element
            path_element = dwg.path(d=path_data, fill='none', stroke='black', stroke_width=1)
            dwg.add(path_element)
            
            # Save SVG
            dwg.save()
            log.info(f"Exported SVG to {filename}")
            return True
        
        except Exception as e:
            log.error(f"SVG export failed: {e}")
            return False


class MotifVariantGenerator:
    """Generate procedural variants of base SVG motifs."""
    
    def __init__(self, processor: SVGPathProcessor):
        self.processor = processor
        self._load_design_constraints()
    
    def _load_design_constraints(self):
        """Load design language constraints."""
        try:
            with open("design/design_language.json", "r") as f:
                self.design_constraints = json.load(f)
        except Exception as e:
            log.warning(f"Failed to load design constraints: {e}")
            self.design_constraints = {}
    
    def generate_boomerang_variants(self, base_path: SVGPath, count: int = 5, seed: Optional[int] = None) -> List[SVGPath]:
        """Generate variant boomerang shapes from base."""
        if seed is not None:
            random.seed(seed)
        
        variants = []
        base_bounds = self._get_path_bounds(base_path)
        
        for i in range(count):
            # Apply random transformations
            variant = base_path
            
            # Random scale variation
            scale_x = random.uniform(0.8, 1.2)
            scale_y = random.uniform(0.8, 1.2)
            variant = self.processor.transform_path(variant, "scale", scale_x=scale_x, scale_y=scale_y)
            
            # Random rotation
            angle = random.uniform(-45, 45)
            variant = self.processor.transform_path(variant, "rotate", angle=angle)
            
            # Random skew for organic feel
            skew_x = random.uniform(-10, 10)
            skew_y = random.uniform(-10, 10)
            variant = self.processor.transform_path(variant, "skew", skew_x=skew_x, skew_y=skew_y)
            
            # Validate safe area
            if self.processor.validate_safe_area(variant, base_bounds):
                variants.append(variant)
            else:
                log.warning(f"Variant {i} exceeds safe bounds, regenerating")
                # Try again with more conservative transformations
                variant = self._generate_conservative_variant(base_path)
                if variant:
                    variants.append(variant)
        
        if seed is not None:
            random.seed()
        
        return variants
    
    def generate_starburst_variants(self, base_path: SVGPath, count: int = 5, seed: Optional[int] = None) -> List[SVGPath]:
        """Generate variant starburst shapes from base."""
        if seed is not None:
            random.seed(seed)
        
        variants = []
        base_bounds = self._get_path_bounds(base_path)
        
        for i in range(count):
            variant = base_path
            
            # Random rotation for starburst effect
            angle = random.uniform(0, 360)
            variant = self.processor.transform_path(variant, "rotate", angle=angle)
            
            # Random scale
            scale = random.uniform(0.7, 1.3)
            variant = self.processor.transform_path(variant, "scale", scale_x=scale, scale_y=scale)
            
            # Validate safe area
            if self.processor.validate_safe_area(variant, base_bounds):
                variants.append(variant)
            else:
                variant = self._generate_conservative_variant(base_path)
                if variant:
                    variants.append(variant)
        
        if seed is not None:
            random.seed()
        
        return variants
    
    def generate_abstract_cutout_variants(self, base_path: SVGPath, count: int = 5, seed: Optional[int] = None) -> List[SVGPath]:
        """Generate abstract cutout variants using boolean operations."""
        if seed is not None:
            random.seed(seed)
        
        variants = []
        base_bounds = self._get_path_bounds(base_path)
        
        for i in range(count):
            # Create a simple geometric shape for boolean operations
            geometric_shape = self._create_geometric_shape(base_bounds)
            
            # Random boolean operation
            operation = random.choice(["union", "intersection", "difference"])
            variant = self.processor.boolean_operation(base_path, geometric_shape, operation)
            
            if variant and self.processor.validate_safe_area(variant, base_bounds):
                variants.append(variant)
            else:
                # Fallback to simple transformation
                variant = self._generate_conservative_variant(base_path)
                if variant:
                    variants.append(variant)
        
        if seed is not None:
            random.seed()
        
        return variants
    
    def _create_geometric_shape(self, bounds: Tuple[float, float, float, float]) -> SVGPath:
        """Create a simple geometric shape for boolean operations."""
        x_min, y_min, x_max, y_max = bounds
        width = x_max - x_min
        height = y_max - y_min
        
        # Create a circle or rectangle
        if random.choice([True, False]):
            # Circle
            center_x = (x_min + x_max) / 2
            center_y = (y_min + y_max) / 2
            radius = min(width, height) / 4
            
            # Approximate circle with bezier curves
            segments = []
            for i in range(4):
                angle = i * 90
                next_angle = (i + 1) * 90
                
                start_x = center_x + radius * math.cos(math.radians(angle))
                start_y = center_y + radius * math.sin(math.radians(angle))
                end_x = center_x + radius * math.cos(math.radians(next_angle))
                end_y = center_y + radius * math.sin(math.radians(next_angle))
                
                # Control points for smooth curve
                cp1_x = center_x + radius * 1.5 * math.cos(math.radians(angle + 45))
                cp1_y = center_y + radius * 1.5 * math.sin(math.radians(angle + 45))
                cp2_x = center_x + radius * 1.5 * math.cos(math.radians(next_angle - 45))
                cp2_y = center_y + radius * 1.5 * math.sin(math.radians(next_angle - 45))
                
                if i == 0:
                    segments.append(Line(complex(start_x, start_y), complex(start_x, start_y)))
                
                segments.append(CubicBezier(
                    complex(start_x, start_y),
                    complex(cp1_x, cp1_y),
                    complex(cp2_x, cp2_y),
                    complex(end_x, end_y)
                ))
            
            return SVGPath(*segments)
        else:
            # Rectangle
            points = [
                complex(x_min + width/4, y_min + height/4),
                complex(x_max - width/4, y_min + height/4),
                complex(x_max - width/4, y_max - height/4),
                complex(x_min + width/4, y_max - height/4)
            ]
            
            segments = []
            for i, point in enumerate(points):
                if i == 0:
                    segments.append(Line(point, point))
                else:
                    segments.append(Line(points[i-1], point))
            
            segments.append(Line(points[-1], points[0]))  # Close the rectangle
            return SVGPath(*segments)
    
    def _generate_conservative_variant(self, base_path: SVGPath) -> Optional[SVGPath]:
        """Generate a conservative variant that respects safe bounds."""
        # Simple scale down
        variant = self.processor.transform_path(base_path, "scale", scale_x=0.9, scale_y=0.9)
        return variant
    
    def _get_path_bounds(self, path: SVGPath) -> Tuple[float, float, float, float]:
        """Get bounding box of a path."""
        if not path:
            return (0, 0, 100, 100)
        
        x_coords = []
        y_coords = []
        
        for segment in path:
            if hasattr(segment, 'start'):
                x_coords.append(segment.start.real)
                y_coords.append(segment.start.imag)
            if hasattr(segment, 'end'):
                x_coords.append(segment.end.real)
                y_coords.append(segment.end.imag)
        
        if not x_coords:
            return (0, 0, 100, 100)
        
        return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))


# Convenience functions for easy integration
def create_path_processor(safe_margins: int = SAFE_MARGINS_PX) -> SVGPathProcessor:
    """Create a configured SVG path processor."""
    return SVGPathProcessor(safe_margins)


def create_variant_generator(processor: Optional[SVGPathProcessor] = None) -> MotifVariantGenerator:
    """Create a configured motif variant generator."""
    if processor is None:
        processor = create_path_processor()
    return MotifVariantGenerator(processor)


def generate_motif_variants(
    base_svg_path: str, 
    motif_type: str, 
    count: int = 5, 
    output_dir: str = "assets/generated",
    seed: Optional[int] = None
) -> List[str]:
    """Generate variants of a base motif and save them to files."""
    processor = create_path_processor()
    generator = create_variant_generator(processor)
    
    # Parse base SVG
    with open(base_svg_path, 'r') as f:
        svg_content = f.read()
    
    base_path = processor.parse_svg_path(svg_content)
    if not base_path:
        log.error(f"Failed to parse base SVG: {base_svg_path}")
        return []
    
    # Generate variants based on type
    if motif_type == "boomerang":
        variants = generator.generate_boomerang_variants(base_path, count, seed)
    elif motif_type == "starburst":
        variants = generator.generate_starburst_variants(base_path, count, seed)
    elif motif_type == "abstract":
        variants = generator.generate_abstract_cutout_variants(base_path, count, seed)
    else:
        log.error(f"Unknown motif type: {motif_type}")
        return []
    
    # Save variants
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    saved_files = []
    base_name = Path(base_svg_path).stem
    
    for i, variant in enumerate(variants):
        filename = f"{base_name}_variant_{i:02d}.svg"
        filepath = output_path / filename
        
        if processor.export_svg(variant, str(filepath)):
            saved_files.append(str(filepath))
    
    log.info(f"Generated {len(saved_files)} variants of {base_svg_path}")
    return saved_files
