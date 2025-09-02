# bin/utils/slug.py
from typing import Union

from pathlib import Path


def safe_slug_from_script(path: Union[str, Path]) -> str:
    """
    Robust slug derivation:
      - Prefer stem of filename (no underscore assumption).
      - Lowercase, replace spaces and underscores with hyphens, collapse repeats.
      - Strip special characters, provide fallback for empty results.
    """
    stem = Path(path).stem.strip()
    # Replace underscores and spaces with hyphens
    s = stem.replace("_", "-").replace(" ", "-")
    # Split and rejoin to handle multiple spaces/underscores
    s = "-".join(s.split())
    # Strip special characters (keep only alphanumeric and hyphens)
    import re

    s = re.sub(r"[^a-zA-Z0-9-]", "", s)
    # Collapse multiple hyphens
    while "--" in s:
        s = s.replace("--", "-")
    # Strip leading/trailing hyphens
    s = s.strip("-")
    # Provide fallback for empty results
    return s.lower() if s else "unnamed"
