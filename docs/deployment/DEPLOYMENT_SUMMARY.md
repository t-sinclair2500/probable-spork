# Legacy Pipeline Decommission - Deployment Summary

## Overview

Successfully decommissioned the legacy stock B-roll pipeline (Pixabay/Pexels) and prepared the repository for the new **Storyboard → SceneScript → Animatics** pipeline. The legacy code has been quarantined behind feature flags to ensure a safe transition.

## What Was Accomplished

### 1. Legacy Code Quarantine ✅

- **Moved to `legacy/` directory:**
  - `bin/fetch_assets.py` → `legacy/fetch_assets.py`
  - `bin/download_assets.py` → `legacy/download_assets.py`

- **Created thin shims in `bin/`:**
  - `bin/fetch_assets.py` - Routes to legacy or no-ops based on config
  - `bin/download_assets.py` - Routes to legacy or no-ops based on config

### 2. Configuration Updates ✅

- **Added new video pipeline settings to `conf/global.yaml`:**
  ```yaml
  video:
    animatics_only: true            # NEW default - skip stock asset downloads
    enable_legacy_stock: false      # Keep legacy stock path disabled by default
    min_coverage: 0.85              # Minimum scene coverage threshold
  ```

- **Moved legacy settings:**
  - `animatics.animatics_only` → `video.animatics_only`

### 3. Pipeline Orchestration ✅

- **Updated `bin/run_pipeline.py`:**
  - Routes between animatics-only and legacy paths based on config
  - Logs pipeline mode for state tracking
  - Maintains backward compatibility

### 4. Video Assembly Updates ✅

- **Updated `bin/assemble_video.py`:**
  - Prefers animatics as primary video source
  - Enforces animatics-only policy when configured
  - Adds `source_mode` to video metadata
  - Fails gracefully if animatics missing in animatics-only mode

### 5. Acceptance Testing ✅

- **Updated `bin/acceptance.py`:**
  - Enforces animatics-only policy when enabled
  - Validates `source_mode` in video metadata
  - Checks coverage thresholds
  - Prevents stock assets in animatics-only mode

### 6. Make Targets ✅

- **Added new targets to `Makefile`:**
  ```bash
  make animatics-only    # Switch to animatics-only mode (default)
  make legacy-on         # Enable legacy stock asset pipeline
  make pipeline-status   # Check current pipeline configuration
  ```

### 7. Test Updates ✅

- **Updated `bin/test_e2e.py`:**
  - Handles both pipeline modes
  - Skips asset fetching in animatics-only mode
  - Maintains backward compatibility

### 8. Documentation ✅

- **Created `LEGACY_MIGRATION.md`:**
  - Complete migration guide
  - Configuration changes
  - Rollback procedures
  - Troubleshooting guide

- **Updated `docs/operational/OPERATOR_RUNBOOK.md`:**
  - Pipeline mode management
  - Mode differences
  - Quick reference commands

## Current State

### Pipeline Mode: ANIMATICS-ONLY (Default)

- ✅ Legacy code quarantined and accessible via shims
- ✅ New configuration flags active
- ✅ Pipeline routes to animatics path by default
- ✅ Acceptance tests enforce new policy
- ✅ Rollback ready via `make legacy-on`

### File Structure

```
probable-spork/
├── bin/
│   ├── fetch_assets.py          # Shim (routes to legacy or no-ops)
│   ├── download_assets.py       # Shim (routes to legacy or no-ops)
│   ├── storyboard_plan.py       # New: generates SceneScript
│   ├── animatics_generate.py    # New: creates MP4 scenes
│   └── ...
├── legacy/                       # NEW: quarantined legacy code
│   ├── fetch_assets.py          # Original stock asset logic
│   └── download_assets.py       # Original download utilities
└── conf/
    └── global.yaml              # Updated with video pipeline flags
```

## Verification Commands

### Check Configuration
```bash
# View current video pipeline settings
grep -A 5 "video:" conf/global.yaml

# Check pipeline mode
make pipeline-status  # (requires yq)
```

### Test Legacy Shims
```bash
# Should log "LEGACY DISABLED" in animatics-only mode
python3 bin/fetch_assets.py --help

# Check logs for legacy warnings
grep -R "LEGACY DISABLED" logs/
```

### Pipeline Execution
```bash
# Run in current mode (animatics-only by default)
python3 bin/run_pipeline.py --dry-run --from-step llm_script

# Switch to legacy mode if needed
make legacy-on
```

## Rollback Procedures

### Quick Rollback (Recommended)
```bash
make legacy-on
```

### Hard Rollback (Emergency)
```bash
# Restore original files
git mv legacy/fetch_assets.py bin/
git mv legacy/download_assets.py bin/

# Remove shims
rm bin/fetch_assets.py bin/download_assets.py

# Reset configuration
make legacy-on
```

## Next Steps

1. **Monitor**: Watch for any issues in animatics-only mode
2. **Test**: Run acceptance tests to ensure policy enforcement
3. **Optimize**: Fine-tune animatics generation quality
4. **Cleanup**: Remove legacy code after stable operation (optional)

## Success Criteria Met

- ✅ **Policy in effect**: Animatics-only mode is the default; legacy calls are harmless no-ops
- ✅ **Pipeline composes**: Storyboard → Animatics generate → Assemble routing implemented
- ✅ **Acceptance enforces**: Fails if any legacy asset slips in while `animatics_only=true`
- ✅ **Rollback ready**: One Make target flips legacy back on

## Files Modified

- `conf/global.yaml` - Added video pipeline configuration
- `bin/run_pipeline.py` - Updated pipeline routing logic
- `bin/assemble_video.py` - Added animatics-only policy enforcement
- `bin/acceptance.py` - Updated validation for new policy
- `bin/test_e2e.py` - Added pipeline mode handling
- `Makefile` - Added pipeline mode management targets
- `bin/fetch_assets.py` - Replaced with shim
- `bin/download_assets.py` - Replaced with shim

## Files Created

- `legacy/fetch_assets.py` - Quarantined original
- `legacy/download_assets.py` - Quarantined original
- `LEGACY_MIGRATION.md` - Migration guide
- `DEPLOYMENT_SUMMARY.md` - This summary

## Files Moved

- `bin/fetch_assets.py` → `legacy/fetch_assets.py`
- `bin/download_assets.py` → `legacy/download_assets.py`

The migration is complete and the repository is now ready for the new animatics pipeline while maintaining full backward compatibility through the legacy toggle system.
