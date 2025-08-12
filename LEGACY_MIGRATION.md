# Legacy Pipeline Migration Guide

## Overview

This document describes the migration from the legacy stock asset pipeline (Pixabay/Pexels) to the new **Storyboard → SceneScript → Animatics** pipeline. The legacy code has been quarantined behind feature flags to ensure a safe transition.

## Migration Status

- ✅ **COMPLETED**: Legacy code quarantined in `legacy/` directory
- ✅ **COMPLETED**: New `video.animatics_only` configuration flag added
- ✅ **COMPLETED**: Pipeline routing updated to prefer animatics path
- ✅ **COMPLETED**: Acceptance tests enforce animatics-only policy
- ✅ **COMPLETED**: Make targets for easy mode switching

## Configuration Changes

### New Video Pipeline Settings

The following settings have been added to `conf/global.yaml`:

```yaml
video:
  animatics_only: true            # NEW default - skip stock asset downloads
  enable_legacy_stock: false      # Keep legacy stock path disabled by default
  min_coverage: 0.85              # Minimum scene coverage threshold
```

### Legacy Settings Moved

The following settings have been moved from `animatics.animatics_only` to `video.animatics_only`:

```yaml
# OLD (deprecated)
animatics:
  animatics_only: false

# NEW (current)
video:
  animatics_only: true
```

## Pipeline Behavior

### Animatics-Only Mode (Default)

When `video.animatics_only=true` and `video.enable_legacy_stock=false`:

1. **Storyboard Planning**: Generates SceneScript from script
2. **Animatics Generation**: Creates MP4 scenes from SceneScript
3. **Assembly**: Uses animatics as primary video source
4. **No Stock Assets**: Legacy fetch_assets.py becomes a no-op
5. **Coverage Enforcement**: Requires animatics to meet `min_coverage` threshold

### Legacy Mode (Optional)

When `video.animatics_only=false` or `video.enable_legacy_stock=true`:

1. **Stock Asset Fetching**: Downloads from Pixabay/Pexels
2. **Asset Ranking**: Traditional asset selection logic
3. **Assembly**: Uses stock assets with fallback coverage
4. **Optional Animatics**: Can still generate animatics if enabled

## File Structure Changes

### Quarantined Files

The following files have been moved to `legacy/`:

- `legacy/fetch_assets.py` - Original stock asset fetching logic
- `legacy/download_assets.py` - Original asset download utilities

### Shim Files

Thin shim files remain in `bin/` to maintain import compatibility:

- `bin/fetch_assets.py` - Routes to legacy or no-ops based on config
- `bin/download_assets.py` - Routes to legacy or no-ops based on config

### New Pipeline Files

The following files handle the new animatics pipeline:

- `bin/storyboard_plan.py` - Generates SceneScript from script
- `bin/animatics_generate.py` - Creates MP4 scenes from SceneScript

## Make Targets

### Pipeline Mode Management

```bash
# Check current pipeline mode
make pipeline-status

# Switch to animatics-only mode (default)
make animatics-only

# Enable legacy stock asset pipeline
make legacy-on
```

### Testing

```bash
# Test in current mode
make test

# Test with live API calls (requires keys)
make test-live
```

## Acceptance Testing

### Animatics-Only Validation

When `video.animatics_only=true`, acceptance tests enforce:

1. **No Stock Assets**: Must not reference any files with provider metadata
2. **Source Mode**: Video metadata must have `source_mode: "animatics"`
3. **Coverage Threshold**: Must meet `video.min_coverage` requirement
4. **SceneScript**: Must have valid SceneScript JSON
5. **Animatics**: Must have scene MP4 files

### Legacy Mode Validation

When legacy mode is enabled, acceptance tests validate:

1. **Asset Coverage**: Traditional asset pipeline coverage metrics
2. **Source Mode**: Video metadata must have `source_mode: "legacy_stock"`
3. **Asset Quality**: Stock asset relevance and licensing

## Rollback Procedures

### Quick Rollback (Recommended)

```bash
# Enable legacy mode
make legacy-on

# Verify configuration
make pipeline-status
```

### Hard Rollback (Emergency)

```bash
# Restore original files
git mv legacy/fetch_assets.py bin/
git mv legacy/download_assets.py bin/

# Remove shim files
rm bin/fetch_assets.py bin/download_assets.py

# Reset configuration
make legacy-on
```

## Troubleshooting

### Common Issues

1. **"LEGACY DISABLED" warnings**: Normal in animatics-only mode
2. **Missing animatics error**: Ensure storyboard_plan.py and animatics_generate.py run successfully
3. **Coverage threshold failures**: Check animatics generation quality and min_coverage setting

### Debug Commands

```bash
# Check pipeline mode
make pipeline-status

# View current configuration
yq '.video' conf/global.yaml

# Check for legacy warnings in logs
grep -R "LEGACY DISABLED" logs/

# Validate animatics pipeline
python bin/storyboard_plan.py --slug <slug>
python bin/animatics_generate.py --slug <slug>
```

## Migration Checklist

- [x] Legacy code quarantined in `legacy/` directory
- [x] Configuration flags added to `conf/global.yaml`
- [x] Pipeline routing updated in `bin/run_pipeline.py`
- [x] Assembly logic updated in `bin/assemble_video.py`
- [x] Acceptance tests enforce new policy
- [x] Make targets for mode switching
- [x] Documentation updated
- [x] Tests updated for new pipeline modes

## Next Steps

1. **Monitor**: Watch for any issues in animatics-only mode
2. **Optimize**: Fine-tune animatics generation quality
3. **Cleanup**: Remove legacy code after stable operation (optional)
4. **Enhance**: Add more animatics generation features

## Support

For issues or questions about the migration:

1. Check this document first
2. Review logs for "LEGACY DISABLED" messages
3. Verify pipeline mode with `make pipeline-status`
4. Check acceptance test results
5. Review SceneScript and animatics generation logs
