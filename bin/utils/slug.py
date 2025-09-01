# bin/utils/slug.py
from pathlib import Path
import re

_SLUG_SAFE = re.compile(r"[^a-z0-9-]+")

def safe_slug_from_script(path: str) -> str:
    """
    Derive a robust slug from a script filename or path.
    - Use basename without extension.
    - If there's an underscore, do NOT assume semantic parts; just use stem as-is.
    - Normalize: lowercase, replace spaces/underscores with '-', strip non [a-z0-9-], dedupe '-'.
    """
    stem = Path(path).stem  # handles .txt or other extensions
    # normalize separators to hyphen
    s = stem.replace("_", "-").replace(" ", "-").lower()
    # strip disallowed
    s = _SLUG_SAFE.sub("-", s)
    # dedupe hyphens
    s = re.sub(r"-{2,}", "-", s).strip("-")
    # fallback in worst case
    return s or "unnamed"
