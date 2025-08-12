# Layout Engine

The Layout Engine provides deterministic, art-directed layout utilities for the Procedural Animatics Toolkit. It ensures scenes avoid collisions, respect safe margins, and feel intentionally composed.

## Features

- **Deterministic layouts** with configurable seeds
- **Poisson-disk sampling** for natural element distribution
- **Rule-of-thirds grid** for composition guidance
- **Collision-free placement** with overlap resolution
- **Text block packing** with skyline algorithm
- **Constraint system** for layout rules

## Usage

### Basic Functions

```python
from bin.cutout.layout_engine import (
    poisson_points, thirds_grid, place_non_overlapping,
    pack_text_blocks, apply_constraints
)

# Generate Poisson-disk distributed points
points = poisson_points(1280, 720, r=64, seed=42)

# Get rule-of-thirds grid
thirds = thirds_grid(1280, 720)
# Returns: {'T1': (426, 240), 'T2': (853, 240), 'T3': (426, 480), 'T4': (853, 480)}

# Pack text blocks efficiently
blocks = [
    {'w': 320, 'h': 120, 'id': 'title'},
    {'w': 280, 'h': 120, 'id': 'subtitle'}
]
packed = pack_text_blocks(blocks)
```

### Advanced Usage

```python
from bin.cutout.layout_engine import LayoutEngine

# Create engine instance with seed
engine = LayoutEngine(seed=42)

# Apply layout constraints
items = [
    {'id': 'title', 'x': 100, 'y': 100, 'w': 200, 'h': 80},
    {'id': 'subtitle', 'x': 100, 'y': 200, 'w': 150, 'h': 60}
]

constraints = [
    {'type': 'align', 'target': 'T1', 'ids': ['title']},
    {'type': 'distribute_horizontal', 'ids': ['title', 'subtitle']}
]

result = engine.apply_constraints(items, constraints)
```

## Configuration

Layout behavior can be configured in `conf/modules.yaml`:

```yaml
procedural:
  seed: 42  # Default seed for deterministic layouts
  enable_jitter: true  # Allow slight position variations

layout:
  poisson:
    k_attempts: 30  # Maximum attempts for Poisson sampling
    min_spacing: 64  # Minimum distance between points
  packing:
    algorithm: "skyline"  # Packing algorithm
    max_iterations: 1000  # Max iterations for overlap resolution
```

## Performance

- **Poisson sampling**: O(n) where n is the number of points
- **Text packing**: O(n log n) for ≤20 blocks, completes in <50ms
- **Constraint application**: O(n × c) where c is constraint count

## Constraints

Supported constraint types:

- `keep_inside`: Ensure items stay within safe margins
- `align`: Align items to rule-of-thirds points (T1, T2, T3, T4)
- `distribute_horizontal`: Evenly distribute items horizontally
- `distribute_vertical`: Evenly distribute items vertically

## Safe Margins

All layouts respect `SAFE_MARGINS_PX` from the SDK (default: 64px) to ensure elements don't get cut off at screen edges.
