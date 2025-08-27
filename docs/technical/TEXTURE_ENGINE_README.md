# Texture Engine for Mid-Century Modern Print Aesthetics

## Overview

The Texture Engine adds authentic mid-century modern print aesthetics to the animation pipeline, including organic grain, edge treatment, and halftone effects. This system ensures all SVG and rasterized elements have consistent, subtle texture overlays that enhance the vintage aesthetic without obscuring design details.

## Features

### 🎨 **Texture Types**
- **Organic Grain**: Opensimplex/Perlin noise for natural paper texture
- **Edge Treatment**: Feathering and posterization for period-accurate printing
- **Halftone Effects**: Dot patterns simulating vintage printing techniques
- **Color Preservation**: Maintains brand palette integrity

### ⚙️ **Configuration**
- **Session-based**: New textures generated per render session
- **Caching**: Intelligent texture caching for performance
- **Parameterized**: Fully configurable via YAML settings
- **Fallbacks**: Graceful degradation when optional dependencies unavailable

### 🔧 **Technical Implementation**
- **Pillow Integration**: Seamless integration with existing image pipeline
- **Memory Efficient**: Generates textures on-demand
- **Cross-platform**: Works on Raspberry Pi 5 and development machines
- **Backward Compatible**: Existing pipeline continues to work unchanged

## Installation

### Dependencies

Add these to your `requirements.txt`:

```txt
# Texture and paper feel processing
opensimplex==0.4.3
scikit-image==0.22.0; python_version < "3.12"
```

### Install Dependencies

```bash
pip install opensimplex scikit-image
```

**Note**: `scikit-image` is Python version dependent. For Python 3.12+, use alternative edge detection methods.

## Configuration

### Global Configuration

Add texture settings to `conf/global.yaml`:

```yaml
# Texture and paper feel settings
textures:
  enabled: true                    # Enable/disable texture overlay
  cache_dir: "render_cache/textures"  # Texture cache directory
  session_based: true              # Generate new textures per render session
  
  # Noise settings
  grain:
    density: 0.15                  # Grain density (0.0-1.0)
    scale: 2.0                     # Noise scale factor
    intensity: 0.08                # Grain intensity (0.0-1.0)
    seed_variation: true           # Vary seed per session
  
  # Edge treatment
  edges:
    feather_radius: 1.5            # Edge feathering radius in pixels
    posterization_levels: 8        # Number of posterization levels (2-16)
    edge_strength: 0.3             # Edge detection strength (0.0-1.0)
  
  # Halftone effect
  halftone:
    enabled: true                  # Enable halftone dot pattern
    dot_size: 1.2                  # Halftone dot size in pixels
    dot_spacing: 3.0               # Spacing between dots
    angle: 45                      # Halftone angle in degrees
    intensity: 0.12                # Halftone effect intensity (0.0-1.0)
  
  # Color constraints
  color_preservation: true         # Ensure textures don't introduce new colors
  brand_palette_only: true         # Use only brand palette colors for textures
```

### Configuration Parameters

#### Grain Settings
- **density**: Controls how much of the image is affected by grain
- **scale**: Determines the size of noise patterns
- **intensity**: How strong the grain effect appears
- **seed_variation**: Whether to use different seeds per session

#### Edge Settings
- **feather_radius**: Softens edges for vintage feel
- **posterization_levels**: Reduces color depth for retro look
- **edge_strength**: How prominent edge detection appears

#### Halftone Settings
- **enabled**: Toggle halftone dot patterns
- **dot_size**: Size of halftone dots
- **dot_spacing**: Distance between dots
- **angle**: Rotation angle of halftone pattern
- **intensity**: How visible the halftone effect is

## Usage

### Basic Usage

The texture engine automatically integrates with the existing pipeline:

```python
from bin.cutout.texture_engine import create_texture_engine

# Load configuration
config = load_config()
texture_config = config.textures

# Create texture engine
engine = create_texture_engine(texture_config, brand_palette)

# Apply texture to image
textured_image = engine.apply_texture_overlay(original_image)
```

### Advanced Usage

```python
# Generate specific texture types
noise_texture = engine.generate_noise_texture(800, 600)
halftone_texture = engine.generate_halftone_texture(800, 600)
edge_texture = engine.apply_edge_treatment(original_image)

# Process multiple images
image_paths = ["image1.png", "image2.png", "image3.png"]
processed_paths = engine.process_image_batch(image_paths, "output_dir")

# Clean up cache
engine.cleanup_cache()
```

### Integration with Rasterization

The texture engine automatically integrates with SVG rasterization:

```python
# Existing code continues to work
raster_path = rasterize_svg("element.svg", 400, 300)

# Textures are automatically applied if enabled in config
# No code changes required
```

## Testing

### Run Test Suite

```bash
python test_texture_engine.py
```

This tests:
- Configuration loading
- Texture engine functionality
- Integration with rasterization pipeline
- Caching system

### Run Demonstration

```bash
python demo_texture_effects.py
```

This creates:
- Sample images with different texture configurations
- Before/after comparisons
- Texture effect variations

## Performance Considerations

### Caching Strategy
- **Session-based**: New textures per render session for variety
- **Dimension-aware**: Separate cache entries for different sizes
- **Config-aware**: Different cache keys for different settings

### Memory Usage
- Textures generated on-demand
- Automatic cleanup of old cache files
- Efficient numpy operations for large images

### Raspberry Pi 5 Optimization
- Minimal memory footprint
- Efficient fallbacks when optional libraries unavailable
- Configurable quality vs. performance trade-offs

## Troubleshooting

### Common Issues

#### Texture Engine Not Available
```
✗ Failed to import texture engine: No module named 'opensimplex'
```
**Solution**: Install required dependencies
```bash
pip install opensimplex scikit-image
```

#### Scikit-image Import Error (Python 3.12+)
```
✗ Failed to import scikit-image: No module named 'skimage'
```
**Solution**: Use Pillow fallback methods or upgrade to Python 3.11

#### Memory Issues on Pi
```
✗ Out of memory during texture generation
```
**Solution**: Reduce texture resolution or disable some effects
```yaml
textures:
  grain:
    intensity: 0.05  # Reduce from 0.08
  halftone:
    enabled: false   # Disable halftone
```

### Debug Mode

Enable verbose logging:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Cache Management

Clear texture cache if issues arise:

```python
from bin.cutout.texture_engine import create_texture_engine
engine = create_texture_engine(config.textures)
engine.cleanup_cache()
```

## Examples

### Subtle Grain Effect
```yaml
textures:
  enabled: true
  grain:
    density: 0.1
    intensity: 0.05
  halftone:
    enabled: false
  edges:
    edge_strength: 0.1
```

### Strong Vintage Look
```yaml
textures:
  enabled: true
  grain:
    density: 0.2
    intensity: 0.12
  halftone:
    enabled: true
    intensity: 0.15
    dot_size: 1.5
  edges:
    edge_strength: 0.4
    posterization_levels: 6
```

### Disabled Textures
```yaml
textures:
  enabled: false
```

## Architecture

### Core Components

1. **TextureEngine**: Main texture generation and application class
2. **Texture Integration**: Integration layer for rasterization pipeline
3. **Configuration**: Pydantic models for type-safe configuration
4. **Caching**: Session-based texture caching system

### Data Flow

```
SVG Input → Rasterization → Texture Engine → Textured Output
                ↓
        Check Cache → Generate → Apply → Cache
```

### Dependencies

- **Required**: Pillow, numpy
- **Optional**: opensimplex (better noise), scikit-image (better edges)
- **Fallbacks**: Built-in alternatives when optional deps unavailable

## Contributing

### Adding New Texture Types

1. Extend `TextureEngine` class with new method
2. Add configuration parameters to YAML schema
3. Update configuration classes in `bin/core.py`
4. Add tests and documentation

### Performance Improvements

- Profile texture generation bottlenecks
- Optimize numpy operations for Pi 5
- Implement texture pre-generation for common sizes

## License

This texture engine is part of the probable-spork project and follows the same licensing terms.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review configuration examples
3. Run the test suite to verify installation
4. Check logs for detailed error messages
