#!/usr/bin/env python3
"""
SVG Geometry Engine Core

Provides a robust geometry toolkit for SVG path operations used by the asset generator 
and micro-animations. Supports boolean operations, path offsets, morphing, and 
programmatic assembly of motifs/icons.

All operations respect brand design constraints and include validation.
"""

import json
import logging
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, TYPE_CHECKING

from bin.core import get_logger

log = get_logger("svg_geom")

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
    log.warning("shapely not available - boolean operations will use fallbacks")

try:
    import svgwrite
    SVGWRITE_AVAILABLE = True
except ImportError:
    SVGWRITE_AVAILABLE = False
    svgwrite = Any
    log.warning("svgwrite not available - SVG export will use string concatenation")


class SVGGeometryEngine:
    """Core SVG geometry operations with fallbacks and validation."""
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize the geometry engine with optional seed for deterministic output."""
        self.seed = seed
        if seed is not None:
            random.seed(seed)
        
        self._validate_dependencies()
        self._validation_errors = []
    
    def _validate_dependencies(self):
        """Validate that required dependencies are available."""
        if not SVG_PATHS_AVAILABLE:
            log.error("svgpathtools is required for path operations")
            raise ImportError("svgpathtools is required for path operations")
        if not SVG_ELEMENTS_AVAILABLE:
            log.error("svgelements is required for SVG parsing")
            raise ImportError("svgelements is required for SVG parsing")
    
    def _log_validation_error(self, operation: str, error: str):
        """Log validation errors for reporting."""
        self._validation_errors.append({
            "operation": operation,
            "error": error,
            "timestamp": logging.Formatter().formatTime(logging.LogRecord(
                "svg_geom", logging.INFO, "", 0, "", (), None
            ))
        })
        log.warning(f"Validation error in {operation}: {error}")


def load_svg_paths(path: str) -> List[Dict]:
    """
    Load SVG paths from file and return list of path data with attributes.
    
    Args:
        path: Path to SVG file
        
    Returns:
        List of dicts with 'd' (path data) and 'fill' (color) attributes
        
    Raises:
        FileNotFoundError: If SVG file doesn't exist
        ValueError: If SVG parsing fails
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"SVG file not found: {path}")
    
    if not SVG_ELEMENTS_AVAILABLE:
        raise ImportError("svgelements required for SVG parsing")
    
    try:
        with open(path, 'r') as f:
            svg_content = f.read()
        
        svg = svgelements.SVG.parse(svg_content)
        paths = []
        
        for path_elem in svg.select("path"):
            path_data = {
                'd': path_elem.d,
                'fill': getattr(path_elem, 'fill', '#000000')
            }
            paths.append(path_data)
        
        log.info(f"Loaded {len(paths)} paths from {path}")
        return paths
        
    except Exception as e:
        log.error(f"Failed to parse SVG {path}: {e}")
        raise ValueError(f"SVG parsing failed: {e}")


def boolean_union(paths: List) -> List:
    """
    Perform boolean union operation on list of paths.
    
    Args:
        paths: List of SVG path data strings or objects
        
    Returns:
        List of unified paths. Falls back to input if shapely unavailable.
    """
    if not SHAPELY_AVAILABLE:
        log.warning("shapely not available - returning original paths")
        return paths
    
    if not SVG_PATHS_AVAILABLE:
        log.warning("svgpathtools not available - returning original paths")
        return paths
    
    try:
        # Convert paths to shapely polygons
        polygons = []
        for path_data in paths:
            if isinstance(path_data, str):
                path_obj = svgpathtools.parse_path(path_data)
            else:
                path_obj = path_data
            
            # Sample points along path for polygon creation
            points = []
            for segment in path_obj:
                if hasattr(segment, 'start'):
                    points.append((segment.start.real, segment.start.imag))
                if hasattr(segment, 'end'):
                    points.append((segment.end.real, segment.end.imag))
            
            if len(points) >= 3:
                try:
                    poly = Polygon(points)
                    if poly.is_valid:
                        polygons.append(poly)
                except Exception as e:
                    log.debug(f"Failed to create polygon from path: {e}")
        
        if not polygons:
            log.warning("No valid polygons created from paths")
            return paths
        
        # Perform union
        union_result = unary_union(polygons)
        
        # Convert back to paths
        result_paths = []
        if union_result.geom_type == "Polygon":
            result_paths.append(_polygon_to_path(union_result))
        elif union_result.geom_type == "MultiPolygon":
            for poly in union_result.geoms:
                result_paths.append(_polygon_to_path(poly))
        
        log.info(f"Boolean union: {len(paths)} paths -> {len(result_paths)} unified paths")
        return result_paths
        
    except Exception as e:
        log.error(f"Boolean union failed: {e}")
        return paths


def inset_path(path_d: str, delta: float) -> str:
    """
    Create inset (offset) version of SVG path.
    
    Args:
        path_d: SVG path data string
        delta: Offset distance (positive for inset, negative for outset)
        
    Returns:
        New path data string
    """
    if not SVG_PATHS_AVAILABLE:
        log.warning("svgpathtools not available - returning original path")
        return path_d
    
    try:
        path = svgpathtools.parse_path(path_d)
        
        # Simple offset by scaling around centroid
        if delta == 0:
            return path_d
        
        # Calculate centroid
        total_x = 0
        total_y = 0
        point_count = 0
        
        for segment in path:
            if hasattr(segment, 'start'):
                total_x += segment.start.real
                total_y += segment.start.imag
                point_count += 1
            if hasattr(segment, 'end'):
                total_x += segment.end.real
                total_y += segment.end.imag
                point_count += 1
        
        if point_count == 0:
            return path_d
        
        centroid_x = total_x / point_count
        centroid_y = total_y / point_count
        
        # Scale factor for offset
        scale_factor = 1.0 + (delta / 100.0)  # Simple scaling approach
        
        # Create offset path
        offset_segments = []
        for segment in path:
            if hasattr(segment, 'start') and hasattr(segment, 'end'):
                # Scale around centroid
                new_start = complex(
                    centroid_x + (segment.start.real - centroid_x) * scale_factor,
                    centroid_y + (segment.start.imag - centroid_y) * scale_factor
                )
                new_end = complex(
                    centroid_x + (segment.end.real - centroid_x) * scale_factor,
                    centroid_y + (segment.end.imag - centroid_y) * scale_factor
                )
                
                if isinstance(segment, Line):
                    offset_segments.append(Line(new_start, new_end))
                elif isinstance(segment, CubicBezier):
                    # Handle control points for cubic bezier
                    if hasattr(segment, 'control1') and hasattr(segment, 'control2'):
                        c1 = complex(
                            centroid_x + (segment.control1.real - centroid_x) * scale_factor,
                            centroid_y + (segment.control1.imag - centroid_y) * scale_factor
                        )
                        c2 = complex(
                            centroid_x + (segment.control2.real - centroid_x) * scale_factor,
                            centroid_y + (segment.control2.imag - centroid_y) * scale_factor
                        )
                        offset_segments.append(CubicBezier(new_start, c1, c2, new_end))
                    else:
                        offset_segments.append(CubicBezier(new_start, new_start, new_end, new_end))
                else:
                    # Fallback for other segment types
                    offset_segments.append(Line(new_start, new_end))
        
        offset_path = SVGPath(*offset_segments)
        return str(offset_path)
        
    except Exception as e:
        log.error(f"Path inset failed: {e}")
        return path_d


def morph_paths(src_paths: List, tgt_paths: List, t: float, seed: Optional[int] = None) -> List:
    """
    Morph between source and target paths using interpolation.
    
    Args:
        src_paths: Source path data list
        tgt_paths: Target path data list
        t: Interpolation factor (0.0 to 1.0)
        seed: Optional seed for deterministic morphing
        
    Returns:
        List of morphed paths
    """
    if not SVG_PATHS_AVAILABLE:
        log.warning("svgpathtools not available - returning source paths")
        return src_paths
    
    if seed is not None:
        random.seed(seed)
    
    try:
        # Ensure we have the same number of paths
        max_paths = max(len(src_paths), len(tgt_paths))
        morphed_paths = []
        
        for i in range(max_paths):
            src_path_data = src_paths[i] if i < len(src_paths) else src_paths[-1]
            tgt_path_data = tgt_paths[i] if i < len(tgt_paths) else tgt_paths[-1]
            
            # Parse paths
            src_path = svgpathtools.parse_path(src_path_data if isinstance(src_path_data, str) else src_path_data['d'])
            tgt_path = svgpathtools.parse_path(tgt_path_data if isinstance(tgt_path_data, str) else tgt_path_data['d'])
            
            # Interpolate path segments
            morphed_segments = []
            max_segments = max(len(src_path), len(tgt_path))
            
            for j in range(max_segments):
                src_segment = src_path[j] if j < len(src_path) else src_path[-1]
                tgt_segment = tgt_path[j] if j < len(tgt_path) else tgt_path[-1]
                
                # Interpolate segment endpoints
                if hasattr(src_segment, 'start') and hasattr(tgt_segment, 'start'):
                    start_x = src_segment.start.real * (1 - t) + tgt_segment.start.real * t
                    start_y = src_segment.start.imag * (1 - t) + tgt_segment.start.imag * t
                    start_point = complex(start_x, start_y)
                else:
                    start_point = complex(0, 0)
                
                if hasattr(src_segment, 'end') and hasattr(tgt_segment, 'end'):
                    end_x = src_segment.end.real * (1 - t) + tgt_segment.end.real * t
                    end_y = src_segment.end.imag * (1 - t) + tgt_segment.end.imag * t
                    end_point = complex(end_x, end_y)
                else:
                    end_point = complex(0, 0)
                
                # Create morphed segment (simplified to Line for stability)
                morphed_segments.append(Line(start_point, end_point))
            
            morphed_path = SVGPath(*morphed_segments)
            morphed_paths.append(morphed_path)
        
        log.info(f"Morphed {len(src_paths)} -> {len(tgt_paths)} paths at t={t}")
        return morphed_paths
        
    except Exception as e:
        log.error(f"Path morphing failed: {e}")
        return src_paths


def assemble_icon(primitives: List[Dict], palette: List[str], seed: Optional[int] = None) -> str:
    """
    Assemble an icon from primitive shapes using the specified palette.
    
    Args:
        primitives: List of primitive definitions with 'type', 'params', 'fill'
        palette: List of color hex codes
        seed: Optional seed for deterministic assembly
        
    Returns:
        SVG XML string
    """
    if seed is not None:
        random.seed(seed)
    
    if not SVGWRITE_AVAILABLE:
        # Fallback to string concatenation
        return _assemble_icon_fallback(primitives, palette, seed)
    
    try:
        # Create SVG drawing
        dwg = svgwrite.Drawing(size=('100', '100'))
        
        # Add description with parameters
        dwg.add(dwg.desc(f"Assembled icon with {len(primitives)} primitives, seed: {seed}"))
        
        # Add primitives
        for i, primitive in enumerate(primitives):
            if primitive['type'] == 'circle':
                circle = dwg.circle(
                    center=(primitive['params'].get('cx', 50), primitive['params'].get('cy', 50)),
                    r=primitive['params'].get('r', 20),
                    fill=primitive.get('fill', random.choice(palette))
                )
                dwg.add(circle)
            
            elif primitive['type'] == 'rect':
                rect = dwg.rect(
                    insert=(primitive['params'].get('x', 10), primitive['params'].get('y', 10)),
                    size=(primitive['params'].get('width', 30), primitive['params'].get('height', 30)),
                    fill=primitive.get('fill', random.choice(palette))
                )
                dwg.add(rect)
            
            elif primitive['type'] == 'path':
                path = dwg.path(
                    d=primitive['params'].get('d', 'M10,10 L90,90'),
                    fill=primitive.get('fill', random.choice(palette))
                )
                dwg.add(path)
        
        svg_str = dwg.tostring()
        log.info(f"Assembled icon with {len(primitives)} primitives")
        return svg_str
        
    except Exception as e:
        log.error(f"Icon assembly failed: {e}")
        return _assemble_icon_fallback(primitives, palette, seed)


def _assemble_icon_fallback(primitives: List[Dict], palette: List[str], seed: Optional[int] = None) -> str:
    """Fallback icon assembly using string concatenation."""
    svg_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">',
        f'<desc>Assembled icon with {len(primitives)} primitives, seed: {seed}</desc>'
    ]
    
    for primitive in primitives:
        if primitive['type'] == 'circle':
            cx = primitive['params'].get('cx', 50)
            cy = primitive['params'].get('cy', 50)
            r = primitive['params'].get('r', 20)
            fill = primitive.get('fill', random.choice(palette))
            svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>')
        
        elif primitive['type'] == 'rect':
            x = primitive['params'].get('x', 10)
            y = primitive['params'].get('y', 10)
            width = primitive['params'].get('width', 30)
            height = primitive['params'].get('height', 30)
            fill = primitive.get('fill', random.choice(palette))
            svg_parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{fill}"/>')
        
        elif primitive['type'] == 'path':
            d = primitive['params'].get('d', 'M10,10 L90,90')
            fill = primitive.get('fill', random.choice(palette))
            svg_parts.append(f'<path d="{d}" fill="{fill}"/>')
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def save_svg(svg_str: str, out_path: str) -> None:
    """
    Save SVG string to file.
    
    Args:
        svg_str: SVG XML string
        out_path: Output file path
    """
    try:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(out_file, 'w') as f:
            f.write(svg_str)
        
        log.info(f"Saved SVG to {out_path}")
        
    except Exception as e:
        log.error(f"Failed to save SVG to {out_path}: {e}")
        raise


def _polygon_to_path(polygon: 'Polygon') -> str:
    """Convert shapely polygon to SVG path string."""
    if not hasattr(polygon, 'exterior'):
        return ""
    
    coords = list(polygon.exterior.coords)
    if len(coords) < 3:
        return ""
    
    path_parts = []
    for i, (x, y) in enumerate(coords):
        if i == 0:
            path_parts.append(f"M{x},{y}")
        else:
            path_parts.append(f"L{x},{y}")
    
    path_parts.append("Z")  # Close path
    return " ".join(path_parts)


def validate_geometry(paths: List[str]) -> Dict:
    """
    Validate geometry for common issues.
    
    Args:
        paths: List of SVG path data strings
        
    Returns:
        Validation report dictionary
    """
    report = {
        "total_paths": len(paths),
        "valid_paths": 0,
        "errors": [],
        "warnings": []
    }
    
    for i, path_data in enumerate(paths):
        try:
            if not SVG_PATHS_AVAILABLE:
                continue
            
            # Handle both string and path object inputs
            if isinstance(path_data, str):
                path = svgpathtools.parse_path(path_data)
            else:
                path = path_data
            
            # Check for NaN values
            has_nan = False
            for segment in path:
                if hasattr(segment, 'start'):
                    if math.isnan(segment.start.real) or math.isnan(segment.start.imag):
                        has_nan = True
                        break
                if hasattr(segment, 'end'):
                    if math.isnan(segment.end.real) or math.isnan(segment.end.imag):
                        has_nan = True
                        break
            
            if has_nan:
                report["errors"].append(f"Path {i}: Contains NaN values")
                continue
            
            # Check bounds
            if hasattr(path, 'bbox'):
                bbox = path.bbox()
                if bbox and len(bbox) == 4:
                    width = abs(bbox[2] - bbox[0])
                    height = abs(bbox[3] - bbox[1])
                    
                    if width > 10000 or height > 10000:
                        report["warnings"].append(f"Path {i}: Very large bounds ({width:.1f}x{height:.1f})")
                    
                    if width < 0.1 or height < 0.1:
                        report["warnings"].append(f"Path {i}: Very small bounds ({width:.3f}x{height:.3f})")
            
            report["valid_paths"] += 1
            
        except Exception as e:
            report["errors"].append(f"Path {i}: Parse error - {e}")
    
    return report


def write_validation_report(report: Dict, output_path: str) -> None:
    """Write geometry validation report to JSON file."""
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        log.info(f"Validation report written to {output_path}")
        
    except Exception as e:
        log.error(f"Failed to write validation report: {e}")
        raise
