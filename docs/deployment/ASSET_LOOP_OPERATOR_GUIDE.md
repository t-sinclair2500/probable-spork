# Asset Loop Operator Guide

This guide explains how to use the asset loop management system for the procedural animatics pipeline.

## Overview

The asset loop system manages the complete lifecycle of visual assets:
1. **Manifest** - Index and catalog all available SVG assets
2. **Planning** - Analyze storyboard requirements and identify gaps
3. **Generation** - Fill gaps with procedurally generated assets
4. **Reflow** - Adjust layouts to prevent collisions and maintain quality

## Quick Start

### Complete Asset Loop
```bash
# Run the complete asset loop for a specific topic
make asset-loop SLUG=eames-history
```

This single command runs all four phases in sequence.

### Step-by-Step Execution
```bash
# 1. Rebuild the asset manifest (indexes all SVG files)
make asset-rebuild

# 2. Create asset plan for a specific topic
make asset-plan SLUG=eames-history

# 3. Fill identified gaps with generated assets
make asset-fill SLUG=eames-history

# 4. Reflow assets to prevent collisions
make asset-reflow SLUG=eames-history
```

## Individual Commands

### Asset Manifest Management
```bash
# Rebuild the complete asset library manifest
make asset-rebuild

# Or use the CLI directly
python3 bin/asset_manifest.py --rebuild

# View manifest summary
python3 bin/asset_manifest.py --summary

# Check for palette violations
python3 bin/asset_manifest.py --rebuild --filter palette-only
```

### Asset Planning
```bash
# Create asset plan for a specific topic
make asset-plan SLUG=<topic-slug>

# The plan is saved to: runs/<slug>/asset_plan.json
```

### Asset Generation
```bash
# Fill asset gaps based on the plan
make asset-fill SLUG=<topic-slug>

# Generated assets are saved to: assets/generated/
# Generation report: runs/<slug>/asset_generation_report.json
```

### Asset Reflow
```bash
# Adjust layouts to prevent collisions
make asset-reflow SLUG=<topic-slug>

# Reflow summary: runs/<slug>/reflow_summary.json
```

## Output Artifacts

Each phase generates specific artifacts in the `runs/<slug>/` directory:

- **`asset_plan.json`** - Resolved assets and identified gaps
- **`asset_generation_report.json`** - New assets with parameters and seeds
- **`reflow_summary.json`** - Layout adjustments and collision resolution

## Configuration

The asset loop system respects these configuration files:
- `conf/modules.yaml` - Asset policy and generation thresholds
- `conf/render.yaml` - Procedural seed and safe margins
- `design/design_language.json` - Palette and design constraints

## Troubleshooting

### Common Issues

1. **Thumbnail Generation Fails**
   - Install ImageMagick: `brew install imagemagick` (macOS) or `apt install imagemagick` (Ubuntu)
   - Or install rsvg-convert: `brew install librsvg` (macOS) or `apt install librsvg2-bin` (Ubuntu)

2. **Palette Violations**
   - Check `data/library_manifest.json` for violations
   - Review `design/design_language.json` for allowed colors
   - Regenerate assets with compliant palette

3. **Asset Not Found**
   - Run `make asset-rebuild` to refresh the manifest
   - Check that assets exist in expected directories

### Logs and Debugging

- Use `--verbose` flag for detailed logging: `python3 bin/asset_manifest.py --rebuild --verbose`
- Check `logs/` directory for detailed execution logs
- Review `jobs/state.jsonl` for pipeline execution history

## Integration with Pipeline

The asset loop integrates with the main pipeline:
- Assets are automatically selected during storyboard generation
- Generated assets are tracked in the manifest
- Usage counts are updated after each pipeline run

## Best Practices

1. **Run manifest rebuild** before starting new topics
2. **Review asset plans** to understand what will be generated
3. **Check palette compliance** regularly
4. **Use deterministic seeds** for reproducible results
5. **Monitor asset reuse ratios** for efficiency

## Examples

### Eames History Topic
```bash
# Complete asset loop for Eames topic
make asset-loop SLUG=eames-history

# Check results
jq '.gaps | length' runs/eames-history/asset_plan.json
jq '.assets | length' runs/eames-history/asset_generation_report.json
```

### Custom Topic
```bash
# For a custom topic "productivity-tips"
make asset-loop SLUG=productivity-tips
```

## Support

For issues or questions:
1. Check the logs for error messages
2. Review the generated artifacts for clues
3. Verify configuration files are correct
4. Ensure all dependencies are installed
