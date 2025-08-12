# NAMING CONVENTIONS AND GLOSSARY

## CANONICAL TERMS (ALWAYS USE THESE)

### Core Concepts
- **SceneScript**: The complete specification file for an animatic (.scenescript.json)
- **Element**: A visual component within a scene (text, prop, character, etc.)
- **Keyframe**: A point in time defining element properties (position, scale, opacity)
- **BrandStyle**: Configuration for consistent visual identity
- **Beat**: A narrative unit or timing marker
- **Animatic Clip**: The final rendered video output

### Element Types
- **text**: Text-based content (headlines, body copy, captions)
- **prop**: Visual objects or graphics
- **character**: Person or avatar representations
- **list_step**: Numbered or bulleted list items
- **shape**: Geometric shapes (rectangles, circles, etc.)
- **lower_third**: Information graphics at bottom of screen
- **counter**: Numeric displays (timers, statistics)

### Animation Types
- **fade_in**: Element appears with increasing opacity
- **fade_out**: Element disappears with decreasing opacity
- **slide_left**: Element moves from right to left
- **slide_right**: Element moves from left to right
- **slide_up**: Element moves from bottom to top
- **slide_down**: Element moves from top to bottom
- **pop**: Element scales up then down for emphasis
- **slow_zoom**: Gradual scale increase over time
- **slow_pan**: Gradual position change over time

## FORBIDDEN ALIASES (NEVER USE THESE)

### Common Mistakes
- ❌ "pecent" instead of "percentage"
- ❌ "percentages" instead of "percentage"
- ❌ "scene" instead of "Scene" (when referring to the class)
- ❌ "element" instead of "Element" (when referring to the class)
- ❌ "keyframe" instead of "Keyframe" (when referring to the class)
- ❌ "animation" instead of "AnimType"
- ❌ "transition" instead of specific AnimType values
- ❌ "style" instead of "BrandStyle"
- ❌ "brand" instead of "BrandStyle"

### Path Naming
- ❌ "script_dir" instead of "slug_root"
- ❌ "animatics_folder" instead of "anim_dir"
- ❌ "script_file" instead of "scene_script"
- ❌ "style_file" instead of "brand_style"

### Constants
- ❌ "WIDTH" instead of "VIDEO_W"
- ❌ "HEIGHT" instead of "VIDEO_H"
- ❌ "FRAME_RATE" instead of "FPS"
- ❌ "MARGINS" instead of "SAFE_MARGINS_PX"
- ❌ "MAX_WORDS" instead of "MAX_WORDS_PER_CARD"
- ❌ "LINE_SPACING" instead of "LINE_HEIGHT"

## IMPORT STATEMENTS

### Correct
```python
from bin.cutout.sdk import (
    VIDEO_W, VIDEO_H, FPS, SAFE_MARGINS_PX,
    AnimType, Paths, BrandStyle, Keyframe, Element, Scene, SceneScript
)
```

### Incorrect
```python
# Don't import individual constants from other modules
from bin.core import BASE  # ❌
from moviepy.editor import VideoFileClip  # ❌ (unless specifically needed)

# Don't create local aliases
VIDEO_WIDTH = 1280  # ❌
FRAME_RATE = 30     # ❌
```

## FILE NAMING

### SceneScript Files
- Format: `{slug}.scenescript.json`
- Example: `google-business-profile.scenescript.json`
- Location: `scripts/{slug}/`

### Brand Style Files
- Format: `style.yaml`
- Location: `assets/brand/`
- Example: `assets/brand/style.yaml`

### Animatics Output
- Format: `{slug}_animatics/`
- Location: `assets/`
- Example: `assets/google-business-profile_animatics/`

## VALIDATION RULES

### SceneScript Validation
- Must have exactly these top-level keys: `slug`, `fps`, `scenes`
- `scenes` array must have at least one scene
- Each scene must have: `id`, `duration_ms`, `elements`
- Element types must match the canonical enum exactly

### Brand Style Validation
- Must include all required font sizes: `hook`, `body`, `lower_third`
- Colors must be valid hex codes or CSS color names
- Numeric values must be positive integers

## EXAMPLES

### Good SceneScript Structure
```json
{
  "slug": "demo",
  "fps": 30,
  "scenes": [
    {
      "id": "intro",
      "duration_ms": 3000,
      "elements": [
        {
          "id": "title",
          "type": "text",
          "content": "Welcome",
          "x": 640,
          "y": 360
        }
      ]
    }
  ]
}
```

### Good Brand Style Usage
```python
from bin.cutout.sdk import load_style, BrandStyle

style = load_style()
primary_color = style.colors["primary"]
hook_size = style.font_sizes["hook"]
```

## ENFORCEMENT

- All new code must import from `bin.cutout.sdk`
- CI/CD will validate naming conventions
- Code reviews must check for forbidden aliases
- Automated tests verify canonical term usage
- Documentation must use exact terms from this glossary
