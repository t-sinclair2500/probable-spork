#!/usr/bin/env python3
"""
Pacing KPI Module

Computes pacing metrics for video content:
- Words per second
- Cuts per minute  
- Average scene length
- Speech/music ratio

Deterministic metrics using script text, SRT timings, and scene durations.
"""

import argparse
import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

try:
    from .core import get_logger, load_config, load_modules_cfg, load_brief
except ImportError:
    # Handle direct execution
    import sys
    sys.path.append(os.path.dirname(__file__))
    from core import get_logger, load_config, load_modules_cfg, load_brief

log = get_logger("pacing-kpi")


def parse_srt_timing(srt_path: str) -> Tuple[float, int]:
    """
    Parse SRT file to extract total speech duration and word count.
    
    Args:
        srt_path: Path to SRT caption file
        
    Returns:
        Tuple of (total_speech_ms, total_words)
    """
    if not os.path.exists(srt_path):
        log.warning(f"SRT file not found: {srt_path}")
        return 0.0, 0
    
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse SRT timing blocks
        timing_pattern = r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})'
        matches = re.findall(timing_pattern, content)
        
        total_speech_ms = 0
        total_words = 0
        
        for start_str, end_str in matches:
            # Convert HH:MM:SS,mmm to milliseconds
            start_parts = start_str.replace(',', '.').split(':')
            end_parts = end_str.replace(',', '.').split(':')
            
            start_ms = (int(start_parts[0]) * 3600 + 
                       int(start_parts[1]) * 60 + 
                       float(start_parts[2])) * 1000
            end_ms = (int(end_parts[0]) * 3600 + 
                     int(end_parts[1]) * 60 + 
                     float(end_parts[2])) * 1000
            
            duration_ms = end_ms - start_ms
            total_speech_ms += duration_ms
        
        # For SRT files, we don't count words from captions as they may contain full script
        # Instead, we'll use the script text for word count and SRT only for timing
        log.info(f"Parsed SRT: {total_speech_ms:.0f}ms speech duration")
        return total_speech_ms, 0
        
    except Exception as e:
        log.error(f"Error parsing SRT file {srt_path}: {e}")
        return 0.0, 0


def count_words(text: str) -> int:
    """Count words in text, handling common punctuation."""
    # Remove common punctuation and count word boundaries
    cleaned = re.sub(r'[^\w\s]', ' ', text)
    words = re.findall(r'\b\w+\b', cleaned)
    return len(words)


def compute_pacing(script_text: str, scenes: List[Dict], video_ms: int, 
                   srt_path: Optional[str] = None) -> Dict:
    """
    Compute pacing KPIs for video content.
    
    Args:
        script_text: Final script text content
        scenes: List of scene dictionaries with duration_ms
        video_ms: Total video duration in milliseconds
        srt_path: Optional path to SRT caption file
        
    Returns:
        Dictionary with pacing metrics and metadata
    """
    log.info(f"Computing pacing KPIs for {len(scenes)} scenes, {video_ms}ms video")
    
    # Load configuration
    config = load_config()
    modules_cfg = load_modules_cfg()
    render_cfg = modules_cfg.get('render', {})
    
    # Extract scene durations and count transitions
    scene_durations = []
    scene_transitions = len(scenes)  # Each scene is a transition
    
    for scene in scenes:
        duration_ms = scene.get('duration_ms', 0)
        if duration_ms > 0:
            scene_durations.append(duration_ms)
            log.debug(f"Scene {scene.get('id', 'unknown')}: {duration_ms}ms")
    
    # Count words in script
    script_words = count_words(script_text)
    log.info(f"Script contains {script_words} words")
    
    # Determine speech timing source
    if srt_path and os.path.exists(srt_path):
        speech_ms, srt_words = parse_srt_timing(srt_path)
        source = "vo"
        if speech_ms > 0:
            total_speech_ms = speech_ms
            log.info(f"Using SRT timing: {speech_ms:.0f}ms speech")
        else:
            # Fallback to script word count estimation
            speech_ratio = render_cfg.get('speech_ratio_default', 0.8)
            total_speech_ms = video_ms * speech_ratio
            log.warning(f"SRT parsing failed, using estimated speech ratio: {speech_ratio}")
    else:
        # No SRT available, use brief target and configurable ratio
        brief_cfg = load_brief()
        target_intent = brief_cfg.get('intent', 'default')
        
        # Load intent profiles for speech ratio
        intent_profiles_path = os.path.join(os.path.dirname(__file__), '..', 'conf', 'intent_profiles.yaml')
        if os.path.exists(intent_profiles_path):
            with open(intent_profiles_path, 'r') as f:
                import yaml
                intent_profiles = yaml.safe_load(f)
                speech_ratio = intent_profiles.get(target_intent, {}).get('speech_ratio_default', 0.8)
        else:
            speech_ratio = 0.8
        
        total_speech_ms = video_ms * speech_ratio
        source = "brief"
        log.info(f"No SRT available, using brief target with {speech_ratio} speech ratio")
    
    # Calculate KPIs
    video_seconds = video_ms / 1000.0
    speech_seconds = total_speech_ms / 1000.0
    
    # Words per second
    words_per_sec = script_words / speech_seconds if speech_seconds > 0 else 0.0
    
    # Cuts per minute
    video_minutes = video_seconds / 60.0
    cuts_per_min = scene_transitions / video_minutes if video_minutes > 0 else 0.0
    
    # Average scene length
    if scene_durations:
        avg_scene_ms = sum(scene_durations) / len(scene_durations)
        avg_scene_s = avg_scene_ms / 1000.0
    else:
        avg_scene_s = 0.0
    
    # Speech/music ratio
    music_ms = video_ms - total_speech_ms
    if music_ms > 0:
        speech_music_ratio = total_speech_ms / music_ms
    else:
        # Clamp to reasonable value if no music
        speech_music_ratio = 10.0  # High ratio when no music
    
    # Prepare scene details for report
    scene_details = []
    for scene in scenes:
        scene_details.append({
            "id": scene.get('id', 'unknown'),
            "duration_ms": scene.get('duration_ms', 0)
        })
    
    # Compile results
    kpi_result = {
        "words_per_sec": round(words_per_sec, 2),
        "cuts_per_min": round(cuts_per_min, 1),
        "avg_scene_s": round(avg_scene_s, 2),
        "speech_music_ratio": round(speech_music_ratio, 2),
        "scenes": scene_details,
        "source": source,
        "metadata": {
            "script_words": script_words,
            "video_duration_ms": video_ms,
            "speech_duration_ms": total_speech_ms,
            "scene_count": len(scenes),
            "computed_at": None  # Will be set by caller
        }
    }
    
    log.info(f"Pacing KPIs computed: {words_per_sec:.2f} wps, {cuts_per_min:.1f} cpm, "
             f"{avg_scene_s:.2f}s avg scene, {speech_music_ratio:.2f} speech/music")
    
    return kpi_result


def save_pacing_report(slug: str, kpi_data: Dict, report_dir: str = None) -> str:
    """
    Save pacing report to runs directory.
    
    Args:
        slug: Content slug identifier
        kpi_data: KPI computation results
        report_dir: Optional custom report directory
        
    Returns:
        Path to saved report file
    """
    if report_dir is None:
        report_dir = os.path.join(os.path.dirname(__file__), '..', 'runs', slug)
    
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, 'pacing_report.json')
    
    # Add timestamp
    import datetime
    kpi_data['metadata']['computed_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
    
    with open(report_path, 'w') as f:
        json.dump(kpi_data, f, indent=2)
    
    log.info(f"Pacing report saved to {report_path}")
    return report_path


def update_video_metadata(slug: str, kpi_data: Dict, metadata_dir: str = None) -> str:
    """
    Update video metadata with pacing KPIs.
    
    Args:
        slug: Content slug identifier
        kpi_data: KPI computation results
        metadata_dir: Optional custom metadata directory
        
    Returns:
        Path to updated metadata file
    """
    if metadata_dir is None:
        metadata_dir = os.path.join(os.path.dirname(__file__), '..', 'videos')
    
    metadata_path = os.path.join(metadata_dir, f'{slug}.metadata.json')
    
    # Load existing metadata
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {}
    
    # Add pacing section
    metadata['pacing'] = {
        "words_per_sec": kpi_data['words_per_sec'],
        "cuts_per_min": kpi_data['cuts_per_min'],
        "avg_scene_s": kpi_data['avg_scene_s'],
        "speech_music_ratio": kpi_data['speech_music_ratio'],
        "source": kpi_data['source'],
        "computed_at": kpi_data['metadata']['computed_at']
    }
    
    # Save updated metadata
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    log.info(f"Video metadata updated with pacing KPIs: {metadata_path}")
    return metadata_path


def run_complete_pacing_analysis(slug: str, script_text: str, scenes: List[Dict], 
                                video_ms: int, srt_path: Optional[str] = None) -> Dict:
    """
    Run complete pacing analysis including KPI computation and comparison.
    
    Args:
        slug: Content slug identifier
        script_text: Final script text content
        scenes: List of scene dictionaries with duration_ms
        video_ms: Total video duration in milliseconds
        srt_path: Optional path to SRT caption file
        
    Returns:
        Complete analysis results with KPIs and comparison
    """
    log.info(f"Running complete pacing analysis for {slug}")
    
    # Compute KPIs first
    kpi_data = compute_pacing(script_text, scenes, video_ms, srt_path)
    
    # Save KPI report
    save_pacing_report(slug, kpi_data)
    
    # Run comparison analysis
    try:
        # Try absolute import first
        from bin.pacing_compare import run_pacing_analysis
        comparison_result = run_pacing_analysis(slug, kpi_data)
        log.info(f"Comparison analysis completed for {slug}")
        return comparison_result
    except ImportError:
        try:
            # Try relative import
            from .pacing_compare import run_pacing_analysis
            comparison_result = run_pacing_analysis(slug, kpi_data)
            log.info(f"Comparison analysis completed for {slug}")
            return comparison_result
        except ImportError:
            log.warning("Pacing comparison module not available, skipping comparison")
            # Update metadata with just KPIs
            update_video_metadata(slug, kpi_data)
            return {
                "slug": slug,
                "kpi_data": kpi_data,
                "comparison": None,
                "status": "kpi_only"
            }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute pacing KPIs for video content")
    parser.add_argument("--slug", required=True, help="Content slug identifier")
    parser.add_argument("--script-file", help="Path to script file (auto-detected if not provided)")
    parser.add_argument("--srt-file", help="Path to SRT caption file (auto-detected if not provided)")
    
    args = parser.parse_args()
    slug = args.slug
    
    # Auto-detect script file if not provided
    if not args.script_file:
        script_file = os.path.join(os.path.dirname(__file__), '..', 'scripts', f'{slug}.txt')
        if not os.path.exists(script_file):
            print(f"Error: Script file not found at {script_file}")
            print("Please provide --script-file or ensure script exists at scripts/{slug}.txt")
            sys.exit(1)
    else:
        script_file = args.script_file
    
    # Auto-detect SRT file if not provided
    if not args.srt_file:
        srt_file = os.path.join(os.path.dirname(__file__), '..', 'voiceovers', f'{slug}.srt')
        if not os.path.exists(srt_file):
            srt_file = None
            log.info(f"SRT file not found, will use brief-based timing")
    else:
        srt_file = args.srt_file
    
    # Load script
    try:
        with open(script_file, 'r') as f:
            script_text = f.read()
    except Exception as e:
        print(f"Error loading script file {script_file}: {e}")
        sys.exit(1)
    
    # Load actual scenescript data
    scenescript_path = os.path.join(os.path.dirname(__file__), '..', 'scenescripts', f'{slug}.json')
    if os.path.exists(scenescript_path):
        with open(scenescript_path, 'r') as f:
            scenescript = json.load(f)
        scenes = scenescript.get('scenes', [])
        video_ms = sum(scene.get('duration_ms', 0) for scene in scenes)
        log.info(f"Loaded scenescript: {len(scenes)} scenes, {video_ms}ms total")
    else:
        print(f"Error: Scenescript not found at {scenescript_path}")
        print("Please ensure scenescript exists at scenescripts/{slug}.json")
        sys.exit(1)
    
    # Compute KPIs
    kpi_result = compute_pacing(script_text, scenes, video_ms, srt_file)
    
    # Save report and update metadata
    save_pacing_report(slug, kpi_result)
    update_video_metadata(slug, kpi_result)
    
    # Print concise summary as required by P5-5
    flags = []
    if kpi_result.get('source') == 'vo':
        flags.append('vo-timed')
    if kpi_result.get('source') == 'brief':
        flags.append('brief-timed')
    
    print(f"{kpi_result['words_per_sec']:.1f}wps {kpi_result['cuts_per_min']:.1f}cuts/min {kpi_result['avg_scene_s']:.1f}s avg {' '.join(flags)} adjusted=false")
    
    print(f"\nPacing KPIs computed and saved successfully for {slug}!")
    print(f"Words/sec: {kpi_result['words_per_sec']:.2f}")
    print(f"Cuts/min: {kpi_result['cuts_per_min']:.2f}")
    print(f"Avg scene: {kpi_result['avg_scene_s']:.2f}s")
    print(f"Speech/music ratio: {kpi_result['speech_music_ratio']:.2f}")
    print(f"Source: {kpi_result.get('source', 'unknown')}")
