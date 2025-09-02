#!/usr/bin/env python3
"""
Music Library Management System

Handles music bed selection, BPM analysis, mood tagging, and integration
with the video pipeline according to the music bed policy.
"""

import json
import os
import subprocess

# Ensure repo root on path
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger, load_config

log = get_logger("music_library")


@dataclass
class MusicTrack:
    """Represents a music track with metadata."""

    file_path: str
    title: str
    artist: str
    bpm: Optional[int] = None
    mood: Optional[str] = None
    genre: Optional[str] = None
    duration: Optional[float] = None
    license: Optional[str] = None
    source: Optional[str] = None
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MusicLibrary:
    """Manages music tracks with BPM analysis and mood tagging."""

    def __init__(self, library_path: str = "assets/music"):
        self.library_path = Path(library_path)
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.library_path / "library.json"
        self.tracks: Dict[str, MusicTrack] = {}
        self._load_library()

    def _load_library(self):
        """Load existing music library metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    data = json.load(f)
                    for track_id, track_data in data.items():
                        self.tracks[track_id] = MusicTrack(**track_data)
                log.info(f"Loaded {len(self.tracks)} tracks from music library")
            except Exception as e:
                log.warning(f"Failed to load music library: {e}")

    def _save_library(self):
        """Save music library metadata."""
        try:
            data = {
                track_id: track.to_dict() for track_id, track in self.tracks.items()
            }
            with open(self.metadata_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save music library: {e}")

    def add_track(
        self,
        file_path: str,
        title: str,
        artist: str,
        mood: Optional[str] = None,
        genre: Optional[str] = None,
        license: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Add a new track to the library with automatic BPM detection."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Music file not found: {file_path}")

        # Generate track ID from filename
        track_id = Path(file_path).stem

        # Detect BPM if not provided
        bpm = None
        if not mood:  # Only detect BPM if we need to analyze the track
            bpm = self._detect_bpm(file_path)

        # Get duration
        duration = self._get_duration(file_path)

        # Create track object
        track = MusicTrack(
            file_path=file_path,
            title=title,
            artist=artist,
            bpm=bpm,
            mood=mood,
            genre=genre,
            duration=duration,
            license=license,
            source=source,
            tags=tags or [],
        )

        self.tracks[track_id] = track
        self._save_library()
        log.info(f"Added track: {title} by {artist} (BPM: {bpm})")

        return track_id

    def _detect_bpm(self, file_path: str) -> Optional[int]:
        """Detect BPM using ffmpeg and audio analysis."""
        try:
            # Use ffmpeg to extract audio features for BPM detection
            # This is a simplified approach - in production you might want
            # a more sophisticated BPM detection library
            cmd = [
                "ffmpeg",
                "-i",
                file_path,
                "-af",
                "silencedetect=noise=-50dB:d=0.1",
                "-f",
                "null",
                "-",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            # For now, return a default BPM based on file analysis
            # In a full implementation, you'd analyze the audio data
            # This is a placeholder that would be replaced with actual BPM detection
            return 120  # Default BPM

        except Exception as e:
            log.warning(f"BPM detection failed for {file_path}: {e}")
            return None

    def _get_duration(self, file_path: str) -> Optional[float]:
        """Get audio file duration using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception as e:
            log.warning(f"Duration detection failed for {file_path}: {e}")
        return None

    def select_track(
        self,
        target_bpm: Optional[int] = None,
        mood: Optional[str] = None,
        genre: Optional[str] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
    ) -> Optional[MusicTrack]:
        """Select the best matching track based on criteria."""
        if not self.tracks:
            log.warning("No tracks available in music library")
            return None

        # Score tracks based on criteria
        scored_tracks = []
        for track in self.tracks.values():
            score = 0

            # BPM matching (closer is better)
            if target_bpm and track.bpm:
                bpm_diff = abs(track.bpm - target_bpm)
                if bpm_diff <= 10:
                    score += 100 - bpm_diff * 5  # Higher score for closer BPM
                elif bpm_diff <= 20:
                    score += 50 - bpm_diff * 2

            # Mood matching
            if mood and track.mood and mood.lower() == track.mood.lower():
                score += 50

            # Genre matching
            if genre and track.genre and genre.lower() == track.genre.lower():
                score += 30

            # Duration constraints
            if track.duration:
                if min_duration and track.duration < min_duration:
                    continue  # Skip tracks that are too short
                if max_duration and track.duration > max_duration:
                    continue  # Skip tracks that are too long

                # Prefer tracks that are close to target duration
                if min_duration and max_duration:
                    target_duration = (min_duration + max_duration) / 2
                    duration_diff = abs(track.duration - target_duration)
                    score += max(0, 20 - duration_diff)

            scored_tracks.append((track, score))

        if not scored_tracks:
            return None

        # Sort by score and return the best match
        scored_tracks.sort(key=lambda x: x[1], reverse=True)
        best_track = scored_tracks[0][0]
        best_score = scored_tracks[0][1]

        log.info(f"Selected track: {best_track.title} (score: {best_score})")
        return best_track

    def get_tracks_by_mood(self, mood: str) -> List[MusicTrack]:
        """Get all tracks matching a specific mood."""
        return [
            track
            for track in self.tracks.values()
            if track.mood and track.mood.lower() == mood.lower()
        ]

    def get_tracks_by_bpm_range(self, min_bpm: int, max_bpm: int) -> List[MusicTrack]:
        """Get all tracks within a BPM range."""
        return [
            track
            for track in self.tracks.values()
            if track.bpm and min_bpm <= track.bpm <= max_bpm
        ]

    def list_tracks(self) -> List[Dict[str, Any]]:
        """List all tracks with metadata."""
        return [track.to_dict() for track in self.tracks.values()]

    def remove_track(self, track_id: str) -> bool:
        """Remove a track from the library."""
        if track_id in self.tracks:
            del self.tracks[track_id]
            self._save_library()
            log.info(f"Removed track: {track_id}")
            return True
        return False


class MusicSelectionAgent:
    """Intelligent music selection based on video content analysis."""

    def __init__(self, music_library: MusicLibrary):
        self.library = music_library
        self.config = load_config()

    def select_music_for_video(
        self, script_text: str, tone: str, target_duration: float, pacing_wpm: int
    ) -> Optional[MusicTrack]:
        """Select appropriate music based on video content analysis."""
        log.info(
            f"Selecting music for video: tone={tone}, duration={target_duration}s, pacing={pacing_wpm}wpm"
        )

        # Analyze script content for mood indicators
        mood = self._analyze_script_mood(script_text, tone)

        # Estimate target BPM based on pacing
        target_bpm = self._estimate_target_bpm(pacing_wpm, tone)

        # Select track with appropriate constraints
        track = self.library.select_track(
            target_bpm=target_bpm,
            mood=mood,
            min_duration=target_duration * 0.8,  # Allow some flexibility
            max_duration=target_duration * 1.5,
        )

        if track:
            log.info(
                f"Selected music: {track.title} by {track.artist} (BPM: {track.bpm}, Mood: {track.mood})"
            )
        else:
            log.warning("No suitable music track found")

        return track

    def _analyze_script_mood(self, script_text: str, tone: str) -> str:
        """Analyze script content to determine mood."""
        text_lower = script_text.lower()

        # Mood mapping based on tone and content keywords
        mood_mapping = {
            "energetic": ["energetic", "exciting", "amazing", "incredible", "awesome"],
            "calm": ["calm", "peaceful", "gentle", "soothing", "relaxing"],
            "dramatic": ["dramatic", "intense", "powerful", "epic", "thrilling"],
            "playful": ["fun", "playful", "silly", "humorous", "entertaining"],
            "professional": [
                "professional",
                "serious",
                "formal",
                "business",
                "corporate",
            ],
            "friendly": ["friendly", "warm", "welcoming", "approachable", "kind"],
        }

        # Default mood based on tone
        default_mood = {
            "energetic": "energetic",
            "calm": "calm",
            "dramatic": "dramatic",
            "playful": "playful",
            "professional": "professional",
            "friendly": "friendly",
            "conversational": "friendly",
            "authoritative": "professional",
            "silly": "playful",
        }.get(tone.lower(), "friendly")

        # Check for mood indicators in script
        for mood, keywords in mood_mapping.items():
            if any(keyword in text_lower for keyword in keywords):
                return mood

        return default_mood

    def _estimate_target_bpm(self, pacing_wpm: int, tone: str) -> int:
        """Estimate target BPM based on pacing and tone."""
        # Base BPM on pacing (words per minute)
        base_bpm = 90  # Default moderate pace

        if pacing_wpm < 140:
            base_bpm = 70  # Slow, deliberate
        elif pacing_wpm > 180:
            base_bpm = 130  # Fast, energetic

        # Adjust based on tone
        tone_adjustments = {
            "energetic": 20,
            "dramatic": 15,
            "playful": 10,
            "calm": -20,
            "professional": -5,
            "friendly": 0,
        }

        adjustment = tone_adjustments.get(tone.lower(), 0)
        target_bpm = base_bpm + adjustment

        # Ensure BPM is within reasonable bounds
        target_bpm = max(60, min(160, target_bpm))

        log.info(
            f"Estimated target BPM: {target_bpm} (base: {base_bpm}, tone adjustment: {adjustment})"
        )
        return target_bpm


def create_sample_music_library():
    """Create a sample music library with placeholder tracks."""
    library = MusicLibrary()

    # Add some sample tracks (these would be replaced with actual music files)
    sample_tracks = [
        {
            "file_path": "assets/music/sample_energetic.mp3",
            "title": "Energetic Uplift",
            "artist": "Sample Artist",
            "bpm": 130,
            "mood": "energetic",
            "genre": "electronic",
            "license": "royalty-free",
            "source": "sample",
            "tags": ["upbeat", "motivational", "tech"],
        },
        {
            "file_path": "assets/music/sample_calm.mp3",
            "title": "Calm Reflection",
            "artist": "Sample Artist",
            "bpm": 70,
            "mood": "calm",
            "genre": "ambient",
            "license": "royalty-free",
            "source": "sample",
            "tags": ["peaceful", "meditation", "background"],
        },
        {
            "file_path": "assets/music/sample_professional.mp3",
            "title": "Professional Business",
            "artist": "Sample Artist",
            "bpm": 90,
            "mood": "professional",
            "genre": "corporate",
            "license": "royalty-free",
            "source": "sample",
            "tags": ["business", "corporate", "formal"],
        },
    ]

    for track_info in sample_tracks:
        # Only add if the file exists (for testing purposes)
        if os.path.exists(track_info["file_path"]):
            library.add_track(**track_info)

    return library


if __name__ == "__main__":
    # Test the music library
    library = create_sample_music_library()
    agent = MusicSelectionAgent(library)

    # Test selection
    sample_script = (
        "This is an exciting and energetic video about amazing new technology!"
    )
    track = agent.select_music_for_video(sample_script, "energetic", 30.0, 165)

    if track:
        print(f"Selected: {track.title} by {track.artist}")
    else:
        print("No track selected")
