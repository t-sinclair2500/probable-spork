#!/usr/bin/env python3
"""
Music Mixing and Audio Processing

Handles professional audio mixing including ducking, fading, volume control,
and integration with the video pipeline.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging

# Ensure repo root on path
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger, load_config

log = get_logger("music_mixer")


class MusicMixer:
    """Professional audio mixing with ducking, fading, and volume control."""
    
    def __init__(self, config=None):
        self.config = config or load_config()
        self.temp_dir = tempfile.mkdtemp(prefix="music_mixer_")
    
    def __del__(self):
        """Clean up temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass
    
    def mix_audio_with_music(self, voiceover_path: str, music_path: str, 
                            output_path: str, 
                            music_db: float = -22.0,
                            duck_db: float = -15.0,
                            fade_in_ms: int = 500,
                            fade_out_ms: int = 500,
                            enable_ducking: bool = True) -> bool:
        """
        Mix voiceover with background music using professional techniques.
        
        Args:
            voiceover_path: Path to voiceover audio file
            music_path: Path to background music file
            output_path: Path for output mixed audio
            music_db: Music volume in dB (negative values = quieter)
            duck_db: Ducking level in dB when voiceover is present
            fade_in_ms: Fade-in duration in milliseconds
            fade_out_ms: Fade-out duration in milliseconds
            enable_ducking: Whether to enable sidechain ducking
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            log.info(f"Mixing audio: VO={voiceover_path}, Music={music_path}")
            
            if enable_ducking:
                return self._mix_with_ducking(
                    voiceover_path, music_path, output_path,
                    music_db, duck_db, fade_in_ms, fade_out_ms
                )
            else:
                return self._mix_simple(
                    voiceover_path, music_path, output_path,
                    music_db, fade_in_ms, fade_out_ms
                )
                
        except Exception as e:
            log.error(f"Audio mixing failed: {e}")
            return False
    
    def _mix_with_ducking(self, voiceover_path: str, music_path: str, 
                          output_path: str, music_db: float, duck_db: float,
                          fade_in_ms: int, fade_out_ms: int) -> bool:
        """Mix audio with professional sidechain ducking."""
        try:
            # Create temporary files for processing
            temp_music = os.path.join(self.temp_dir, "temp_music.mp3")
            temp_ducked = os.path.join(self.temp_dir, "temp_ducked.mp3")
            
            # Step 1: Prepare music with fades
            if not self._prepare_music_with_fades(music_path, temp_music, fade_in_ms, fade_out_ms):
                return False
            
            # Step 2: Apply sidechain compression for ducking
            if not self._apply_sidechain_ducking(
                temp_music, voiceover_path, temp_ducked, music_db, duck_db
            ):
                return False
            
            # Step 3: Mix voiceover and ducked music
            if not self._final_mix(voiceover_path, temp_ducked, output_path):
                return False
            
            log.info("Successfully applied sidechain ducking and mixing")
            return True
            
        except Exception as e:
            log.error(f"Ducking-based mixing failed: {e}")
            return False
    
    def _mix_simple(self, voiceover_path: str, music_path: str, 
                    output_path: str, music_db: float,
                    fade_in_ms: int, fade_out_ms: int) -> bool:
        """Simple mixing without ducking."""
        try:
            # Create temporary music file with fades
            temp_music = os.path.join(self.temp_dir, "temp_music.mp3")
            
            if not self._prepare_music_with_fades(music_path, temp_music, fade_in_ms, fade_out_ms):
                return False
            
            # Simple volume mixing
            if not self._simple_volume_mix(voiceover_path, temp_music, output_path, music_db):
                return False
            
            log.info("Successfully applied simple volume mixing")
            return True
            
        except Exception as e:
            log.error(f"Simple mixing failed: {e}")
            return False
    
    def _prepare_music_with_fades(self, music_path: str, output_path: str,
                                 fade_in_ms: int, fade_out_ms: int) -> bool:
        """Prepare music with fade-in and fade-out effects."""
        try:
            # Use ffmpeg to apply fades
            cmd = [
                'ffmpeg', '-y', '-i', music_path,
                '-af', f'afade=t=in:st=0:d={fade_in_ms/1000:.3f},afade=t=out:st={self._get_music_duration(music_path)-fade_out_ms/1000:.3f}:d={fade_out_ms/1000:.3f}',
                '-c:a', 'libmp3lame', '-q:a', '2',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                log.error(f"Fade application failed: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            log.error(f"Failed to prepare music with fades: {e}")
            return False
    
    def _apply_sidechain_ducking(self, music_path: str, voiceover_path: str,
                                 output_path: str, music_db: float, duck_db: float) -> bool:
        """Apply sidechain compression for automatic ducking."""
        try:
            # Use ffmpeg's sidechaincompress filter for professional ducking
            cmd = [
                'ffmpeg', '-y',
                '-i', music_path,
                '-i', voiceover_path,
                '-filter_complex', f'[0:a][1:a]sidechaincompress=threshold=0.1:ratio=4:attack=5:release=50[music]; [music]volume={music_db}dB[final]',
                '-map', '[final]',
                '-c:a', 'libmp3lame', '-q:a', '2',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                log.error(f"Sidechain ducking failed: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            log.error(f"Failed to apply sidechain ducking: {e}")
            return False
    
    def _simple_volume_mix(self, voiceover_path: str, music_path: str,
                           output_path: str, music_db: float) -> bool:
        """Simple volume-based mixing without ducking."""
        try:
            # Mix voiceover and music with volume control
            cmd = [
                'ffmpeg', '-y',
                '-i', voiceover_path,
                '-i', music_path,
                '-filter_complex', f'[0:a]volume=1.0[vo]; [1:a]volume={pow(10, music_db/20):.6f}[music]; [vo][music]amix=inputs=2:duration=first[out]',
                '-map', '[out]',
                '-c:a', 'libmp3lame', '-q:a', '2',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                log.error(f"Simple volume mixing failed: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            log.error(f"Failed to apply simple volume mixing: {e}")
            return False
    
    def _final_mix(self, voiceover_path: str, music_path: str, output_path: str) -> bool:
        """Final mixing of voiceover and processed music."""
        try:
            # Simple concatenation since music is already processed
            cmd = [
                'ffmpeg', '-y',
                '-i', voiceover_path,
                '-i', music_path,
                '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first[out]',
                '-map', '[out]',
                '-c:a', 'libmp3lame', '-q:a', '2',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                log.error(f"Final mixing failed: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            log.error(f"Failed to apply final mixing: {e}")
            return False
    
    def _get_music_duration(self, music_path: str) -> float:
        """Get duration of music file in seconds."""
        try:
            cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', music_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                return 30.0  # Default fallback duration
                
        except Exception as e:
            log.warning(f"Failed to get music duration: {e}")
            return 30.0  # Default fallback duration
    
    def normalize_audio(self, input_path: str, output_path: str, 
                       target_lufs: float = -16.0) -> bool:
        """Normalize audio to target loudness using EBU R128 standard."""
        try:
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-af', f'loudnorm=I={target_lufs}:TP=-1.5:LRA=11',
                '-c:a', 'libmp3lame', '-q:a', '2',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                log.error(f"Audio normalization failed: {result.stderr}")
                return False
            
            log.info(f"Audio normalized to {target_lufs} LUFS")
            return True
            
        except Exception as e:
            log.error(f"Failed to normalize audio: {e}")
            return False
    
    def create_music_loop(self, music_path: str, output_path: str, 
                          target_duration: float) -> bool:
        """Create a seamless loop of music to match target duration."""
        try:
            # Get music duration
            music_duration = self._get_music_duration(music_path)
            
            if music_duration >= target_duration:
                # Music is long enough, just trim
                cmd = [
                    'ffmpeg', '-y', '-i', music_path,
                    '-t', str(target_duration),
                    '-c:a', 'copy',
                    output_path
                ]
            else:
                # Need to loop music to reach target duration
                # Calculate number of loops needed
                loops_needed = int(target_duration / music_duration) + 1
                
                # Create a file list for concatenation
                file_list = os.path.join(self.temp_dir, "file_list.txt")
                with open(file_list, 'w') as f:
                    for _ in range(loops_needed):
                        f.write(f"file '{music_path}'\n")
                
                # Concatenate loops
                cmd = [
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                    '-i', file_list,
                    '-t', str(target_duration),
                    '-c:a', 'copy',
                    output_path
                ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                log.error(f"Music looping failed: {result.stderr}")
                return False
            
            log.info(f"Created music loop: {target_duration}s from {music_duration}s source")
            return True
            
        except Exception as e:
            log.error(f"Failed to create music loop: {e}")
            return False


def test_music_mixer():
    """Test the music mixer functionality."""
    mixer = MusicMixer()
    
    # Test with sample files (these would need to exist)
    test_vo = "voiceovers/test.mp3"
    test_music = "assets/music/test.mp3"
    test_output = "test_mixed.mp3"
    
    if os.path.exists(test_vo) and os.path.exists(test_music):
        success = mixer.mix_audio_with_music(
            test_vo, test_music, test_output,
            music_db=-22.0, duck_db=-15.0,
            fade_in_ms=500, fade_out_ms=500,
            enable_ducking=True
        )
        
        if success:
            print(f"Successfully created mixed audio: {test_output}")
        else:
            print("Audio mixing failed")
    else:
        print("Test files not found, skipping test")


if __name__ == "__main__":
    test_music_mixer()
