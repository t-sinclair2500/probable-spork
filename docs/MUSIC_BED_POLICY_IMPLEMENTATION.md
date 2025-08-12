# Music Bed Policy Implementation

This document describes the implementation of the music bed policy for the video pipeline, ensuring all videos have appropriate background music that complements the content without overpowering narration.

## Overview

The music bed policy implementation consists of three main components:

1. **Music Library Management** (`bin/music_library.py`)
2. **Music Mixing & Processing** (`bin/music_mixer.py`) 
3. **Music Integration Manager** (`bin/music_integration.py`)

## Features

### Music Selection
- **Intelligent Selection**: Automatically selects music based on script content analysis
- **BPM Matching**: Matches music tempo to video pacing (words per minute)
- **Mood Analysis**: Analyzes script content to determine appropriate mood
- **Tone Alignment**: Considers video tone (energetic, calm, professional, etc.)

### Audio Processing
- **Sidechain Ducking**: Automatically reduces music volume during voiceover
- **Fade Effects**: Smooth fade-in/out aligned to scene transitions
- **Volume Control**: Configurable music and ducking levels
- **Loop Management**: Seamlessly extends music to match video duration

### Library Management
- **Metadata Tracking**: BPM, mood, genre, license, and source information
- **Bulk Import**: Import music from directories with automatic metadata detection
- **Quality Control**: Validation and health checking of music library
- **License Compliance**: Track licensing requirements and attribution

## Configuration

### Global Configuration (`conf/global.yaml`)

```yaml
# Music bed policy configuration
music:
  enabled: true                  # Enable/disable music bed functionality
  library_path: "assets/music"   # Path to music library
  auto_select: true              # Automatically select music based on content
  require_music: false           # Whether music is required for all videos
  fallback_to_silent: true      # Fallback to silent if no music available
  
  # Music selection criteria
  selection:
    bpm_weight: 0.4              # Weight for BPM matching (0.0-1.0)
    mood_weight: 0.4             # Weight for mood matching (0.0-1.0)
    genre_weight: 0.2            # Weight for genre matching (0.0-1.0)
    
  # Audio processing settings
  processing:
    enable_ducking: true         # Enable sidechain ducking
    enable_fades: true           # Enable fade in/out effects
    fade_in_ms: 500             # Fade-in duration in milliseconds
    fade_out_ms: 500            # Fade-out duration in milliseconds
    loop_strategy: "seamless"    # seamless, crossfade, or extend
    
  # Quality and licensing
  quality:
    min_bitrate: "128k"          # Minimum music bitrate
    preferred_formats: ["mp3", "wav", "m4a"]
    require_license_info: true   # Require license information for tracks
```

### Render Settings

```yaml
render:
  music_db: -22                 # Music volume in dB (negative = quieter)
  duck_db: -15                  # Ducking level in dB when VO present
```

## Usage

### Command Line Management

The `bin/music_manager.py` CLI tool provides comprehensive music library management:

```bash
# Setup music library
python bin/music_manager.py setup

# Import music from directory
python bin/music_manager.py import --source /path/to/music --license "royalty-free"

# View library statistics
python bin/music_manager.py stats

# Validate library integrity
python bin/music_manager.py validate

# Test music selection
python bin/music_manager.py test --script scripts/test.txt --tone conversational --duration 30

# List tracks with filters
python bin/music_manager.py list --mood energetic --bpm-min 120
```

### Programmatic Usage

```python
from bin.music_integration import MusicIntegrationManager

# Initialize manager
manager = MusicIntegrationManager()

# Prepare music for video
music_path = manager.prepare_music_for_video(
    script_path="scripts/video.txt",
    voiceover_path="voiceovers/video.mp3", 
    output_dir="output/",
    video_metadata={
        'tone': 'conversational',
        'duration': 30.0,
        'pacing_wpm': 165
    }
)

# Integrate music with voiceover
success = manager.integrate_music_with_video(
    voiceover_path="voiceovers/video.mp3",
    music_path=music_path,
    output_path="output/final_audio.mp3",
    video_metadata={'duration': 30.0}
)
```

## Policy Compliance

### Success Criteria Met

✅ **Music bed selected to match pacing (BPM) and tone of video**
- Automatic BPM detection and matching
- Script content analysis for mood determination
- Tone-based music selection

✅ **Track library stored locally or licensed from a provider**
- Local music library with metadata tracking
- License and source information management
- Support for various audio formats

✅ **Automatic ducking during voiceover segments**
- Sidechain compression for professional ducking
- Configurable ducking levels
- Fallback to simple volume mixing

✅ **Fades in/out aligned to scene transitions**
- Configurable fade durations
- Duration-based fade adjustment
- Smooth transitions between scenes

### Test Criteria Met

✅ **For 3 test videos, verify music complements tone**
- Energetic tech video → Energetic music
- Calm educational video → Calm music  
- Professional business video → Professional music

✅ **Confirm narration is clearly audible over music**
- Sidechain ducking reduces music during voiceover
- Configurable volume separation
- Professional audio mixing techniques

✅ **Ensure no abrupt music cuts**
- Fade-in/out effects on all music
- Seamless looping for extended content
- Smooth scene transitions

## Implementation Details

### Music Selection Algorithm

1. **Content Analysis**: Analyze script text for mood indicators
2. **Pacing Calculation**: Estimate target BPM based on words per minute
3. **Scoring System**: Score tracks based on BPM, mood, and genre match
4. **Duration Validation**: Ensure music length is appropriate for video

### Audio Processing Pipeline

1. **Music Preparation**: Apply fades and extend/loop as needed
2. **Sidechain Ducking**: Use ffmpeg for professional audio compression
3. **Final Mixing**: Combine voiceover and processed music
4. **Quality Control**: Ensure output meets audio standards

### Library Management

1. **Metadata Extraction**: BPM detection, duration analysis
2. **File Organization**: Structured storage with metadata tracking
3. **Health Monitoring**: Validation and issue reporting
4. **Import Automation**: Bulk import with license tracking

## Dependencies

- **pydub**: Audio processing and manipulation
- **ffmpeg**: Professional audio/video processing
- **ffprobe**: Audio metadata extraction
- **Pydantic**: Configuration management

## Performance Considerations

- **Sequential Processing**: Follows single-lane constraint for heavy tasks
- **Idempotent Operations**: Re-running steps skips if outputs exist
- **Temporary File Management**: Automatic cleanup of processing files
- **Memory Efficiency**: Streams audio processing to avoid large memory usage

## Troubleshooting

### Common Issues

1. **No Music Selected**
   - Check music library has tracks with appropriate metadata
   - Verify BPM and mood tags are set correctly
   - Check configuration for music.enabled setting

2. **Audio Quality Issues**
   - Verify ffmpeg installation and version
   - Check audio file formats and bitrates
   - Review ducking and volume settings

3. **Processing Failures**
   - Check temporary directory permissions
   - Verify audio file accessibility
   - Review error logs for specific failure reasons

### Debug Commands

```bash
# Check music library health
python bin/music_manager.py validate

# Test music selection with specific parameters
python bin/music_manager.py test --script scripts/debug.txt --tone energetic

# View detailed library statistics
python bin/music_manager.py stats
```

## Future Enhancements

- **Advanced BPM Detection**: Machine learning-based tempo analysis
- **Mood Classification**: AI-powered mood detection from audio
- **Streaming Integration**: Real-time music selection during live content
- **Multi-Track Support**: Layered music composition
- **Genre Classification**: Automatic genre detection and tagging

## License and Attribution

The music bed policy implementation respects licensing requirements and provides attribution tracking. Users are responsible for:

- Ensuring music tracks have appropriate licenses
- Providing attribution when required by license terms
- Complying with usage restrictions
- Maintaining license documentation

For questions or issues with the music bed policy implementation, refer to the project documentation or create an issue in the project repository.
