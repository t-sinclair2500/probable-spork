#!/usr/bin/env python3
"""
Layout Engine for Procedural Animatics Toolkit

Provides deterministic, art-directed layout utilities for scenes to avoid collisions,
respect safe margins, and feel intentionally composed.

All units in pixels; scene size = VIDEO_W × VIDEO_H from sdk.
"""

import math
import random
import time
from typing import Dict, List, Optional, Tuple, Union

from .sdk import VIDEO_W, VIDEO_H, SAFE_MARGINS_PX


class LayoutEngine:
    """Main layout engine class providing deterministic layout algorithms."""
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize layout engine with optional seed for deterministic results."""
        self.seed = seed
        if seed is not None:
            random.seed(seed)
        self._rng = random.Random(seed if seed is not None else time.time())
    
    def poisson_points(self, w: int, h: int, r: int, k: int = 30, seed: Optional[int] = None) -> List[Tuple[float, float]]:
        """
        Generate Poisson-disk distributed points using Bridson's algorithm.
        
        Args:
            w: Width of the area
            h: Height of the area
            r: Minimum distance between points
            k: Maximum attempts per point
            seed: Optional seed for deterministic results
            
        Returns:
            List of (x, y) coordinate tuples
        """
        if seed is not None:
            local_rng = random.Random(seed)
        else:
            local_rng = self._rng
            
        # Initialize grid for spatial partitioning
        cell_size = r / math.sqrt(2)
        cols = int(w / cell_size) + 1
        rows = int(h / cell_size) + 1
        grid = [[None for _ in range(cols)] for _ in range(rows)]
        
        points = []
        active_list = []
        
        # Add first point at center
        first_point = (w / 2, h / 2)
        points.append(first_point)
        active_list.append(first_point)
        
        # Add to grid
        col = int(first_point[0] / cell_size)
        row = int(first_point[1] / cell_size)
        grid[row][col] = first_point
        
        while active_list:
            # Pick random active point
            point_idx = local_rng.randint(0, len(active_list) - 1)
            point = active_list[point_idx]
            
            # Try to generate new points around this one
            success = False
            for _ in range(k):
                # Generate point at random distance between r and 2r
                angle = local_rng.uniform(0, 2 * math.pi)
                distance = local_rng.uniform(r, 2 * r)
                new_point = (
                    point[0] + distance * math.cos(angle),
                    point[1] + distance * math.sin(angle)
                )
                
                # Check bounds
                if not (0 <= new_point[0] < w and 0 <= new_point[1] < h):
                    continue
                
                # Check if too close to existing points
                col = int(new_point[0] / cell_size)
                row = int(new_point[1] / cell_size)
                
                # Check surrounding cells
                too_close = False
                for drow in range(max(0, row - 2), min(rows, row + 3)):
                    for dcol in range(max(0, col - 2), min(cols, col + 3)):
                        if grid[drow][dcol] is not None:
                            dist = math.sqrt(
                                (new_point[0] - grid[drow][dcol][0]) ** 2 +
                                (new_point[1] - grid[drow][dcol][1]) ** 2
                            )
                            if dist < r:
                                too_close = True
                                break
                    if too_close:
                        break
                
                if not too_close:
                    points.append(new_point)
                    active_list.append(new_point)
                    grid[row][col] = new_point
                    success = True
                    break
            
            if not success:
                # Remove point from active list
                active_list.pop(point_idx)
        
        return points
    
    def thirds_grid(self, w: int, h: int) -> Dict[str, Tuple[int, int]]:
        """
        Calculate rule-of-thirds grid intersection points.
        
        Args:
            w: Width of the area
            h: Height of the area
            
        Returns:
            Dictionary with keys 'T1', 'T2', 'T3', 'T4' mapping to (x, y) coordinates
        """
        third_w = w / 3
        third_h = h / 3
        
        return {
            'T1': (int(third_w), int(third_h)),           # Top-left intersection
            'T2': (int(2 * third_w), int(third_h)),       # Top-right intersection
            'T3': (int(third_w), int(2 * third_h)),       # Bottom-left intersection
            'T4': (int(2 * third_w), int(2 * third_h))    # Bottom-right intersection
        }
    
    def place_non_overlapping(self, rects: List[Tuple[int, int]], min_gap: int, seed: Optional[int] = None) -> List[Tuple[int, int]]:
        """
        Place rectangles without overlapping, respecting safe margins.
        
        Args:
            rects: List of (width, height) tuples
            min_gap: Minimum gap between rectangles
            seed: Optional seed for deterministic results
            
        Returns:
            List of (x, y) positions for each rectangle
        """
        if seed is not None:
            local_rng = random.Random(seed)
        else:
            local_rng = self._rng
            
        # Available area (respecting safe margins)
        available_w = VIDEO_W - 2 * SAFE_MARGINS_PX
        available_h = VIDEO_H - 2 * SAFE_MARGINS_PX
        
        positions = []
        placed_rects = []  # List of (x, y, w, h) tuples
        
        for rect_w, rect_h in rects:
            best_position = None
            best_overlap = float('inf')
            
            # Try multiple random positions
            for attempt in range(100):
                x = local_rng.randint(SAFE_MARGINS_PX, SAFE_MARGINS_PX + available_w - rect_w)
                y = local_rng.randint(SAFE_MARGINS_PX, SAFE_MARGINS_PX + available_h - rect_h)
                
                # Check overlap with existing rectangles
                total_overlap = 0
                for px, py, pw, ph in placed_rects:
                    # Calculate overlap area
                    overlap_x = max(0, min(x + rect_w, px + pw) - max(x, px))
                    overlap_y = max(0, min(y + rect_h, py + ph) - max(y, py))
                    overlap_area = overlap_x * overlap_y
                    total_overlap += overlap_area
                
                # Check if position is better
                if total_overlap < best_overlap:
                    best_overlap = total_overlap
                    best_position = (x, y)
                    
                    # If no overlap, this is perfect
                    if total_overlap == 0:
                        break
            
            if best_position is None:
                # Fallback: place at safe margin
                best_position = (SAFE_MARGINS_PX, SAFE_MARGINS_PX)
            
            positions.append(best_position)
            placed_rects.append((best_position[0], best_position[1], rect_w, rect_h))
        
        return positions
    
    def pack_text_blocks(self, blocks: List[Dict], container: Tuple[int, int] = (VIDEO_W, VIDEO_H), margin: int = SAFE_MARGINS_PX) -> List[Dict]:
        """
        Pack text blocks efficiently within container using skyline algorithm.
        
        Args:
            blocks: List of dicts with 'w', 'h', 'id' keys
            container: (width, height) of container
            margin: Safe margin from edges
            
        Returns:
            List of dicts with x, y positions added
        """
        if not blocks:
            return []
        
        # Sort blocks by height (tallest first) for better skyline packing
        sorted_blocks = sorted(blocks, key=lambda b: b['h'], reverse=True)
        
        # Initialize skyline (list of (x, y, width) tuples representing available space)
        skyline = [(margin, margin, container[0] - 2 * margin)]
        
        result = []
        
        for block in sorted_blocks:
            block_w = block['w']
            block_h = block['h']
            
            # Find best position in skyline
            best_x = None
            best_y = None
            best_skyline_idx = None
            
            for i, (sx, sy, sw) in enumerate(skyline):
                if sw >= block_w:  # Skyline segment is wide enough
                    # Check if height fits
                    if sy + block_h <= container[1] - margin:
                        if best_x is None or sy < best_y:
                            best_x = sx
                            best_y = sy
                            best_skyline_idx = i
            
            if best_x is None:
                # No suitable position found, place at bottom
                best_x = margin
                best_y = container[1] - margin - block_h
                best_skyline_idx = 0
            
            # Update skyline
            sx, sy, sw = skyline[best_skyline_idx]
            
            # Split skyline segment
            new_segments = []
            if best_x > sx:
                new_segments.append((sx, sy, best_x - sx))
            
            new_segments.append((best_x, best_y + block_h, block_w))
            
            if best_x + block_w < sx + sw:
                new_segments.append((best_x + block_w, sy, sx + sw - (best_x + block_w)))
            
            # Replace old segment with new ones
            skyline.pop(best_skyline_idx)
            for seg in reversed(new_segments):
                if seg[2] > 0:  # Only add non-zero width segments
                    skyline.insert(best_skyline_idx, seg)
            
            # Add result
            result.append({
                **block,
                'x': best_x,
                'y': best_y
            })
        
        return result
    
    def apply_constraints(self, items: List[Dict], constraints: List[Dict]) -> List[Dict]:
        """
        Apply layout constraints to items.
        
        Args:
            items: List of item dicts with x, y, w, h keys
            constraints: List of constraint dicts
            
        Returns:
            List of items with constraints applied
        """
        result = items.copy()
        
        for constraint in constraints:
            constraint_type = constraint.get('type')
            
            if constraint_type == 'keep_inside':
                margin = constraint.get('margin', SAFE_MARGINS_PX)
                for item in result:
                    # Ensure item stays within safe bounds
                    if 'x' in item and 'y' in item and 'w' in item and 'h' in item:
                        item['x'] = max(margin, min(item['x'], VIDEO_W - margin - item['w']))
                        item['y'] = max(margin, min(item['y'], VIDEO_H - margin - item['h']))
            
            elif constraint_type == 'align':
                target = constraint.get('target')
                ids_to_align = constraint.get('ids', [])
                
                if target in ['T1', 'T2', 'T3', 'T4']:
                    # Align to rule-of-thirds
                    thirds = self.thirds_grid(VIDEO_W, VIDEO_H)
                    target_pos = thirds[target]
                    
                    for item in result:
                        if item.get('id') in ids_to_align:
                            # Center item on target position
                            if 'w' in item and 'h' in item:
                                item['x'] = target_pos[0] - item['w'] // 2
                                item['y'] = target_pos[1] - item['h'] // 2
            
            elif constraint_type == 'distribute_horizontal':
                ids_to_distribute = constraint.get('ids', [])
                if len(ids_to_distribute) > 1:
                    # Find items to distribute
                    items_to_distribute = [item for item in result if item.get('id') in ids_to_distribute]
                    if items_to_distribute:
                        # Calculate total width and spacing
                        total_width = sum(item.get('w', 0) for item in items_to_distribute)
                        available_width = VIDEO_W - 2 * SAFE_MARGINS_PX
                        spacing = (available_width - total_width) / (len(items_to_distribute) - 1) if len(items_to_distribute) > 1 else 0
                        
                        # Position items
                        current_x = SAFE_MARGINS_PX
                        for item in items_to_distribute:
                            item['x'] = current_x
                            current_x += item.get('w', 0) + spacing
            
            elif constraint_type == 'distribute_vertical':
                ids_to_distribute = constraint.get('ids', [])
                if len(ids_to_distribute) > 1:
                    # Find items to distribute
                    items_to_distribute = [item for item in result if item.get('id') in ids_to_distribute]
                    if items_to_distribute:
                        # Calculate total height and spacing
                        total_height = sum(item.get('h', 0) for item in items_to_distribute)
                        available_height = VIDEO_H - 2 * SAFE_MARGINS_PX
                        spacing = (available_height - total_height) / (len(items_to_distribute) - 1) if len(items_to_distribute) > 1 else 0
                        
                        # Position items
                        current_y = SAFE_MARGINS_PX
                        for item in items_to_distribute:
                            item['y'] = current_y
                            current_y += item.get('h', 0) + spacing
        
        return result


# Convenience functions that create a default engine instance
def poisson_points(w: int, h: int, r: int, k: int = 30, seed: Optional[int] = None) -> List[Tuple[float, float]]:
    """Generate Poisson-disk distributed points."""
    engine = LayoutEngine(seed)
    return engine.poisson_points(w, h, r, k, seed)


def thirds_grid(w: int, h: int) -> Dict[str, Tuple[int, int]]:
    """Calculate rule-of-thirds grid intersection points."""
    engine = LayoutEngine()
    return engine.thirds_grid(w, h)


def place_non_overlapping(rects: List[Tuple[int, int]], min_gap: int, seed: Optional[int] = None) -> List[Tuple[int, int]]:
    """Place rectangles without overlapping."""
    engine = LayoutEngine(seed)
    return engine.place_non_overlapping(rects, min_gap, seed)


def pack_text_blocks(blocks: List[Dict], container: Tuple[int, int] = (VIDEO_W, VIDEO_H), margin: int = SAFE_MARGINS_PX) -> List[Dict]:
    """Pack text blocks efficiently within container."""
    engine = LayoutEngine()
    return engine.pack_text_blocks(blocks, container, margin)


def apply_constraints(items: List[Dict], constraints: List[Dict]) -> List[Dict]:
    """Apply layout constraints to items."""
    engine = LayoutEngine()
    return engine.apply_constraints(items, constraints)
