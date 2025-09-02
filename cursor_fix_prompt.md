# Code Quality Fix Prompt for Cursor Agent

## Think
You are tasked with fixing critical code quality issues in a Python codebase. The analysis shows:
- 1 syntax error (f-string with backslash in Python 3.9)
- Multiple undefined names causing import errors
- 209 linting errors including unused variables and import organization issues
- Dead code detected by vulture

The codebase follows specific patterns:
- Uses `bin.core` for shared functionality
- Has a virtual environment setup
- Follows PEP 8 standards
- Uses logging instead of print statements
- Requires idempotent operations

## Plan
**Phase 1: Fix Critical Issues (Runtime Failures)**
1. Fix f-string syntax error in `bin/viral/shorts.py:98`
2. Add missing imports for undefined names:
   - `_read_yaml` in multiple files
   - `Path` in `bin/tts_generate.py`
   - `time` in `bin/voice_cues.py`
   - `validate_scenescript` in `bin/test_integration.py`
3. Fix bare except clauses (E722 errors)

**Phase 2: Clean Up Imports**
1. Move all imports to top of files (E402 errors)
2. Remove unused imports detected by vulture
3. Fix import redefinitions (F811 errors)
4. Add missing imports for undefined names

**Phase 3: Remove Dead Code**
1. Remove unused variables (F841 errors)
2. Remove unused functions and classes
3. Clean up unused imports in cutout modules

## Apply

### Phase 1: Critical Fixes

**Fix f-string syntax error:**
```python
# In bin/viral/shorts.py line 98, replace:
f"[v2]subtitles='{ass_path.as_posix().replace(':','\\:')}'"
# With:
f"[v2]subtitles='{ass_path.as_posix().replace(':','\\\\:')}'"
```

**Add missing imports:**
```python
# In files missing _read_yaml:
from bin.utils.config import _read_yaml

# In bin/tts_generate.py:
from pathlib import Path

# In bin/voice_cues.py:
import time

# In bin/test_integration.py:
from bin.cutout.sdk import validate_scene_script as validate_scenescript
```

**Fix bare except clauses:**
```python
# Replace bare except: with specific exceptions:
try:
    # code
except Exception as e:
    # handle specific exception
```

### Phase 2: Import Cleanup

**Standard import order:**
```python
# Standard library imports
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Third-party imports
import requests
from PIL import Image, ImageDraw, ImageFont

# Local imports
from bin.core import get_logger, load_config
from bin.utils.config import _read_yaml
```

**Remove unused imports:**
```python
# Remove these unused imports from cutout modules:
# - Arc, QuadraticBezier, SVGElementPath, LineString, Point
```

### Phase 3: Dead Code Removal

**Remove unused variables:**
```python
# Remove unused variables like:
# - log (if not used)
# - x, y in _fit_text function
# - window_seconds, filter_palette_only, etc.
```

## Verify

**Run verification commands:**
```bash
# Activate virtual environment
source venv/bin/activate

# Check for syntax errors
python -m py_compile bin/viral/shorts.py

# Run ruff to check for remaining issues
python -m ruff check bin/ --output-format=concise

# Run vulture to check for remaining dead code
python -m vulture bin/ --min-confidence 80

# Test that critical functionality still works
python -c "from bin.viral.thumbnails import generate_thumbnails; print('Import successful')"
```

**Success Criteria:**
- No syntax errors
- No undefined name errors
- No import organization errors (E402)
- No unused variable errors (F841)
- No bare except clauses (E722)
- No import redefinitions (F811)
- Significantly reduced vulture dead code warnings

**Files to prioritize:**
1. `bin/viral/shorts.py` (syntax error)
2. `bin/tts_generate.py` (missing Path import)
3. `bin/voice_cues.py` (missing time import)
4. `bin/test_integration.py` (missing validate_scenescript)
5. Files with _read_yaml undefined name errors
6. Files with E402 import organization errors
7. Files with F841 unused variable errors

**Remember:**
- Follow the project's coding standards
- Maintain backward compatibility
- Test each fix before moving to the next
- Use logging instead of print statements
- Keep functions idempotent
- Respect the single-lane constraint for heavy operations

