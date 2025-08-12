#!/usr/bin/env python3
"""
Piper TTS Adapter

Provides text-to-speech synthesis using Piper with:
- SSML-lite parsing for pacing and emphasis
- Loudness normalization to target LUFS
- Audio caching for performance
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.core import get_logger

log = get_logger("tts_piper")

class PiperTTS:
    """Piper TTS adapter with SSML-lite parsing and audio processing."""
    
    def __init__(self, config: Dict):
        """
        Initialize Piper TTS.
        
        Args:
            config: TTS configuration from models.yaml
        """
        self.config = config
        self.voice_id = config.get('voice_id', 'en_US-amy-medium')
        self.rate = config.get('rate', 'medium')
        self.pitch = config.get('pitch', 0)
        self.pause_ms = config.get('pause_ms', 120)
        self.ssml = config.get('ssml', True)
        self.lufs_target = config.get('lufs_target', -16.0)
        self.cache_dir = Path(config.get('cache_dir', 'voice_cache'))
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Piper command template
        self.piper_cmd = self._find_piper_command()
        
        # Rate mapping
        self.rate_map = {
            'slow': 0.8,
            'medium': 1.0,
            'fast': 1.2
        }
    
    def _find_piper_command(self) -> str:
        """Find Piper executable."""
        # Check common locations
        possible_paths = [
            'piper',
            '/usr/local/bin/piper',
            str(ROOT / 'vendor' / 'piper' / 'piper'),
            str(ROOT / 'bin' / 'piper')
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    log.info(f"Found Piper at: {path}")
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        log.warning("Piper not found in PATH, will try to use 'piper' command")
        return 'piper'
    
    def synthesize(self, text: str, output_path: Optional[Path] = None, 
                   **kwargs) -> Path:
        """
        Synthesize text to speech.
        
        Args:
            text: Text to synthesize
            output_path: Output path for audio file
            **kwargs: Override config parameters
            
        Returns:
            Path to generated audio file
        """
        # Check cache first
        cache_key = self._generate_cache_key(text, kwargs)
        cached_path = self.cache_dir / f"{cache_key}.wav"
        
        if cached_path.exists():
            log.info(f"Using cached audio: {cached_path}")
            if output_path:
                # Copy cached file to desired location
                import shutil
                shutil.copy2(cached_path, output_path)
                return output_path
            return cached_path
        
        # Parse SSML-lite if enabled
        if self.ssml and kwargs.get('ssml', True):
            parsed_text = self._parse_ssml_lite(text)
        else:
            parsed_text = text
        
        # Generate temporary output path
        if not output_path:
            output_path = Path(tempfile.mktemp(suffix='.wav'))
        
        # Synthesize with Piper
        wav_path = self._synthesize_with_piper(parsed_text, output_path, **kwargs)
        
        # Apply loudness normalization
        normalized_path = self._normalize_loudness(wav_path)
        
        # Cache the result
        if normalized_path != cached_path:
            import shutil
            shutil.copy2(normalized_path, cached_path)
        
        return normalized_path
    
    def _parse_ssml_lite(self, text: str) -> str:
        """
        Parse SSML-lite tags for pacing and emphasis.
        
        Supported tags:
        - <break time="300ms"/> - Pause for specified duration
        - <emphasis>text</emphasis> - Emphasized text
        - <prosody rate="slow|medium|fast">text</prosody> - Rate control
        """
        # Handle break tags
        text = re.sub(r'<break\s+time="(\d+)ms"\s*/>', 
                     lambda m: f" [PAUSE_{m.group(1)}ms] ", text)
        
        # Handle emphasis tags
        text = re.sub(r'<emphasis>(.*?)</emphasis>', 
                     lambda m: f" [EMPHASIS] {m.group(1)} [END_EMPHASIS] ", text)
        
        # Handle prosody rate tags
        text = re.sub(r'<prosody\s+rate="(slow|medium|fast)">(.*?)</prosody>',
                     lambda m: f" [RATE_{m.group(1).upper()}] {m.group(2)} [END_RATE] ", text)
        
        return text
    
    def _synthesize_with_piper(self, text: str, output_path: Path, **kwargs) -> Path:
        """Synthesize text using Piper command-line tool."""
        # Get parameters
        voice_id = kwargs.get('voice_id', self.voice_id)
        rate = kwargs.get('rate', self.rate)
        pitch = kwargs.get('pitch', self.pitch)
        
        # Convert rate to Piper's speed parameter
        speed = self.rate_map.get(rate, 1.0)
        
        # Build Piper command
        cmd = [
            self.piper_cmd,
            '--model', f'models/{voice_id}.onnx',
            '--output_file', str(output_path),
            '--speed', str(speed)
        ]
        
        if pitch != 0:
            cmd.extend(['--pitch', str(pitch)])
        
        log.info(f"Running Piper: {' '.join(cmd)}")
        
        try:
            # Create temporary text file for input
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(text)
                temp_text_path = f.name
            
            # Add input file to command
            cmd.append(temp_text_path)
            
            # Run Piper
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # Clean up temp file
            os.unlink(temp_text_path)
            
            if result.returncode != 0:
                log.error(f"Piper failed: {result.stderr}")
                raise RuntimeError(f"Piper synthesis failed: {result.stderr}")
            
            log.info(f"Piper synthesis completed: {output_path}")
            return output_path
            
        except subprocess.TimeoutExpired:
            log.error("Piper synthesis timed out")
            raise RuntimeError("Piper synthesis timed out")
        except Exception as e:
            log.error(f"Piper synthesis failed: {e}")
            raise
    
    def _normalize_loudness(self, audio_path: Path) -> Path:
        """Apply loudness normalization using FFmpeg."""
        if self.lufs_target is None:
            return audio_path
        
        # Create normalized output path
        normalized_path = audio_path.parent / f"{audio_path.stem}_normalized{audio_path.suffix}"
        
        # FFmpeg loudnorm filter
        cmd = [
            'ffmpeg', '-y',  # Overwrite output
            '-i', str(audio_path),
            '-af', f'loudnorm=I={self.lufs_target}:TP=-1.5:LRA=11',
            '-ar', '22050',  # Sample rate
            str(normalized_path)
        ]
        
        log.info(f"Applying loudness normalization: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                log.error(f"Loudness normalization failed: {result.stderr}")
                return audio_path  # Return original if normalization fails
            
            log.info(f"Loudness normalization completed: {normalized_path}")
            return normalized_path
            
        except subprocess.TimeoutExpired:
            log.error("Loudness normalization timed out")
            return audio_path
        except Exception as e:
            log.error(f"Loudness normalization failed: {e}")
            return audio_path
    
    def _generate_cache_key(self, text: str, kwargs: Dict) -> str:
        """Generate cache key for text and parameters."""
        # Create hash of text and parameters
        cache_data = {
            'text': text,
            'voice_id': kwargs.get('voice_id', self.voice_id),
            'rate': kwargs.get('rate', self.rate),
            'pitch': kwargs.get('pitch', self.pitch),
            'ssml': kwargs.get('ssml', self.ssml)
        }
        
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()[:16]
    
    def list_voices(self) -> List[str]:
        """List available voices."""
        try:
            # Check if Piper supports voice listing
            result = subprocess.run([self.piper_cmd, '--list_voices'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                voices = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        voices.append(line.strip())
                return voices
            else:
                log.warning("Piper doesn't support --list_voices")
                return []
                
        except Exception as e:
            log.error(f"Failed to list voices: {e}")
            return []
    
    def get_voice_info(self, voice_id: str) -> Optional[Dict]:
        """Get information about a specific voice."""
        try:
            # Check if voice model exists
            model_path = Path(f'models/{voice_id}.onnx')
            if model_path.exists():
                return {
                    'voice_id': voice_id,
                    'model_path': str(model_path),
                    'model_size': model_path.stat().st_size,
                    'available': True
                }
            else:
                return {
                    'voice_id': voice_id,
                    'model_path': str(model_path),
                    'available': False
                }
                
        except Exception as e:
            log.error(f"Failed to get voice info for {voice_id}: {e}")
            return None

def synthesize(text: str, voice_id: str, rate: str = "medium", 
               pitch: int = 0, pause_ms: int = 120, ssml: bool = True, 
               lufs_target: float = -16.0, cache_dir: str = "voice_cache") -> str:
    """
    Convenience function for text-to-speech synthesis.
    
    Args:
        text: Text to synthesize
        voice_id: Voice identifier
        rate: Speech rate (slow, medium, fast)
        pitch: Pitch adjustment (-20 to +20)
        pause_ms: Default pause between sentences
        ssml: Enable SSML-lite parsing
        lufs_target: Target loudness in LUFS
        cache_dir: Directory for audio caching
        
    Returns:
        Path to generated audio file
    """
    config = {
        'voice_id': voice_id,
        'rate': rate,
        'pitch': pitch,
        'pause_ms': pause_ms,
        'ssml': ssml,
        'lufs_target': lufs_target,
        'cache_dir': cache_dir
    }
    
    tts = PiperTTS(config)
    return str(tts.synthesize(text))

if __name__ == "__main__":
    # Test the TTS system
    config = {
        'voice_id': 'en_US-amy-medium',
        'rate': 'medium',
        'pitch': 0,
        'pause_ms': 120,
        'ssml': True,
        'lufs_target': -16.0,
        'cache_dir': 'voice_cache'
    }
    
    tts = PiperTTS(config)
    
    # Test text
    test_text = """
    This is a test of the Piper TTS system.
    <break time="500ms"/>
    It supports <emphasis>SSML-lite</emphasis> tags for pacing.
    <prosody rate="slow">This part is spoken slowly.</prosody>
    """
    
    try:
        output_path = tts.synthesize(test_text)
        print(f"TTS synthesis completed: {output_path}")
    except Exception as e:
        print(f"TTS synthesis failed: {e}")
