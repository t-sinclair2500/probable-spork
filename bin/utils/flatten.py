# bin/utils/flatten.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List

Element = Dict[str, Any]


def _is_scene(obj: Any) -> bool:
    # Duck-typing: Scene if it has .elements, ["elements"], or to_elements()
    if obj is None:
        return False
    if hasattr(obj, "elements"):
        return True
    if isinstance(obj, dict) and "elements" in obj:
        return True
    if hasattr(obj, "to_elements") and callable(getattr(obj, "to_elements")):
        return True
    return False


def _scene_to_elements(scene: Any) -> List[Element]:
    # Extract elements from varied scene shapes
    if scene is None:
        return []
    if hasattr(scene, "to_elements") and callable(getattr(scene, "to_elements")):
        out = scene.to_elements()
        return list(out or [])
    if hasattr(scene, "elements"):
        el = getattr(scene, "elements")
        return list(el or [])
    if isinstance(scene, dict) and "elements" in scene:
        return list(scene.get("elements") or [])
    return []


def flatten_elements(items: Iterable[Any]) -> List[Element]:
    """
    Flatten a mixed sequence of Scenes and/or Elements into a flat, ordered list of Element dicts.
    - Preserves ordering: scenes are processed in order; elements within scenes retain order.
    - Ignores None and empty items.
    - Ensures each element is a dict. If an object has .to_dict(), use it.
    """
    flat: List[Element] = []
    for item in items or []:
        if item is None:
            continue
        if _is_scene(item):
            for el in _scene_to_elements(item):
                if el is None:
                    continue
                if hasattr(el, "to_dict") and callable(getattr(el, "to_dict")):
                    flat.append(el.to_dict())
                elif isinstance(el, dict):
                    flat.append(el)
                else:
                    # best-effort: wrap unknown element object into dict via __dict__
                    flat.append({k: v for k, v in vars(el).items()})
        else:
            # treat as single element
            if hasattr(item, "to_dict") and callable(getattr(item, "to_dict")):
                flat.append(item.to_dict())
            elif isinstance(item, dict):
                flat.append(item)
            else:
                flat.append({k: v for k, v in vars(item).items()})
    return flat
