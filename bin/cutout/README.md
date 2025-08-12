# Color Engine

The Color Engine provides centralized palette operations, WCAG contrast validation, and scene color policy enforcement for the Procedural Animatics Toolkit.

## Features

- **Brand Palette Management**: Load colors from `design/design_language.json`
- **WCAG Compliance**: Automatic contrast ratio checking for accessibility
- **Color Generation**: Deterministic color selection with seeding
- **Tint/Shade Operations**: Create lighter/darker variants using perceptual space
- **Scene Validation**: Enforce color limits and validate scene palettes

## Usage

### Basic Operations

```python
from bin.cutout.color_engine import load_palette, pick_scene_colors

# Load the brand palette
palette = load_palette()
print(f"Available colors: {list(palette.keys())}")

# Pick colors for a scene (deterministic with seed)
colors = pick_scene_colors(seed=42, k=3)
print(f"Scene colors: {colors}")
```

### WCAG Compliance

```python
from bin.cutout.color_engine import contrast_ratio, assert_legible_text

# Check contrast ratio
ratio = contrast_ratio("#1A1A1A", "#FFFFFF")
print(f"Contrast: {ratio:.2f}:1")

# Assert text is legible (raises ValueError if insufficient contrast)
assert_legible_text("#1A1A1A", "#FFFFFF")  # Passes
# assert_legible_text("#FF0000", "#FF0000")  # Fails
```

### Color Variations

```python
from bin.cutout.color_engine import tint, shade

base_color = "#1C4FA1"
lighter = tint(base_color, 0.2)    # 20% lighter
darker = shade(base_color, 0.2)    # 20% darker
```

### Scene Validation

```python
from bin.cutout.color_engine import validate_scene_colors, enforce_scene_palette

# Validate scene colors meet requirements
is_valid = validate_scene_colors(["#F8F1E5", "#1A1A1A"], "my_scene")

# Enforce palette limits
limited_colors = enforce_scene_palette(["#A", "#B", "#C", "#D"], max_k=3)
```

## Configuration

The color engine reads from `conf/global.yaml`:

```yaml
procedural:
  max_colors_per_scene: 3  # Maximum colors per scene
```

## Color Policy

- **Maximum Colors**: Limited to `procedural.max_colors_per_scene` (default: 3)
- **WCAG Standards**: 
  - Normal text: 4.5:1 contrast ratio
  - Large text: 3.0:1 contrast ratio
- **Brand Consistency**: All colors must come from the design language palette

## Technical Details

- **Color Space**: Uses HSL for tint/shade operations
- **Performance**: Includes color conversion caching
- **Deterministic**: Same seed always produces same color selection
- **Error Handling**: Graceful fallbacks with informative error messages
