# Audio Acceptance Implementation - Phase 1

## Overview
Successfully implemented audio validation for the acceptance pipeline as required by P1-3_Audio_Acceptance.txt. The implementation measures LUFS, true peak, and ducking effectiveness to ensure audio meets broadcast standards.

## Components Implemented

### 1. Audio Validator (`bin/audio_validator.py`)
- **LUFS Measurement**: Uses ffmpeg loudnorm filter to measure integrated LUFS and range
- **True Peak Measurement**: Uses ffmpeg volumedetect to measure true peak in dBTP
- **Ducking Validation**: Measures audio levels in speech vs non-speech windows
- **Auto-normalization**: One-pass correction if audio is out of spec (configurable)

### 2. Configuration Updates (`conf/global.yaml`)
Added audio quality targets under `render.audio`:
```yaml
audio:
  vo_lufs_target: -16.0      # Voiceover target LUFS
  music_lufs_target: -23.0   # Music bed target LUFS  
  true_peak_max: -1.0        # Maximum true peak in dBTP
  ducking_min_db: 6.0        # Minimum ducking difference in dB
  enable_auto_normalization: true  # Auto-normalize if out of spec
```

### 3. Core Configuration Model (`bin/core.py`)
Added `AudioCfg` Pydantic model to support the new audio configuration section.

### 4. Acceptance Integration (`bin/acceptance.py`)
- Integrated audio validation into YouTube lane validation
- Added `_validate_youtube_audio()` method
- Audio validation runs after quality validation
- Results stored in `youtube_results["quality"]["audio"]`

## Audio Quality Targets

| Metric | Target | Tolerance | Notes |
|--------|--------|-----------|-------|
| Voiceover LUFS | -16.0 LUFS | ±2.0 LUFS | Broadcast standard |
| Music LUFS | -23.0 LUFS | ±3.0 LUFS | Background music |
| True Peak | ≤-1.0 dBTP | None | Prevent clipping |
| Ducking | ≥6.0 dB | None | Speech clarity |

## Validation Process

### 1. Voiceover Validation
- Measures LUFS integrated and range
- Measures true peak
- Validates against targets
- Attempts normalization if out of spec

### 2. Mixed Audio Validation
- Extracts audio from final video
- Measures LUFS and true peak
- Validates overall mix quality

### 3. Ducking Validation
- Detects speech segments using silence detection
- Falls back to continuous speech if no silence detected
- Measures audio levels in speech vs non-speech windows
- Calculates ducking effectiveness

## Test Results

Successfully tested with existing Eames video:

**Voiceover**: PASS ✅
- LUFS: -15.95 (target: -16.0, tolerance: ±2.0)
- True Peak: -12.0 dB (target: ≤-1.0)

**Mixed Audio**: PASS ✅
- LUFS: -16.94 (target: -16.0, tolerance: ±2.0)
- True Peak: -15.7 dB (target: ≤-1.0)

**Ducking**: FAIL (expected for test case)
- Single continuous speech segment (10 seconds)
- No background music to duck

## Technical Details

### FFmpeg Integration
- **LUFS**: `loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json`
- **True Peak**: `volumedetect` filter
- **Speech Detection**: `silencedetect=noise=-50dB:d=0.1`

### Error Handling
- Graceful fallbacks for missing dependencies
- Configurable auto-normalization
- Comprehensive error reporting

### Performance
- Temporary file cleanup
- Efficient audio extraction
- Minimal disk I/O

## Usage

### In Acceptance Pipeline
Audio validation runs automatically during acceptance:
```python
# Audio validation
audio_quality = self._validate_youtube_audio(artifacts)
youtube_results["quality"]["audio"] = audio_quality

# Check audio validity
if not audio_quality.get("valid", False):
    audio_error = audio_quality.get("error", "Audio validation failed")
    youtube_results["status"] = "FAIL"
    youtube_results["quality"]["error"] = f"Audio validation failed: {audio_error}"
    return False
```

### Standalone Usage
```python
from bin.audio_validator import AudioValidator

validator = AudioValidator()
result = validator.validate_audio_file("audio.mp3", "voiceover")
ducking = validator.validate_ducking("mixed.mp3", "voiceover.mp3")
```

## Configuration

Audio validation can be controlled via `conf/global.yaml`:
- Enable/disable auto-normalization
- Adjust LUFS targets
- Modify ducking thresholds
- Set true peak limits

## Success Criteria Met ✅

1. **LUFS/peak measurement routine**: ✅ Implemented with ffmpeg integration
2. **Ducking validator**: ✅ Implemented with speech detection and level analysis  
3. **Acceptance hooks**: ✅ Integrated into acceptance.py validation pipeline
4. **One-pass corrective normalization**: ✅ Implemented with configurable fallback
5. **Metrics recording**: ✅ Stored in acceptance results under `quality.audio`

## Operator Notes

The audio validation system provides comprehensive quality assurance for broadcast-ready content:

- **Automatic**: Runs during acceptance without operator intervention
- **Configurable**: Targets and tolerances can be adjusted in `conf/global.yaml`
- **Informative**: Detailed metrics and validation results for troubleshooting
- **Corrective**: Auto-normalization attempts to fix out-of-spec audio
- **Reliable**: Graceful handling of edge cases and missing dependencies

Audio validation is now a core component of the acceptance pipeline, ensuring all videos meet professional audio standards before publication.
