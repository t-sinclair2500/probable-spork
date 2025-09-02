# Quality Gates (Acceptance Harness)

A comprehensive quality assurance system that verifies content meets monetization-grade standards before publishing.

## Overview

The Quality Gates system provides end-to-end QA checks for:
- **Script**: WPM, CTA presence, banned tokens
- **Audio**: LUFS/LRA/True Peak, silence percentage, sibilance
- **Visuals**: Contrast ratios, safe areas, scene duration tolerance
- **Video Master**: Codec/profile compliance, technical specifications
- **Research**: Citation requirements, fact-guard status
- **Monetization**: Disclosure compliance, UTM tracking, link limits

## Quick Start

```bash
# Run QA gates for a content slug
python3 bin/qa/run_gates.py --slug your-content-slug

# Strict mode (treat WARN as blocking)
python3 bin/qa/run_gates.py --slug your-content-slug --strict

# Test with sample data
python3 bin/qa/test_demo.py
```

## Configuration

Edit `conf/qa.yaml` to customize thresholds and policy:

```yaml
policy:
  required_gates: ["script", "audio", "visuals", "video_master", "research", "monetization"]
  warn_gates: []
  block_on_warn: false

thresholds:
  script:
    wpm_min: 145
    wpm_max: 175
    require_cta: true
    ban_tokens: ["[CITATION NEEDED]"]
  
  audio:
    lufs_target: -14.0
    lufs_tolerance: 0.5
    truepeak_max_db: -1.5
    lra_max: 11.0
    silence_max_pct: 4.0
```

## Exit Codes

- `0`: All required gates PASS
- `1`: Any required gate FAILs (blocking)
- `2`: WARN-only blocking enabled and encountered

## Reports

QA reports are generated in:
- `reports/<slug>/qa_report.json` - Structured data
- `reports/<slug>/qa_report.txt` - Human-readable summary
- `logs/qa/<slug>/*.log` - Detailed logs

## Integration

The QA gates are automatically integrated into the pipeline:

1. **YouTube Lane**: Runs after `assemble_video` and before `upload_stage`
2. **Pipeline Blocking**: Prevents upload if QA fails (configurable)
3. **Idempotent**: Re-runs skip if outputs already exist

## Gate Details

### Script Gate
- **WPM**: 145-175 words per minute
- **CTA**: Must contain call-to-action phrases
- **Banned Tokens**: Blocks `[CITATION NEEDED]` and other placeholders

### Audio Gate
- **LUFS**: -14 ±0.5 LUFS (broadcast standard)
- **True Peak**: ≤ -1.5 dBTP
- **LRA**: ≤ 11 LU (loudness range)
- **Silence**: ≤ 4% of total duration
- **Sibilance**: Proxy measurement via RMS

### Visuals Gate
- **Contrast**: ≥ 4.5:1 ratio (WCAG AA)
- **Safe Areas**: Text within 90% of frame
- **Scene Duration**: ±3% tolerance vs planned timing

### Video Master Gate
- **Codec**: H.264 High Profile or ProRes 422
- **Pixel Format**: yuv420p for H.264
- **Audio**: AAC 320 kbps @ 48 kHz

### Research Gate
- **Citations**: Minimum 1 citation per factual beat
- **Fact Guard**: Blocks on unresolved items (configurable)

### Monetization Gate
- **Disclosure**: Must contain #ad, affiliate, sponsored, etc.
- **UTM Tracking**: All links must have utm_source and utm_medium
- **Link Limits**: Maximum 20 links (configurable)

## Development

### Running Tests
```bash
python3 -m pytest tests/test_quality_gates.py -v
```

### Adding New Gates
1. Create measurement module in `bin/qa/measure_*.py`
2. Add gate to `evaluate_all()` in `bin/qa/run_gates.py`
3. Update `conf/qa.yaml` with thresholds
4. Add tests in `tests/test_quality_gates.py`

### Dependencies
- **ffmpeg/ffprobe**: Audio/video analysis
- **Python**: Core logic and file processing
- **No heavy deps**: Uses system tools where possible

## Troubleshooting

### Common Issues

1. **Missing ffmpeg**: Install via package manager
2. **Import errors**: Ensure running from repo root
3. **File not found**: Check artifact paths in `bin/contracts/paths.py`

### Debug Mode
```bash
# Verbose logging
python3 bin/qa/run_gates.py --slug test --strict 2>&1 | tee qa_debug.log
```

## License

Part of the probable-spork content generation pipeline.
