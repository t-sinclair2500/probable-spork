#!/usr/bin/env python3
"""
SRT Generation with Fallback Timing

Generates SRT caption files with multiple timing sources:
1. ASR word timings (preferred)
2. TTS word timings 
3. Heuristic timing based on intent profiles
4. Fallback pacing-based timing

Used by acceptance pipeline to ensure captions are always present.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import yaml

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger, load_config

log = get_logger("srt_generate")


class SRTGenerator:
    """Generates SRT captions with fallback timing strategies"""
    
    def __init__(self, config=None):
        self.config = config or load_config()
        self.intent_profiles = self._load_intent_profiles()
        
    def _load_intent_profiles(self) -> Dict[str, Any]:
        """Load intent profiles for heuristic timing"""
        try:
            intent_profiles_path = os.path.join(ROOT, "conf", "intent_profiles.yaml")
            if os.path.exists(intent_profiles_path):
                with open(intent_profiles_path, 'r', encoding='utf-8') as f:
                    profiles = yaml.safe_load(f)
                log.info(f"[srt-gen] Loaded {len(profiles)} intent profiles for timing")
                return profiles
            else:
                log.warning("[srt-gen] Intent profiles not found, using defaults")
                return self._get_default_intent_profiles()
        except Exception as e:
            log.warning(f"[srt-gen] Failed to load intent profiles: {e}, using defaults")
            return self._get_default_intent_profiles()
    
    def _get_default_intent_profiles(self) -> Dict[str, Any]:
        """Fallback intent profiles if config file is missing"""
        return {
            "default": {
                "words_per_sec": [2.5, 3.5],
                "speech_ratio_default": 0.8
            },
            "narrative_history": {
                "words_per_sec": [2.0, 3.0],
                "speech_ratio_default": 0.85
            },
            "explainer_howto": {
                "words_per_sec": [2.5, 3.5],
                "speech_ratio_default": 0.8
            }
        }
    
    def generate_srt_for_acceptance(self, script_path: str, output_path: str = None, 
                                   intent_type: str = "default", 
                                   target_duration_sec: float = None) -> Dict[str, Any]:
        """
        Generate SRT captions for acceptance pipeline with fallback timing.
        
        Args:
            script_path: Path to script file
            output_path: Output SRT path (optional, auto-generated if None)
            intent_type: Intent type for timing profile
            target_duration_sec: Target duration in seconds (optional)
            
        Returns:
            Dict with generation results and metadata
        """
        log.info(f"[srt-gen] Starting SRT generation for {script_path}")
        
        try:
            # Validate script file
            if not os.path.exists(script_path):
                return {
                    "success": False,
                    "error": f"Script file not found: {script_path}",
                    "error_type": "file_not_found"
                }
            
            # Read script content
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # Try to find existing SRT file first
            existing_srt = self._find_existing_srt(script_path)
            if existing_srt:
                log.info(f"[srt-gen] Found existing SRT: {existing_srt}")
                return {
                    "success": True,
                    "srt_path": existing_srt,
                    "source": "existing",
                    "word_count": len(script_content.split()),
                    "duration_sec": self._estimate_duration_from_srt(existing_srt)
                }
            
            # Try to find ASR/TTS timings
            asr_timings = self._find_asr_timings(script_path)
            tts_timings = self._find_tts_timings(script_path)
            
            if asr_timings:
                log.info(f"[srt-gen] Using ASR timings for SRT generation")
                srt_content = self._generate_srt_from_timings(script_content, asr_timings, "asr")
                source = "asr"
            elif tts_timings:
                log.info(f"[srt-gen] Using TTS timings for SRT generation")
                srt_content = self._generate_srt_from_timings(script_content, tts_timings, "tts")
                source = "tts"
            else:
                log.info(f"[srt-gen] No timings found, using heuristic generation")
                srt_content = self._generate_srt_heuristic(script_content, intent_type, target_duration_sec)
                source = "heuristic"
            
            # Determine output path
            if not output_path:
                output_path = script_path.replace('.txt', '.srt')
            
            # Write SRT file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            # Validate generated SRT
            validation = self._validate_generated_srt(output_path, script_content)
            
            log.info(f"[srt-gen] SRT generation completed successfully: {output_path}")
            return {
                "success": True,
                "srt_path": output_path,
                "source": source,
                "word_count": len(script_content.split()),
                "duration_sec": validation.get("duration_sec", 0),
                "validation": validation,
                "generation_method": source
            }
            
        except Exception as e:
            log.error(f"[srt-gen] SRT generation failed: {str(e)}")
            return {
                "success": False,
                "error": f"SRT generation error: {str(e)}",
                "error_type": "generation_error",
                "script_path": script_path
            }
    
    def _find_existing_srt(self, script_path: str) -> Optional[str]:
        """Find existing SRT file for the script"""
        # Check voiceovers directory first
        script_basename = os.path.basename(script_path).replace('.txt', '')
        voiceovers_dir = os.path.join(ROOT, "voiceovers")
        
        srt_path = os.path.join(voiceovers_dir, f"{script_basename}.srt")
        if os.path.exists(srt_path):
            return srt_path
        
        # Check scripts directory
        scripts_dir = os.path.dirname(script_path)
        srt_path = os.path.join(scripts_dir, f"{script_basename}.srt")
        if os.path.exists(srt_path):
            return srt_path
        
        return None
    
    def _find_asr_timings(self, script_path: str) -> Optional[Dict[str, Any]]:
        """Find ASR word timings if available"""
        try:
            # Look for ASR results in data directory
            script_basename = os.path.basename(script_path).replace('.txt', '')
            data_dir = os.path.join(ROOT, "data", script_basename)
            
            asr_file = os.path.join(data_dir, "asr_results.json")
            if os.path.exists(asr_file):
                with open(asr_file, 'r', encoding='utf-8') as f:
                    asr_data = json.load(f)
                
                if "words" in asr_data and asr_data["words"]:
                    log.info(f"[srt-gen] Found ASR timings with {len(asr_data['words'])} words")
                    return asr_data
        except Exception as e:
            log.debug(f"[srt-gen] ASR timing lookup failed: {e}")
        
        return None
    
    def _find_tts_timings(self, script_path: str) -> Optional[Dict[str, Any]]:
        """Find TTS word timings if available"""
        try:
            # Look for TTS results in voiceovers directory
            script_basename = os.path.basename(script_path).replace('.txt', '')
            voiceovers_dir = os.path.join(ROOT, "voiceovers")
            
            tts_file = os.path.join(voiceovers_dir, f"{script_basename}.tts.json")
            if os.path.exists(tts_file):
                with open(tts_file, 'r', encoding='utf-8') as f:
                    tts_data = json.load(f)
                
                if "words" in tts_data and tts_data["words"]:
                    log.info(f"[srt-gen] Found TTS timings with {len(tts_data['words'])} words")
                    return tts_data
        except Exception as e:
            log.debug(f"[srt-gen] TTS timing lookup failed: {e}")
        
        return None
    
    def _generate_srt_from_timings(self, script_content: str, timings: Dict[str, Any], 
                                  source: str) -> str:
        """Generate SRT from ASR or TTS word timings"""
        words = script_content.split()
        srt_lines = []
        caption_index = 1
        
        if source == "asr":
            # ASR provides word-level timings
            word_timings = timings.get("words", [])
            if len(word_timings) == len(words):
                # Group words into captions (max 8 words per caption)
                max_words_per_caption = 8
                current_caption = []
                start_time = None
                
                for i, (word, timing) in enumerate(zip(words, word_timings)):
                    if not current_caption:
                        start_time = timing.get("start", 0)
                    
                    current_caption.append(word)
                    
                    # End caption if max words reached or end of script
                    if (len(current_caption) >= max_words_per_caption or 
                        i == len(words) - 1):
                        end_time = timing.get("end", start_time + 2.0)
                        
                        caption_text = " ".join(current_caption)
                        srt_lines.extend([
                            str(caption_index),
                            self._format_timestamp(start_time),
                            self._format_timestamp(end_time),
                            caption_text,
                            ""
                        ])
                        
                        caption_index += 1
                        current_caption = []
                        start_time = None
            else:
                log.warning(f"[srt-gen] ASR word count mismatch: {len(word_timings)} vs {len(words)}")
                return self._generate_srt_heuristic(script_content, "default", None)
        
        elif source == "tts":
            # TTS provides word-level timings
            word_timings = timings.get("words", [])
            if len(word_timings) == len(words):
                # Similar grouping logic for TTS
                max_words_per_caption = 8
                current_caption = []
                start_time = None
                
                for i, (word, timing) in enumerate(zip(words, word_timings)):
                    if not current_caption:
                        start_time = timing.get("start", 0)
                    
                    current_caption.append(word)
                    
                    if (len(current_caption) >= max_words_per_caption or 
                        i == len(words) - 1):
                        end_time = timing.get("end", start_time + 2.0)
                        
                        caption_text = " ".join(current_caption)
                        srt_lines.extend([
                            str(caption_index),
                            self._format_timestamp(start_time),
                            self._format_timestamp(end_time),
                            caption_text,
                            ""
                        ])
                        
                        caption_index += 1
                        current_caption = []
                        start_time = None
            else:
                log.warning(f"[srt-gen] TTS word count mismatch: {len(word_timings)} vs {len(words)}")
                return self._generate_srt_heuristic(script_content, "default", None)
        
        return "\n".join(srt_lines)
    
    def _generate_srt_heuristic(self, script_content: str, intent_type: str, 
                               target_duration_sec: float) -> str:
        """Generate SRT using heuristic timing based on intent profiles"""
        log.info(f"[srt-gen] Generating heuristic SRT for intent: {intent_type}")
        
        # Get timing profile
        profile = self.intent_profiles.get(intent_type, self.intent_profiles.get("default", {}))
        words_per_sec_range = profile.get("words_per_sec", [2.5, 3.5])
        words_per_sec = sum(words_per_sec_range) / 2  # Use average
        
        # Split script into sentences for caption grouping
        sentences = self._split_into_sentences(script_content)
        words = script_content.split()
        
        # Calculate timing
        if target_duration_sec:
            # Use target duration to adjust words per second
            total_words = len(words)
            words_per_sec = total_words / target_duration_sec
            log.info(f"[srt-gen] Adjusted words per second to {words_per_sec:.2f} for target duration")
        
        # Generate captions
        srt_lines = []
        caption_index = 1
        current_time = 0.0
        
        for sentence in sentences:
            sentence_words = sentence.split()
            if not sentence_words:
                continue
            
            # Calculate duration for this sentence
            sentence_duration = len(sentence_words) / words_per_sec
            
            # Ensure minimum caption duration
            min_caption_duration = 1.0  # 1 second minimum
            if sentence_duration < min_caption_duration:
                sentence_duration = min_caption_duration
            
            # Format timestamps
            start_time = current_time
            end_time = current_time + sentence_duration
            
            srt_lines.extend([
                str(caption_index),
                self._format_timestamp(start_time),
                self._format_timestamp(end_time),
                sentence.strip(),
                ""
            ])
            
            caption_index += 1
            current_time = end_time
        
        return "\n".join(srt_lines)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for caption grouping"""
        # Simple sentence splitting - can be enhanced with NLP
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds into SRT timestamp format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def _validate_generated_srt(self, srt_path: str, script_content: str) -> Dict[str, Any]:
        """Validate generated SRT file"""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            # Parse SRT to validate structure
            captions = self._parse_srt(srt_content)
            
            # Calculate metrics
            total_captions = len(captions)
            total_duration = 0.0
            word_count = len(script_content.split())
            
            for caption in captions:
                duration = caption["end_time"] - caption["start_time"]
                total_duration += duration
            
            # Check for common issues
            issues = []
            if total_captions == 0:
                issues.append("No captions generated")
            if total_duration == 0:
                issues.append("Zero total duration")
            if any(c["end_time"] <= c["start_time"] for c in captions):
                issues.append("Invalid timestamp ordering")
            
            return {
                "valid": len(issues) == 0,
                "total_captions": total_captions,
                "duration_sec": total_duration,
                "word_count": word_count,
                "issues": issues,
                "avg_caption_duration": total_duration / total_captions if total_captions > 0 else 0
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}",
                "issues": [f"Validation failed: {str(e)}"]
            }
    
    def _parse_srt(self, srt_content: str) -> List[Dict[str, Any]]:
        """Parse SRT content into structured format"""
        captions = []
        lines = srt_content.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Parse caption block
            try:
                # Caption number
                caption_num = int(line)
                i += 1
                
                if i >= len(lines):
                    break
                
                # Timestamp line
                timestamp_line = lines[i].strip()
                start_time, end_time = self._parse_timestamp_line(timestamp_line)
                i += 1
                
                # Caption text
                caption_text = []
                while i < len(lines) and lines[i].strip():
                    caption_text.append(lines[i].strip())
                    i += 1
                
                captions.append({
                    "number": caption_num,
                    "start_time": start_time,
                    "end_time": end_time,
                    "text": " ".join(caption_text)
                })
                
            except (ValueError, IndexError) as e:
                log.warning(f"[srt-gen] Failed to parse caption at line {i}: {e}")
                i += 1
        
        return captions
    
    def _parse_timestamp_line(self, timestamp_line: str) -> Tuple[float, float]:
        """Parse SRT timestamp line into start and end times in seconds"""
        try:
            # Format: HH:MM:SS,mmm --> HH:MM:SS,mmm
            parts = timestamp_line.split(' --> ')
            if len(parts) != 2:
                raise ValueError("Invalid timestamp format")
            
            start_time = self._timestamp_to_seconds(parts[0].strip())
            end_time = self._timestamp_to_seconds(parts[1].strip())
            
            return start_time, end_time
            
        except Exception as e:
            log.warning(f"[srt-gen] Failed to parse timestamp: {timestamp_line}, error: {e}")
            return 0.0, 2.0  # Fallback
    
    def _timestamp_to_seconds(self, timestamp: str) -> float:
        """Convert SRT timestamp to seconds"""
        try:
            # Format: HH:MM:SS,mmm
            time_part, millisec_part = timestamp.split(',')
            hours, minutes, seconds = map(int, time_part.split(':'))
            millisecs = int(millisec_part)
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + millisecs / 1000.0
            return total_seconds
            
        except Exception as e:
            log.warning(f"[srt-gen] Failed to convert timestamp {timestamp}: {e}")
            return 0.0
    
    def _estimate_duration_from_srt(self, srt_path: str) -> float:
        """Estimate duration from existing SRT file"""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            captions = self._parse_srt(srt_content)
            if captions:
                return captions[-1]["end_time"]
            return 0.0
            
        except Exception as e:
            log.warning(f"[srt-gen] Failed to estimate duration from SRT: {e}")
            return 0.0


def generate_srt_for_acceptance(script_path: str, output_path: str = None, 
                               intent_type: str = "default", 
                               target_duration_sec: float = None) -> Dict[str, Any]:
    """Convenience function for acceptance pipeline"""
    generator = SRTGenerator()
    return generator.generate_srt_for_acceptance(script_path, output_path, intent_type, target_duration_sec)


if __name__ == "__main__":
    # Command line interface for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate SRT captions with fallback timing")
    parser.add_argument("script_path", help="Path to script file")
    parser.add_argument("--output", help="Output SRT path (optional)")
    parser.add_argument("--intent", default="default", help="Intent type for timing")
    parser.add_argument("--duration", type=float, help="Target duration in seconds")
    
    args = parser.parse_args()
    
    result = generate_srt_for_acceptance(
        args.script_path, 
        args.output, 
        args.intent, 
        args.duration
    )
    
    if result["success"]:
        print(f"SRT generated successfully: {result['srt_path']}")
        print(f"Source: {result['source']}")
        print(f"Duration: {result['duration_sec']:.2f}s")
    else:
        print(f"SRT generation failed: {result['error']}")
        sys.exit(1)
