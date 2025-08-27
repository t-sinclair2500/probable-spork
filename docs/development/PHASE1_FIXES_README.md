# Phase 1 Fixes Implementation

## Overview

This document describes the implementation of Phase 1 fixes for the acceptance pipeline, addressing critical foundation issues to ensure downstream phases can be trusted.

## Fixes Implemented

### 1. FFmpeg/Audio Extraction Robustness

**Problem**: Audio validation was fragile and could fail silently on codec mismatches or missing streams.

**Solution**: Enhanced `bin/audio_validator.py` with:
- `FFmpegValidator` class for robust FFmpeg/FFprobe validation
- Structured error handling with `AudioValidationError` exceptions
- Graceful fallback to alternative codecs
- Explicit ffprobe validation before processing
- Timeout handling and actionable error messages

**Key Features**:
- Validates FFmpeg and FFprobe installation on startup
- Probes audio streams before processing
- Tries multiple codecs (mp3, aac, wav) with fallback logic
- Provides detailed error information for debugging

**Usage**:
```python
from bin.audio_validator import validate_audio_for_acceptance

result = validate_audio_for_acceptance("audio.mp3", "voiceover")
if not result["valid"]:
    print(f"Audio validation failed: {result['error']}")
    print(f"Error type: {result['error_type']}")
```

### 2. Captions (SRT) Presence + Fallbacks

**Problem**: Missing captions could cause acceptance failures with no recovery mechanism.

**Solution**: Created `bin/srt_generate.py` with:
- Multiple timing sources: ASR → TTS → Heuristic → Pacing
- Intent-based timing profiles from `conf/intent_profiles.yaml`
- Automatic SRT generation when captions are missing
- Validation of generated captions

**Key Features**:
- Prioritizes existing ASR/TTS timings
- Falls back to intent-based heuristic timing
- Groups words into readable captions (max 8 words)
- Ensures minimum caption duration (1 second)

**Usage**:
```python
from bin.srt_generate import generate_srt_for_acceptance

result = generate_srt_for_acceptance(
    script_path="script.txt",
    intent_type="narrative_history"
)
```

### 3. Legibility Defaults + WCAG-AA Contrast Gate

**Problem**: Text overlays could fail accessibility standards with no automatic remediation.

**Solution**: Created `bin/legibility.py` with:
- WCAG-AA contrast ratio validation (4.5:1 threshold)
- Automatic background injection for missing backgrounds
- Safe background color palette from design language
- Detailed contrast analysis and recommendations

**Key Features**:
- Calculates relative luminance using gamma-corrected sRGB
- Finds optimal background colors for given text colors
- Validates entire SceneScripts for legibility
- Provides actionable recommendations for contrast issues

**Usage**:
```python
from bin.legibility import validate_contrast_for_acceptance, inject_safe_background

# Validate existing combination
result = validate_contrast_for_acceptance("#000000", "#FFFFFF", "element_id")

# Inject safe background if needed
result = inject_safe_background("#000000", "element_id")
```

### 4. Duration Policy Enforcement

**Problem**: Hard-coded 3-second defaults and no configurable tolerance for duration validation.

**Solution**: Enhanced duration validation in `bin/acceptance.py`:
- Configurable tolerance from `conf/render.yaml`
- Scene duration bounds enforcement
- Target duration validation against brief specifications
- VO alignment checking when available

**Key Features**:
- Configurable tolerance percentage (default: ±5%)
- Scene duration bounds: 2.5s - 30s
- Supports both brief-based and VO-based timing
- Provides detailed duration analysis and remediation hints

**Configuration**:
```yaml
# conf/render.yaml
acceptance:
  tolerance_pct: 5.0
  min_scene_ms: 2500
  max_scene_ms: 30000
```

### 5. Determinism

**Problem**: Re-running acceptance tests could produce different results.

**Solution**: Added determinism validation to `bin/acceptance.py`:
- Compares key metrics across runs
- Validates SRT consistency for heuristic generation
- Ensures configuration consistency
- Provides detailed difference analysis

**Key Features**:
- Compares overall status, lane statuses, and configuration
- Validates SRT content consistency for generated captions
- Reports specific differences between runs
- Configurable determinism requirements

## Configuration

### New Configuration File: `conf/render.yaml`

The new `render.yaml` configuration file centralizes acceptance pipeline settings:

```yaml
# Audio quality targets and validation
audio:
  vo_lufs_target: -16.0
  music_lufs_target: -23.0
  true_peak_max: -1.0
  ducking_min_db: 6.0
  enable_auto_normalization: true

# Caption requirements and generation
captions:
  require: true
  fallback_generation: true
  timing_priority: ["asr", "tts", "heuristic", "pacing"]

# Acceptance pipeline settings
acceptance:
  tolerance_pct: 5.0
  audio_validation_required: true
  caption_validation_required: true
  legibility_validation_required: true
  wcag_aa_threshold: 4.5
  require_deterministic_runs: true
```

### Enhanced Environment Validation: `bin/check_env.py`

The enhanced environment checker now validates:
- FFmpeg and FFprobe installation and versions
- Required configuration sections in `render.yaml`
- Acceptance pipeline dependencies
- Provides actionable remediation steps

## Testing

### Test Suite: `test_phase1_fixes.py`

A comprehensive test suite validates all Phase 1 fixes:

```bash
python test_phase1_fixes.py
```

Tests cover:
- FFmpeg validation functionality
- SRT generation with fallbacks
- Legibility validation and background injection
- Duration policy configuration
- Acceptance pipeline integration
- Configuration file validation

## Integration

### Enhanced Acceptance Pipeline: `bin/acceptance.py`

The acceptance pipeline now integrates all Phase 1 fixes:

- **Audio Validation**: Uses enhanced FFmpeg-robust validator
- **Caption Validation**: Automatically generates SRT if missing
- **Legibility Validation**: Ensures WCAG-AA compliance
- **Duration Policy**: Enforces configurable tolerance
- **Determinism**: Validates consistent results across runs

### Logging Tags

All new functionality uses consistent logging tags:
- `[audio-accept]` - Audio validation and FFmpeg operations
- `[srt-gen]` - SRT generation and caption validation
- `[legibility-defaults]` - Legibility validation and background injection
- `[duration-policy]` - Duration policy enforcement
- `[acceptance]` - General acceptance pipeline operations

## Success Criteria

### E2E Validation

The implementation satisfies all success criteria:

1. **E2E run on `eames-history` yields acceptance PASS** for:
   - Audio (robust FFmpeg validation)
   - Captions (automatic SRT generation)
   - Legibility (WCAG-AA compliance)
   - Duration (configurable tolerance)

2. **Two identical runs produce identical acceptance metrics** through:
   - Determinism validation
   - SRT consistency checking
   - Configuration validation

3. **No "hard-coded 3s" behavior** - all timing uses:
   - Configurable tolerance from `render.yaml`
   - Brief-based target durations
   - VO alignment when available

### Test Commands

```bash
# Environment validation
make check && python bin/check_env.py

# Acceptance pipeline
python bin/acceptance.py && jq '{audio:.audio, duration:.duration, captions:.captions, legibility:.legibility}' acceptance_results.json

# Phase 1 fixes test suite
python test_phase1_fixes.py
```

## Error Handling

### Graceful Degradation

The implementation provides graceful degradation:

- **Audio failures**: Detailed error messages with remediation steps
- **Missing captions**: Automatic generation with fallback timing
- **Legibility issues**: Background injection and contrast recommendations
- **Duration violations**: Tolerance-based validation with hints
- **Determinism failures**: Detailed difference analysis

### Actionable Messages

All error messages include:
- Error type classification
- Specific failure details
- Remediation steps
- Configuration references

## Future Enhancements

### Potential Improvements

1. **Enhanced ASR Integration**: Better word-level timing extraction
2. **Advanced Contrast Analysis**: Support for complex backgrounds
3. **Performance Monitoring**: Track validation performance over time
4. **Configuration Validation**: Schema validation for render.yaml
5. **Automated Remediation**: Fix common issues automatically

### Monitoring

The implementation provides comprehensive monitoring:
- Detailed validation results
- Performance metrics
- Error categorization
- Determinism tracking

## Conclusion

Phase 1 fixes establish a robust foundation for the acceptance pipeline:

- **Reliability**: FFmpeg robustness prevents silent failures
- **Completeness**: SRT generation ensures captions are always present
- **Accessibility**: WCAG-AA compliance with automatic remediation
- **Flexibility**: Configurable duration policies replace hard-coded defaults
- **Consistency**: Determinism validation ensures reproducible results

These fixes enable downstream phases to trust the acceptance pipeline and focus on higher-level quality improvements.
