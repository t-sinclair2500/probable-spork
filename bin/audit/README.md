# Audit Module

This module contains auditing tools to verify the correct integration and configuration of various pipeline components.

## Viral Wiring Auditor

The `viral_wiring_auditor.py` performs comprehensive verification of viral/shorts/seo module integration across:

### Checks Performed

1. **Pipeline Steps Present & Ordered**
   - Verifies `viral_lab`, `shorts_lab`, `seo_packaging`, `end_screens` steps exist
   - Confirms they execute after `assemble` and before `qa`
   - Validates step required flags (seo_packaging required if enabled)

2. **CLI Flags & Config Gating**
   - Checks `run_pipeline.py` has all required argparse flags
   - Validates `conf/global.yaml` contains viral configuration
   - Ensures effective gating: step runs iff (CLI allows AND config allows)

3. **Configs Exist & Minimal Schema**
   - `conf/viral.yaml`: counts, weights, heuristics, patterns, thumbs
   - `conf/shorts.yaml`: counts, selection, crop, captions, overlays, audio, encoding, filename
   - `conf/seo.yaml`: templates, tags, chapters, cta, end_screen

4. **LLM Hygiene**
   - `conf/models.yaml` has viral.chat_model, viral.timeout_s, viral.seed
   - `bin/viral/hooks.py` and `titles.py` use `ModelRunner.for_task("viral")`
   - Viral scoring wraps LLM calls with safe fallback

5. **Artifacts & Metadata Contract**
   - If `videos/<slug>.metadata.json` exists, validates viral.variants structure
   - Checks for viral.selected.* and shorts files when enabled

6. **Encoder Fallback & CTA Overlay Hooks**
   - Assembler selects `h264_videotoolbox` on macOS, falls back to `libx264`
   - CTA overlay hooks for `assets/generated/<slug>/cta_16x9.mov`

7. **Tooling Health**
   - ffmpeg/ffprobe availability
   - VideoToolbox detection on macOS

### Usage

```bash
# Basic audit (no artifact validation)
python bin/audit/viral_wiring_auditor.py

# Audit with artifact validation for specific slug
python bin/audit/viral_wiring_auditor.py --slug demo-001
```

### Output

- **JSON Report**: `reports/audit/viral_wiring_report.json` - Structured data
- **Markdown Report**: `reports/audit/viral_wiring_report.md` - Human-readable summary
- **Exit Code**: 0 if all required checks pass, non-zero otherwise

### Report Structure

Each check includes:
- `check_id`: Unique identifier for the check
- `status`: PASS, FAIL, WARN, or SKIP
- `details`: Description of what was checked
- `suggest_fix`: Actionable fix suggestion (if applicable)

### Exit Codes

- **0**: All required checks pass
- **1**: One or more critical checks failed

### Integration

The auditor is designed to be run:
- During development to catch integration issues
- Before deployment to ensure viral modules are properly wired
- As part of CI/CD to validate configuration changes
- After pipeline runs to verify artifact contracts



