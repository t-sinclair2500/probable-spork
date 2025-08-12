#!/usr/bin/env python3
"""
Voiceover Cues Parser for Scene Alignment

This script reads SRT caption files and generates voiceover cues that can be used
to align scenes with audio timing. Outputs JSON with start/end timestamps for
each scene section.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import (
    BASE,
    get_logger,
    guard_system,
    load_config,
    log_state,
    single_lock,
)

log = get_logger("voice_cues")


def parse_srt_timestamp(timestamp: str) -> int:
    """
    Parse SRT timestamp format (HH:MM:SS,mmm) to milliseconds.
    
    Args:
        timestamp: SRT timestamp string
        
    Returns:
        Timestamp in milliseconds
    """
    # Handle format: 00:00:00,000
    time_parts = timestamp.replace(',', '.').split(':')
    hours = int(time_parts[0])
    minutes = int(time_parts[1])
    seconds = float(time_parts[2])
    
    total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
    return int(total_ms)


def parse_srt_file(srt_path: str) -> List[Tuple[int, int, str]]:
    """
    Parse SRT file and extract timing information.
    
    Args:
        srt_path: Path to SRT file
        
    Returns:
        List of (start_ms, end_ms, text) tuples
    """
    if not os.path.exists(srt_path):
        log.warning(f"SRT file not found: {srt_path}")
        return []
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # SRT format: number, timestamp --> timestamp, text
    pattern = r'(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})\s+([\s\S]*?)(?=\n\d+\n|$)'
    matches = re.findall(pattern, content)
    
    cues = []
    for match in matches:
        number = int(match[0])
        start_time = parse_srt_timestamp(match[1])
        end_time = parse_srt_timestamp(match[2])
        text = match[3].strip()
        
        cues.append((start_time, end_time, text))
    
    log.info(f"Parsed {len(cues)} cues from SRT file")
    return cues


def map_cues_to_scenes(cues: List[Tuple[int, int, str]], 
                       scenescript_path: str) -> Dict[str, Dict[str, any]]:
    """
    Map voiceover cues to scenes based on timing.
    
    Args:
        cues: List of (start_ms, end_ms, text) tuples
        scenescript_path: Path to SceneScript file
        
    Returns:
        Dictionary mapping scene IDs to audio cue information
    """
    if not os.path.exists(scenescript_path):
        log.warning(f"SceneScript not found: {scenescript_path}")
        return {}
    
    with open(scenescript_path, 'r', encoding='utf-8') as f:
        scenescript = json.load(f)
    
    scenes = scenescript.get('scenes', [])
    if not scenes:
        log.warning("No scenes found in SceneScript")
        return {}
    
    # Calculate cumulative timing for scenes
    scene_timings = []
    current_time = 0
    for scene in scenes:
        duration = scene.get('duration_ms', 0)
        scene_timings.append({
            'id': scene['id'],
            'start_ms': current_time,
            'end_ms': current_time + duration,
            'duration_ms': duration
        })
        current_time += duration
    
    # Map cues to scenes
    scene_cues = {}
    for scene in scene_timings:
        scene_id = scene['id']
        scene_start = scene['start_ms']
        scene_end = scene['end_ms']
        
        # Find cues that overlap with this scene
        scene_cue_list = []
        for cue_start, cue_end, cue_text in cues:
            # Check for overlap (allowing ±300ms tolerance)
            tolerance = 300
            if (cue_start - tolerance <= scene_end and 
                cue_end + tolerance >= scene_start):
                
                # Calculate relative timing within scene
                relative_start = max(0, cue_start - scene_start)
                relative_end = min(scene['duration_ms'], cue_end - scene_start)
                
                # Only include cues that have meaningful overlap
                if relative_end > relative_start:
                    scene_cue_list.append({
                        'start_ms': relative_start,
                        'end_ms': relative_end,
                        'text': cue_text,
                        'absolute_start': cue_start,
                        'absolute_end': cue_end
                    })
        
        if scene_cue_list:
            scene_cues[scene_id] = {
                'scene_start_ms': scene_start,
                'scene_end_ms': scene_end,
                'cues': scene_cue_list
            }
    
    log.info(f"Mapped cues to {len(scene_cues)} scenes")
    return scene_cues


def generate_vo_cues_json(slug: str, output_dir: str) -> str:
    """
    Generate voiceover cues JSON file for the given slug.
    
    Args:
        slug: Content slug identifier
        output_dir: Output directory for vo_cues.json
        
    Returns:
        Path to generated vo_cues.json file
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Paths
    srt_path = os.path.join(BASE, "voiceovers", f"{slug}.srt")
    scenescript_path = os.path.join(BASE, "scenescripts", f"{slug}.json")
    output_path = os.path.join(output_dir, "vo_cues.json")
    
    # Check if output already exists (idempotence)
    if os.path.exists(output_path):
        log.info(f"Voiceover cues already exist: {output_path}")
        return output_path
    
    # Parse SRT file
    cues = parse_srt_file(srt_path)
    if not cues:
        log.warning(f"No cues found in SRT file: {srt_path}")
        # Create empty structure
        vo_cues = {
            "slug": slug,
            "generated_at": None,
            "total_duration_ms": 0,
            "scene_cues": {},
            "warnings": ["No SRT file found or no cues parsed"]
        }
    else:
        # Map cues to scenes
        scene_cues = map_cues_to_scenes(cues, scenescript_path)
        
        # Calculate total duration
        total_duration = max(cue[1] for cue in cues) if cues else 0
        
        vo_cues = {
            "slug": slug,
            "generated_at": time.time(),
            "total_duration_ms": total_duration,
            "scene_cues": scene_cues,
            "warnings": []
        }
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(vo_cues, f, indent=2, ensure_ascii=False)
    
    log.info(f"Generated voiceover cues: {output_path}")
    return output_path


def main():
    """Main function for voice cues generation."""
    parser = argparse.ArgumentParser(description="Generate voiceover cues from SRT files")
    parser.add_argument("--slug", required=True, help="Content slug identifier")
    parser.add_argument("--output-dir", help="Output directory (default: data/<slug>)")
    
    args = parser.parse_args()
    
    # Set output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.join(BASE, "data", args.slug)
    
    try:
        # Load configuration and guard system
        cfg = load_config()
        guard_system(cfg)
        
        # Log start
        log_state("voice_cues", "START", f"slug={args.slug}")
        
        # Generate voiceover cues
        output_path = generate_vo_cues_json(args.slug, output_dir)
        
        # Log success
        log_state("voice_cues", "OK", f"Generated {output_path}")
        print(f"✓ Voiceover cues generated: {output_path}")
        
    except Exception as e:
        log.error(f"Failed to generate voiceover cues: {e}")
        log_state("voice_cues", "ERROR", str(e))
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    with single_lock():
        main()
