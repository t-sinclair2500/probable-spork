# Asset Loop Management

## Overview
The asset loop provides convenient operator commands to run the asset supply chain end-to-end or stepwise, with clear logs and artifacts. It follows a reuse-first policy, preferring existing on-brand assets before generating anything new.

## Quick Start
```bash
# Run complete asset loop for a topic
make asset-loop SLUG=<slug>

# Or run individual steps
make asset-rebuild                    # Rebuild asset library manifest
make asset-plan SLUG=<slug>          # Create asset plan (resolves existing assets)
make asset-fill SLUG=<slug>          # Generate new assets to fill gaps
make asset-reflow SLUG=<slug>        # Reflow storyboard with concrete assets
```

## Individual CLI Commands
```bash
# Rebuild asset manifest
python bin/asset_manifest.py --rebuild

# Resolve assets for a topic
python bin/asset_librarian.py --slug <slug>

# Fill asset gaps
python bin/asset_generator.py --plan runs/<slug>/asset_plan.json

# Reflow storyboard
python bin/reflow_assets.py --slug <slug>
```

## Style Presets & Texture Control

### Quick Preset Selection
Style presets provide operator control over texture parameters without editing configuration files:

```bash
# List available presets
python bin/texture_probe.py --help

# Generate probe grid with specific preset
python bin/texture_probe.py --slug <slug> --preset print-soft
python bin/texture_probe.py --slug <slug> --preset halftone_classic
python bin/texture_probe.py --slug <slug> --preset vintage_paper

# Use base configuration (no preset)
python bin/texture_probe.py --slug <slug>
```

### Available Style Presets
- **print-soft**: Subtle paper grain with minimal posterization
- **print-strong**: Bold paper texture with visible grain and posterization  
- **flat_noise**: Flat design with subtle noise overlay
- **halftone_classic**: Classic halftone dot pattern with moderate grain
- **vintage_paper**: Aged paper feel with heavy grain and posterization
- **minimal**: Clean, minimal texture with subtle edge softening
- **modern_flat**: Modern flat design with minimal texture
- **off**: No texture effects applied

### Texture Probe Tool
The probe tool generates a visual grid showing texture parameter combinations:
- **Input**: Representative test frame with various elements
- **Output**: `runs/<slug>/texture_probe_grid.png` showing grain × posterize × halftone combinations
- **Use case**: Preview texture effects before full render, compare preset styles

### Preset Configuration
Presets are defined in `conf/style_presets.yaml` and can be customized:
- Each preset maps to specific texture parameters
- Presets override base configuration from `conf/global.yaml`
- Changes are logged with preset name and resolved parameters

## Artifacts Generated
Each run creates artifacts under `runs/<slug>/`:
- `asset_plan.json` — resolved assets & gaps list
- `asset_generation_report.json` — new assets with parameters, seeds, palette
- `reflow_summary.json` — bounding boxes before/after, QA results
- `<slug>_reflowed.json` — updated scenescript with concrete assets
- `texture_probe_grid.png` — texture parameter comparison grid (when using probe tool)

## Logging
All commands use structured logging with stage tags:
- `[manifest]` — Asset manifest operations
- `[librarian]` — Asset resolution and planning
- `[generator]` — Asset generation and gap-filling
- `[reflow]` — Storyboard reflow and QA
- `[texture_probe]` — Texture probe and preset operations

## Success Criteria
- **Coverage:** 100% of storyboard placeholders resolved to concrete assets
- **Reuse ratio:** ≥70% of assets are reused when a library exists
- **QA clean:** No collisions after reflow; safe margins respected
- **Metadata:** Video metadata updated with asset coverage information
- **Texture control:** Operators can quickly preview and select texture styles via presets

## Example: Eames Topic with Style Presets
```bash
# Generate probe grid with vintage paper preset
python bin/texture_probe.py --slug eames --preset vintage_paper

# This demonstrates:
# - Style preset resolution and parameter merging
# - Visual texture parameter exploration
# - Preset metadata logging (description, resolved params)
# - Probe grid generation for operator review
```

## Example: Eames Topic
```bash
make asset-loop SLUG=eames
```
This demonstrates:
- 100% asset reuse (5/5 assets resolved from existing library)
- No gaps requiring generation
- All QA checks passing (0 collisions, 0 margin violations)
- Clean artifacts generated in `runs/eames/`
