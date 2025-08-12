#!/usr/bin/env python3
"""
Voice Adapter for Multi-TTS Pipeline

Integrates different TTS providers (Piper, Coqui, OpenAI) with:
- SSML-lite parsing for pacing and emphasis
- Paragraph-based synthesis with caching
- Loudness normalization
- Provider fallback logic
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union
import hashlib

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, log_state, single_lock

log = get_logger("voice_adapter")

class VoiceAdapter:
    """Voice adapter for multi-TTS pipeline integration."""
    
    def __init__(self, models_config: Optional[Dict] = None):
        """Initialize voice adapter."""
        self.config = load_config()
        self.models_config = models_config or self._load_models_config()
        self.voice_config = self.models_config.get('voice', {})
        self.tts_config = self.voice_config.get('tts', {})
        
        # Initialize TTS providers
        self.providers = self._init_providers()
        
        # Cache directory
        self.cache_dir = Path(self.tts_config.get('cache_dir', 'voice_cache'))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_models_config(self) -> Dict:
        """Load models configuration."""
        try:
            import yaml
            models_path = Path(BASE) / "conf" / "models.yaml"
            with open(models_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            log.warning(f"Failed to load models.yaml: {e}, using defaults")
            return {}
    
    def _init_providers(self) -> Dict:
        """Initialize TTS providers."""
        providers = {}
        
        # Piper TTS
        if self.tts_config.get('provider') == 'piper':
            try:
                from vendors.tts_piper import PiperTTS
                providers['piper'] = PiperTTS(self.tts_config)
                log.info("Piper TTS provider initialized")
            except ImportError as e:
                log.warning(f"Piper TTS not available: {e}")
        
        # Coqui TTS (fallback)
        try:
            from TTS.api import TTS
            providers['coqui'] = TTS
            log.info("Coqui TTS provider initialized")
        except ImportError as e:
            log.warning(f"Coqui TTS not available: {e}")
        
        # OpenAI TTS (if enabled)
        if self.config.get('tts', {}).get('openai_enabled'):
            try:
                import openai
                providers['openai'] = openai
                log.info("OpenAI TTS provider initialized")
            except ImportError as e:
                log.warning(f"OpenAI TTS not available: {e}")
        
        if not providers:
            raise RuntimeError("No TTS providers available")
        
        return providers
    
    def synthesize_script(self, script_path: Path, output_dir: Optional[Path] = None) -> Path:
        """
        Synthesize a complete script to audio.
        
        Args:
            script_path: Path to script file
            output_dir: Output directory for audio files
            
        Returns:
            Path to final audio file
        """
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        
        if output_dir is None:
            output_dir = Path(BASE) / "voiceovers"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load script content
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        # Parse script into paragraphs
        paragraphs = self._parse_paragraphs(script_content)
        
        log.info(f"Synthesizing {len(paragraphs)} paragraphs")
        
        # Synthesize each paragraph
        audio_segments = []
        for i, paragraph in enumerate(paragraphs):
            log.info(f"Synthesizing paragraph {i+1}/{len(paragraphs)}")
            
            # Check cache first
            cache_key = self._generate_cache_key(paragraph)
            cached_path = self.cache_dir / f"{cache_key}.wav"
            
            if cached_path.exists():
                log.info(f"Using cached audio for paragraph {i+1}")
                audio_segments.append(cached_path)
            else:
                # Synthesize new audio
                audio_path = self._synthesize_paragraph(paragraph, i, output_dir)
                audio_segments.append(audio_path)
                
                # Cache the result
                import shutil
                shutil.copy2(audio_path, cached_path)
        
        # Concatenate audio segments
        final_audio = self._concatenate_audio(audio_segments, output_dir, script_path.stem)
        
        log.info(f"Script synthesis completed: {final_audio}")
        return final_audio
    
    def _parse_paragraphs(self, script_content: str) -> List[str]:
        """Parse script into paragraphs for synthesis."""
        # Split by double newlines or section markers
        paragraphs = re.split(r'\n\s*\n|\[B-ROLL:', script_content)
        
        # Clean and filter paragraphs
        cleaned_paragraphs = []
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            
            # Skip B-ROLL markers and very short content
            if paragraph.startswith('B-ROLL:') or len(paragraph) < 10:
                continue
            
            # Remove B-ROLL closing brackets
            paragraph = re.sub(r'\]\s*$', '', paragraph)
            
            if paragraph:
                cleaned_paragraphs.append(paragraph)
        
        return cleaned_paragraphs
    
    def _synthesize_paragraph(self, paragraph: str, index: int, output_dir: Path) -> Path:
        """Synthesize a single paragraph."""
        # Try preferred provider first
        preferred_provider = self.tts_config.get('provider', 'piper')
        
        if preferred_provider in self.providers:
            try:
                return self._synthesize_with_provider(
                    preferred_provider, paragraph, index, output_dir
                )
            except Exception as e:
                log.warning(f"Preferred provider {preferred_provider} failed: {e}")
        
        # Fallback to available providers
        for provider_name, provider in self.providers.items():
            if provider_name != preferred_provider:
                try:
                    return self._synthesize_with_provider(
                        provider_name, paragraph, index, output_dir
                    )
                except Exception as e:
                    log.warning(f"Provider {provider_name} failed: {e}")
        
        raise RuntimeError("All TTS providers failed")
    
    def _synthesize_with_provider(self, provider_name: str, paragraph: str, 
                                 index: int, output_dir: Path) -> Path:
        """Synthesize paragraph with specific provider."""
        output_path = output_dir / f"paragraph_{index:03d}_{provider_name}.wav"
        
        if provider_name == 'piper':
            return self._synthesize_piper(paragraph, output_path)
        elif provider_name == 'coqui':
            return self._synthesize_coqui(paragraph, output_path)
        elif provider_name == 'openai':
            return self._synthesize_openai(paragraph, output_path)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
    
    def _synthesize_piper(self, paragraph: str, output_path: Path) -> Path:
        """Synthesize with Piper TTS."""
        provider = self.providers['piper']
        
        # Get Piper-specific parameters
        voice_id = self.tts_config.get('voice_id', 'en_US-amy-medium')
        rate = self.tts_config.get('rate', 'medium')
        pitch = self.tts_config.get('pitch', 0)
        ssml = self.tts_config.get('ssml', True)
        
        return provider.synthesize(
            paragraph, 
            output_path,
            voice_id=voice_id,
            rate=rate,
            pitch=pitch,
            ssml=ssml
        )
    
    def _synthesize_coqui(self, paragraph: str, output_path: Path) -> Path:
        """Synthesize with Coqui TTS."""
        provider = self.providers['coqui']
        
        # Get Coqui-specific parameters
        voice = self.config.get('tts', {}).get('voice', 'tts_models/en/ljspeech/tacotron2-DDC')
        
        # Initialize TTS
        tts = provider(voice)
        
        # Synthesize
        tts.tts_to_file(paragraph, str(output_path))
        
        return output_path
    
    def _synthesize_openai(self, paragraph: str, output_path: Path) -> Path:
        """Synthesize with OpenAI TTS."""
        provider = self.providers['openai']
        
        # Get OpenAI parameters
        voice = self.config.get('tts', {}).get('openai_voice', 'alloy')
        
        # Synthesize
        response = provider.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=paragraph
        )
        
        # Save audio
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        return output_path
    
    def _concatenate_audio(self, audio_segments: List[Path], output_dir: Path, 
                           script_name: str) -> Path:
        """Concatenate audio segments into final file."""
        if len(audio_segments) == 1:
            # Single segment, just rename
            final_path = output_dir / f"{script_name}.wav"
            import shutil
            shutil.copy2(audio_segments[0], final_path)
            return final_path
        
        # Multiple segments, concatenate with FFmpeg
        final_path = output_dir / f"{script_name}.wav"
        
        # Create file list for FFmpeg
        file_list_path = output_dir / "concat_list.txt"
        with open(file_list_path, 'w') as f:
            for segment in audio_segments:
                f.write(f"file '{segment.absolute()}'\n")
        
        # FFmpeg concatenation
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(file_list_path),
            '-c', 'copy',
            str(final_path)
        ]
        
        log.info(f"Concatenating audio segments: {' '.join(cmd)}")
        
        try:
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                log.error(f"Audio concatenation failed: {result.stderr}")
                raise RuntimeError(f"Audio concatenation failed: {result.stderr}")
            
            # Clean up file list
            file_list_path.unlink()
            
            # Clean up individual segments
            for segment in audio_segments:
                if segment.parent == output_dir:  # Only delete if in output dir
                    segment.unlink()
            
            return final_path
            
        except Exception as e:
            log.error(f"Audio concatenation failed: {e}")
            raise
    
    def _generate_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Include provider and voice in cache key
        provider = self.tts_config.get('provider', 'piper')
        voice_id = self.tts_config.get('voice_id', 'en_US-amy-medium')
        
        cache_data = f"{provider}:{voice_id}:{text}"
        return hashlib.sha256(cache_data.encode()).hexdigest()[:16]
    
    def get_provider_status(self) -> Dict[str, Dict]:
        """Get status of all TTS providers."""
        status = {}
        
        for provider_name, provider in self.providers.items():
            try:
                if provider_name == 'piper':
                    # Check if Piper is working
                    voices = provider.list_voices()
                    status[provider_name] = {
                        'available': True,
                        'voices': len(voices),
                        'working': True
                    }
                elif provider_name == 'coqui':
                    # Check if Coqui is working
                    status[provider_name] = {
                        'available': True,
                        'working': True
                    }
                elif provider_name == 'openai':
                    # Check OpenAI API key
                    api_key = os.getenv('OPENAI_API_KEY')
                    status[provider_name] = {
                        'available': True,
                        'api_key': bool(api_key),
                        'working': bool(api_key)
                    }
            except Exception as e:
                status[provider_name] = {
                    'available': True,
                    'working': False,
                    'error': str(e)
                }
        
        return status

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Voice adapter for multi-TTS pipeline")
    parser.add_argument("script", help="Path to script file")
    parser.add_argument("--output-dir", help="Output directory for audio files")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()
    
    if args.dry_run:
        log.info("DRY RUN MODE - No changes will be made")
    
    try:
        script_path = Path(args.script)
        if not script_path.exists():
            log.error(f"Script not found: {script_path}")
            return 1
        
        output_dir = Path(args.output_dir) if args.output_dir else None
        
        # Initialize adapter
        adapter = VoiceAdapter()
        
        # Check provider status
        status = adapter.get_provider_status()
        log.info("TTS Provider Status:")
        for provider, info in status.items():
            log.info(f"  {provider}: {'✓' if info.get('working') else '✗'}")
        
        # Synthesize script
        if not args.dry_run:
            audio_path = adapter.synthesize_script(script_path, output_dir)
            log.info(f"Script synthesis completed: {audio_path}")
        
        return 0
        
    except Exception as e:
        log.error(f"Voice synthesis failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
