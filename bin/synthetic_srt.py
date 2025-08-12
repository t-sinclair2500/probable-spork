#!/usr/bin/env python3
"""
Synthetic SRT Generation for Content Pipeline

Generates deterministic SRT caption files from script text when ASR is not available.
Uses configurable word rate and seedable segmentation for consistent timing.
"""

import os
import re
import random
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Ensure repo root on path
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import (
    BASE,
    get_logger,
    load_config,
    log_state,
)


log = get_logger("synthetic_srt")


def clean_script_text(script_text: str) -> str:
    """
    Clean script text by removing B-ROLL markers and stage directions.
    
    Args:
        script_text: Raw script text
        
    Returns:
        Cleaned text suitable for caption generation
    """
    # Remove B-ROLL markers and their content
    cleaned = re.sub(r'\[B-ROLL:\s*[^\]]*\]', '', script_text)
    
    # Remove other stage directions in brackets
    cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
    
    # Remove extra whitespace and normalize
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Remove markdown formatting
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
    
    return cleaned


def segment_text_for_captions(text: str, max_words_per_caption: int = 8) -> List[str]:
    """
    Segment text into caption-sized chunks.
    
    Args:
        text: Clean text to segment
        max_words_per_caption: Maximum words per caption
        
    Returns:
        List of caption text segments
    """
    # Split by sentences first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    captions = []
    current_caption = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # If adding this sentence would exceed max words, start new caption
        if current_caption and len(current_caption.split()) + len(sentence.split()) > max_words_per_caption:
            if current_caption:
                captions.append(current_caption.strip())
            current_caption = sentence
        else:
            if current_caption:
                current_caption += " " + sentence
            else:
                current_caption = sentence
    
    # Add final caption if any
    if current_caption:
        captions.append(current_caption.strip())
    
    return captions


def calculate_caption_timing(
    captions: List[str], 
    total_duration_sec: float,
    wpm: int = 160,
    seed: Optional[int] = None
) -> List[Tuple[float, float, str]]:
    """
    Calculate timing for each caption based on word count and total duration.
    
    Args:
        captions: List of caption text segments
        total_duration_sec: Total audio duration in seconds
        wpm: Words per minute reading rate
        seed: Random seed for deterministic timing variations
        
    Returns:
        List of (start_sec, end_sec, text) tuples
    """
    if seed is not None:
        random.seed(seed)
    
    # Calculate total words and base timing
    total_words = sum(len(caption.split()) for caption in captions)
    base_wps = wpm / 60.0  # words per second
    
    # Calculate total time needed for all captions
    total_time_needed = total_words / base_wps
    
    # Scale timing to fit total duration
    if total_time_needed > 0:
        scale_factor = total_duration_sec / total_time_needed
    else:
        scale_factor = 1.0
    
    # Generate timing for each caption
    caption_timings = []
    current_time = 0.0
    
    for caption in captions:
        word_count = len(caption.split())
        duration = (word_count / base_wps) * scale_factor
        
        # Add small random variation (±5%) for natural feel
        if seed is not None:
            variation = random.uniform(0.95, 1.05)
            duration *= variation
        
        # Ensure minimum duration
        duration = max(duration, 1.0)
        
        start_time = current_time
        end_time = current_time + duration
        
        caption_timings.append((start_time, end_time, caption))
        current_time = end_time
    
    return caption_timings


def format_srt_timestamp(seconds: float) -> str:
    """
    Format seconds to SRT timestamp format (HH:MM:SS,mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        SRT timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    milliseconds = int((secs % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{int(secs):02d},{milliseconds:03d}"


def generate_srt_content(caption_timings: List[Tuple[float, float, str]]) -> str:
    """
    Generate SRT file content from caption timings.
    
    Args:
        caption_timings: List of (start_sec, end_sec, text) tuples
        
    Returns:
        SRT file content as string
    """
    srt_lines = []
    
    for i, (start_sec, end_sec, text) in enumerate(caption_timings, 1):
        start_timestamp = format_srt_timestamp(start_sec)
        end_timestamp = format_srt_timestamp(end_sec)
        
        srt_lines.append(str(i))
        srt_lines.append(f"{start_timestamp} --> {end_timestamp}")
        srt_lines.append(text)
        srt_lines.append("")  # Empty line between captions
    
    return "\n".join(srt_lines)


def generate_synthetic_srt(
    script_path: str,
    audio_duration_sec: float,
    output_path: str,
    wpm: int = 160,
    max_words_per_caption: int = 8,
    seed: Optional[int] = None
) -> str:
    """
    Generate synthetic SRT file from script text.
    
    Args:
        script_path: Path to script text file
        audio_duration_sec: Duration of audio in seconds
        output_path: Path to output SRT file
        wpm: Words per minute reading rate
        max_words_per_caption: Maximum words per caption
        seed: Random seed for deterministic timing
        
    Returns:
        Path to generated SRT file
    """
    # Read script text
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            script_text = f.read()
    except Exception as e:
        log.error(f"Failed to read script file {script_path}: {e}")
        raise
    
    # Clean script text
    cleaned_text = clean_script_text(script_text)
    
    # Segment into captions
    captions = segment_text_for_captions(cleaned_text, max_words_per_caption)
    
    # Calculate timing
    caption_timings = calculate_caption_timing(
        captions, audio_duration_sec, wpm, seed
    )
    
    # Generate SRT content
    srt_content = generate_srt_content(caption_timings)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write SRT file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        log.info(f"Generated synthetic SRT: {output_path}")
        log.info(f"Captions: {len(captions)}, Duration: {audio_duration_sec:.1f}s, WPM: {wpm}")
    except Exception as e:
        log.error(f"Failed to write SRT file {output_path}: {e}")
        raise
    
    return output_path


def main():
    """Main function for synthetic SRT generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate synthetic SRT captions")
    parser.add_argument("script_path", help="Path to script text file")
    parser.add_argument("audio_duration", type=float, help="Audio duration in seconds")
    parser.add_argument("output_path", help="Path to output SRT file")
    parser.add_argument("--wpm", type=int, default=160, help="Words per minute (default: 160)")
    parser.add_argument("--max-words", type=int, default=8, help="Max words per caption (default: 8)")
    parser.add_argument("--seed", type=int, help="Random seed for deterministic timing")
    
    args = parser.parse_args()
    
    try:
        generate_synthetic_srt(
            args.script_path,
            args.audio_duration,
            args.output_path,
            args.wpm,
            args.max_words,
            args.seed
        )
        print(f"Successfully generated SRT: {args.output_path}")
    except Exception as e:
        log.error(f"Failed to generate SRT: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
