#!/usr/bin/env python3
"""
Music Integration for Video Pipeline

Coordinates music selection, mixing, and integration with the video
assembly pipeline according to the music bed policy.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

# Ensure repo root on path
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger, load_config, log_state
from bin.music_library import MusicLibrary, MusicSelectionAgent
from bin.music_mixer import MusicMixer

log = get_logger("music_integration")


class MusicIntegrationManager:
    """Manages music integration throughout the video pipeline."""
    
    def __init__(self, config=None):
        self.config = config or load_config()
        self.library = MusicLibrary()
        self.agent = MusicSelectionAgent(self.library)
        self.mixer = MusicMixer(config)
        
        # Ensure music directory exists
        self.music_dir = Path("assets/music")
        self.music_dir.mkdir(parents=True, exist_ok=True)
    
    def prepare_music_for_video(self, script_path: str, voiceover_path: str,
                               output_dir: str, video_metadata: Dict[str, Any]) -> Optional[str]:
        """
        Prepare background music for a video based on content analysis.
        
        Args:
            script_path: Path to script file for content analysis
            voiceover_path: Path to voiceover audio file
            output_dir: Directory to store processed music
            video_metadata: Video metadata including tone, duration, etc.
        
        Returns:
            Optional[str]: Path to processed music file, or None if failed
        """
        try:
            log.info(f"Preparing music for video: {script_path}")
            
            # Read script content for analysis
            if not os.path.exists(script_path):
                log.error(f"Script file not found: {script_path}")
                return None
            
            with open(script_path, 'r') as f:
                script_text = f.read()
            
            # Extract video characteristics
            tone = video_metadata.get('tone', 'conversational')
            target_duration = video_metadata.get('duration', 30.0)
            pacing_wpm = video_metadata.get('pacing_wpm', 165)
            
            # Select appropriate music track
            selected_track = self.agent.select_music_for_video(
                script_text, tone, target_duration, pacing_wpm
            )
            
            if not selected_track:
                log.warning("No suitable music track found, proceeding without music")
                return None
            
            # Process music for video
            processed_music_path = self._process_music_for_video(
                selected_track, voiceover_path, output_dir, target_duration
            )
            
            if processed_music_path:
                log.info(f"Music prepared successfully: {processed_music_path}")
                log_state("music_integration", "OK", f"Music prepared: {selected_track.title}")
                return processed_music_path
            else:
                log.error("Failed to process music for video")
                log_state("music_integration", "ERROR", "Music processing failed")
                return None
                
        except Exception as e:
            log.error(f"Music preparation failed: {e}")
            log_state("music_integration", "ERROR", f"Music preparation failed: {e}")
            return None
    
    def _process_music_for_video(self, track: Any, voiceover_path: str,
                                output_dir: str, target_duration: float) -> Optional[str]:
        """Process selected music track for video integration."""
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Output path for processed music
            output_path = os.path.join(output_dir, f"bg_processed_{track.title.replace(' ', '_')}.mp3")
            
            # Check if we need to loop/extend music to match video duration
            if track.duration and track.duration < target_duration:
                # Create extended loop
                if not self.mixer.create_music_loop(track.file_path, output_path, target_duration):
                    log.warning("Failed to create music loop, using original")
                    output_path = track.file_path
            else:
                # Music is long enough, just copy/process
                import shutil
                shutil.copy2(track.file_path, output_path)
            
            log.info(f"Music processed: {output_path}")
            return output_path
            
        except Exception as e:
            log.error(f"Music processing failed: {e}")
            return None
    
    def integrate_music_with_video(self, voiceover_path: str, music_path: str,
                                  output_path: str, video_metadata: Dict[str, Any]) -> bool:
        """
        Integrate music with voiceover for final video audio.
        
        Args:
            voiceover_path: Path to voiceover audio
            music_path: Path to background music
            output_path: Path for final mixed audio
            video_metadata: Video metadata for mixing parameters
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            log.info(f"Integrating music with voiceover: {voiceover_path} + {music_path}")
            
            # Get mixing parameters from config
            music_db = float(getattr(self.config.render, 'music_db', -22.0))
            duck_db = float(getattr(self.config.render, 'duck_db', -15.0))
            
            # Determine fade parameters based on video characteristics
            fade_in_ms = 500  # Default 500ms fade-in
            fade_out_ms = 500  # Default 500ms fade-out
            
            # Adjust fades based on video duration
            duration = video_metadata.get('duration', 30.0)
            if duration < 10.0:
                # Short videos: shorter fades
                fade_in_ms = 200
                fade_out_ms = 200
            elif duration > 60.0:
                # Long videos: longer fades
                fade_in_ms = 1000
                fade_out_ms = 1000
            
            # Mix audio with music
            success = self.mixer.mix_audio_with_music(
                voiceover_path=voiceover_path,
                music_path=music_path,
                output_path=output_path,
                music_db=music_db,
                duck_db=duck_db,
                fade_in_ms=fade_in_ms,
                fade_out_ms=fade_out_ms,
                enable_ducking=True
            )
            
            if success:
                log.info(f"Music integration successful: {output_path}")
                log_state("music_integration", "OK", f"Audio mixed with music: {output_path}")
                return True
            else:
                log.error("Music integration failed")
                log_state("music_integration", "ERROR", "Audio mixing failed")
                return False
                
        except Exception as e:
            log.error(f"Music integration failed: {e}")
            log_state("music_integration", "ERROR", f"Music integration failed: {e}")
            return False
    
    def create_music_library_from_directory(self, source_dir: str, 
                                          license_info: Dict[str, str] = None) -> int:
        """
        Bulk import music files from a directory into the library.
        
        Args:
            source_dir: Directory containing music files
            license_info: License information for imported tracks
        
        Returns:
            int: Number of tracks successfully imported
        """
        try:
            source_path = Path(source_dir)
            if not source_path.exists():
                log.error(f"Source directory not found: {source_dir}")
                return 0
            
            # Supported audio formats
            audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}
            
            imported_count = 0
            for audio_file in source_path.rglob('*'):
                if audio_file.suffix.lower() in audio_extensions:
                    try:
                        # Extract basic info from filename
                        title = audio_file.stem
                        artist = "Unknown Artist"  # Could be enhanced with metadata extraction
                        
                        # Add to library
                        track_id = self.library.add_track(
                            file_path=str(audio_file),
                            title=title,
                            artist=artist,
                            license=license_info.get('license', 'unknown') if license_info else None,
                            source=license_info.get('source', 'local') if license_info else None
                        )
                        
                        if track_id:
                            imported_count += 1
                            log.info(f"Imported track: {title}")
                        
                    except Exception as e:
                        log.warning(f"Failed to import {audio_file}: {e}")
                        continue
            
            log.info(f"Successfully imported {imported_count} tracks")
            return imported_count
            
        except Exception as e:
            log.error(f"Bulk import failed: {e}")
            return 0
    
    def get_music_statistics(self) -> Dict[str, Any]:
        """Get statistics about the music library."""
        try:
            tracks = self.library.list_tracks()
            
            if not tracks:
                return {"total_tracks": 0, "moods": {}, "bpm_ranges": {}}
            
            # Analyze moods
            moods = {}
            for track in tracks:
                mood = track.get('mood', 'unknown')
                moods[mood] = moods.get(mood, 0) + 1
            
            # Analyze BPM ranges
            bpm_ranges = {
                "slow (60-80)": 0,
                "moderate (80-100)": 0,
                "fast (100-120)": 0,
                "very_fast (120+)": 0
            }
            
            for track in tracks:
                bpm = track.get('bpm')
                if bpm:
                    if bpm < 80:
                        bpm_ranges["slow (60-80)"] += 1
                    elif bpm < 100:
                        bpm_ranges["moderate (80-100)"] += 1
                    elif bpm < 120:
                        bpm_ranges["fast (100-120)"] += 1
                    else:
                        bpm_ranges["very_fast (120+)"] += 1
            
            return {
                "total_tracks": len(tracks),
                "moods": moods,
                "bpm_ranges": bpm_ranges,
                "avg_duration": sum(t.get('duration', 0) for t in tracks) / len(tracks) if tracks else 0
            }
            
        except Exception as e:
            log.error(f"Failed to get music statistics: {e}")
            return {"error": str(e)}
    
    def validate_music_library(self) -> Dict[str, Any]:
        """Validate music library integrity and report issues."""
        try:
            tracks = self.library.list_tracks()
            issues = []
            valid_tracks = 0
            
            for track in tracks:
                file_path = track.get('file_path', '')
                
                # Check if file exists
                if not os.path.exists(file_path):
                    issues.append(f"Missing file: {file_path}")
                    continue
                
                # Check if file is readable
                try:
                    with open(file_path, 'rb') as f:
                        f.read(1024)  # Read first 1KB to test access
                except Exception as e:
                    issues.append(f"Unreadable file: {file_path} - {e}")
                    continue
                
                # Check metadata completeness
                if not track.get('bpm'):
                    issues.append(f"Missing BPM: {track.get('title', 'Unknown')}")
                
                if not track.get('mood'):
                    issues.append(f"Missing mood: {track.get('title', 'Unknown')}")
                
                valid_tracks += 1
            
            return {
                "total_tracks": len(tracks),
                "valid_tracks": valid_tracks,
                "issues": issues,
                "health_score": (valid_tracks / len(tracks) * 100) if tracks else 0
            }
            
        except Exception as e:
            log.error(f"Library validation failed: {e}")
            return {"error": str(e)}


def test_music_integration():
    """Test the music integration system."""
    manager = MusicIntegrationManager()
    
    # Test library statistics
    stats = manager.get_music_statistics()
    print(f"Music library statistics: {stats}")
    
    # Test library validation
    validation = manager.validate_music_library()
    print(f"Library validation: {validation}")
    
    # Test music preparation (would need actual files)
    test_script = "scripts/test.txt"
    test_vo = "voiceovers/test.mp3"
    test_output = "test_output"
    
    if os.path.exists(test_script) and os.path.exists(test_vo):
        video_metadata = {
            'tone': 'conversational',
            'duration': 30.0,
            'pacing_wpm': 165
        }
        
        music_path = manager.prepare_music_for_video(
            test_script, test_vo, test_output, video_metadata
        )
        
        if music_path:
            print(f"Music prepared: {music_path}")
        else:
            print("Music preparation failed")
    else:
        print("Test files not found, skipping music preparation test")


if __name__ == "__main__":
    test_music_integration()
