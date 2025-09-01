# Cutout Module Strategy: Clean First, Then Expand

## Current State Analysis

### What's Actually Working & Used
The cutout module is **actively used** in the pipeline with these core components:

1. **asset_loop** - ✅ **Actively used** in storyboard planning and pipeline
2. **motif_generators** - ✅ **Actively used** in asset generation and animatics
3. **texture_engine** - ✅ **Actively used** in texture probing and effects
4. **qa_gates** - ✅ **Actively used** in acceptance testing and quality checks
5. **layout_engine** - ✅ **Actively used** in animatics generation
6. **color_engine** - ✅ **Actively used** in animatics generation
7. **anim_fx** - ✅ **Actively used** in animatics generation
8. **raster_cache** - ✅ **Actively used** in animatics generation

### What Has Unused Imports (Dead Code)
These modules have unused imports but are **not actively used** in the pipeline:

1. **svg_geom** - ❌ **Not used** in main pipeline (only tested)
2. **svg_path_ops** - ❌ **Not used** in main pipeline (only tested)

## Recommended Strategy: Clean First, Then Expand

### Phase 1: Clean Up (Immediate - 1-2 hours)
**Priority: HIGH** - This will immediately improve code quality and reduce confusion.

#### 1.1 Remove Unused Imports from Working Modules
```python
# bin/cutout/texture_engine.py - Remove 3 unused imports:
# - opensimplex
# - skimage  
# - filters

# bin/cutout/sdk.py - Add noqa comments for 5 unused cls parameters
```

#### 1.2 Remove Unused Imports from Unused Modules
```python
# bin/cutout/svg_geom.py - Remove 8 unused imports:
# - Arc, QuadraticBezier (svgpathtools)
# - SVGElementPath (svgelements)  
# - Point, LineString (shapely)

# bin/cutout/svg_path_ops.py - Remove 7 unused imports:
# - Arc, QuadraticBezier (svgpathtools)
# - SVGElementPath (svgelements)
# - Point, LineString (shapely)
```

#### 1.3 Document Current State
- Add comments explaining what's implemented vs. planned
- Mark unused modules as "experimental" or "future feature"

### Phase 2: Assess Expansion Needs (Before Expanding)
**Priority: MEDIUM** - Understand what's actually needed.

#### 2.1 Evaluate Current Functionality
- **Working modules**: asset_loop, motif_generators, texture_engine, qa_gates
- **These provide**: asset generation, quality checks, layout, effects
- **Missing**: Advanced SVG path operations (svg_geom, svg_path_ops)

#### 2.2 Determine if SVG Operations Are Needed
**Question**: Do we actually need the advanced SVG path operations?

**Current pipeline uses**:
- Basic SVG generation (motif_generators)
- Rasterization (raster_cache)
- Layout and effects (layout_engine, anim_fx)

**Missing**:
- Boolean operations (union, intersection)
- Path morphing and transformations
- Advanced geometric operations

### Phase 3: Strategic Decision (Based on Phase 2)

#### Option A: Remove Unused Modules (Conservative)
If SVG operations aren't needed:
- Remove `svg_geom.py` and `svg_path_ops.py`
- Focus on improving existing working modules
- Reduce complexity and maintenance burden

#### Option B: Complete SVG Operations (Expansion)
If SVG operations are needed:
- Clean up unused imports first
- Implement the missing functionality
- Integrate with existing pipeline

#### Option C: Hybrid Approach (Recommended)
- Keep working modules as-is
- Remove unused imports from unused modules
- Mark unused modules as "experimental" for future use
- Focus on improving existing functionality

## Immediate Action Plan

### Step 1: Clean Up (Today)
1. Remove unused imports from `texture_engine.py`
2. Add noqa comments to `sdk.py` validators
3. Remove unused imports from `svg_geom.py` and `svg_path_ops.py`

### Step 2: Test (Today)
1. Run existing tests to ensure nothing breaks
2. Verify pipeline still works
3. Check that all active modules still function

### Step 3: Document (Today)
1. Add comments explaining current state
2. Mark unused modules appropriately
3. Update documentation

## Recommendation: Clean First

**I recommend we clean up the unused imports first** because:

1. **Low Risk**: Removing unused imports won't break existing functionality
2. **High Impact**: Immediately reduces dead code and improves clarity
3. **Foundation**: Creates a clean base for future decisions
4. **Time Efficient**: Takes 1-2 hours vs. weeks of expansion work

After cleanup, we can better assess whether the SVG operations are actually needed for the pipeline.

## Files to Clean Up

### High Priority (Used in Pipeline)
- `bin/cutout/texture_engine.py` - Remove 3 unused imports
- `bin/cutout/sdk.py` - Add 5 noqa comments

### Medium Priority (Not Used in Pipeline)
- `bin/cutout/svg_geom.py` - Remove 8 unused imports
- `bin/cutout/svg_path_ops.py` - Remove 7 unused imports

### Low Priority (Future Decision)
- Decide whether to keep, expand, or remove unused modules

## Conclusion

The cutout module is **working well** for its current purpose. The unused imports are primarily from experimental features that were never fully implemented. 

**Clean first, then decide on expansion** - this approach minimizes risk while improving code quality.

