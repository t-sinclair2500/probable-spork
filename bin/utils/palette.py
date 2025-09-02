# bin/utils/palette.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # optional; only needed for YAML files

HexColor = str


@dataclass
class Palette:
    colors: List[HexColor]
    name: Optional[str] = None

    def get(self, idx: int) -> HexColor:
        if not self.colors:
            return "#000000"
        return self.colors[idx % len(self.colors)]


def _flatten_color_sources(obj: Any) -> List[HexColor]:
    """
    Accept common palette shapes and produce a flat list of hex strings.
    Supported:
      - {'colors': ['#fff', '#000', ...]}
      - {'palette': ['#fff', ...]}
      - {'primary': ['#...'], 'accent': ['#...']}  # category dict → flattened in stable key order
      - ['#fff', '#000']  # raw list
    """
    if obj is None:
        return []
    # Already a Palette
    if isinstance(obj, Palette):
        return list(obj.colors)
    # List of hex colors
    if isinstance(obj, list) and all(isinstance(x, str) for x in obj):
        return list(obj)  # type: ignore
    # Dict forms
    if isinstance(obj, dict):
        if "colors" in obj:
            colors_val = obj["colors"]
            if isinstance(colors_val, list):
                return [str(c) for c in colors_val]
            elif isinstance(colors_val, dict):
                # Handle case where colors is a dict of name->hex pairs
                return [str(c) for c in colors_val.values()]
        if "palette" in obj and isinstance(obj["palette"], list):
            return [str(c) for c in obj["palette"]]
        # Category dict → flatten by sorted keys for determinism
        flat: List[str] = []
        for k in sorted(obj.keys()):
            v = obj[k]
            if isinstance(v, list):
                flat.extend(str(c) for c in v)
            elif isinstance(v, str) and v.startswith("#"):
                # Handle case where dict values are hex strings
                flat.append(v)
        return flat
    # Fallback: best effort string → single color?
    if isinstance(obj, str) and obj.startswith("#"):
        return [obj]
    return []


def ensure_palette(obj: Any, *, name: Optional[str] = None) -> Palette:
    """
    Convert legacy forms (dict/list) into a Palette with .colors.
    """
    if isinstance(obj, Palette):
        return obj
    colors = _flatten_color_sources(obj)
    return Palette(colors=colors, name=name)


def load_palette(
    source: Union[str, Path, Dict[str, Any], Palette], *, name: Optional[str] = None
) -> Palette:
    """
    Load a Palette from:
      - Path to .json or .yaml/.yml file
      - Dict containing colors/palette/etc.
      - Already-constructed Palette
    """
    if isinstance(source, Palette):
        return source
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            # interpret as raw hex color string or a simple JSON payload
            try:
                maybe = json.loads(str(source))
                return ensure_palette(maybe, name=name)
            except Exception:
                # fallback to a single color string (rare)
                return ensure_palette(source, name=name)
        if p.suffix.lower() == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            return ensure_palette(data, name=name or p.stem)
        if p.suffix.lower() in (".yaml", ".yml"):
            if yaml is None:
                raise RuntimeError("PyYAML is required to load YAML palettes.")
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            return ensure_palette(data, name=name or p.stem)
        # unknown extension; try JSON then YAML
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return ensure_palette(data, name=name or p.stem)
        except Exception:
            if yaml:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                return ensure_palette(data, name=name or p.stem)
            raise
    # dict and other forms
    return ensure_palette(source, name=name)
