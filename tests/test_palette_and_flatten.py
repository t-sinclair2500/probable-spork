# tests/test_palette_and_flatten.py
import pytest
from dataclasses import dataclass
from pathlib import Path
import tempfile
import json

from bin.utils.palette import ensure_palette, load_palette, Palette
from bin.utils.flatten import flatten_elements


def test_palette_adapter_from_dict_variants():
    """Test Palette adapter with different dict input formats."""
    d1 = {"colors": ["#111111", "#222222"]}
    d2 = {"palette": ["#aaaaaa", "#bbbbbb"]}
    d3 = {"primary": ["#ff0000"], "accent": ["#00ff00", "#0000ff"]}

    p1 = ensure_palette(d1)
    p2 = ensure_palette(d2)
    p3 = ensure_palette(d3, name="cat")

    assert isinstance(p1, Palette) and p1.colors == ["#111111", "#222222"]
    assert p2.colors == ["#aaaaaa", "#bbbbbb"]
    # category dict flattens in sorted key order: accent, primary
    assert p3.colors == ["#00ff00", "#0000ff", "#ff0000"]
    assert p3.get(0).startswith("#")


def test_palette_adapter_from_list():
    """Test Palette adapter with list input."""
    colors = ["#010203", "#040506", "#070809"]
    p = ensure_palette(colors)
    assert isinstance(p, Palette)
    assert p.colors == colors
    assert p.get(0) == "#010203"
    assert p.get(3) == "#010203"  # wraps around (3 % 3 = 0)


def test_palette_adapter_from_string():
    """Test Palette adapter with single hex color string."""
    p = ensure_palette("#ff0000")
    assert isinstance(p, Palette)
    assert p.colors == ["#ff0000"]


def test_palette_adapter_from_none():
    """Test Palette adapter with None input."""
    p = ensure_palette(None)
    assert isinstance(p, Palette)
    assert p.colors == []
    assert p.get(0) == "#000000"  # fallback


def test_palette_loader_from_json(tmp_path):
    """Test loading palette from JSON file."""
    jp = tmp_path / "pal.json"
    jp.write_text('{"colors":["#010203","#040506"]}', encoding="utf-8")
    p = load_palette(jp)
    assert p.colors == ["#010203", "#040506"]


def test_palette_loader_from_dict():
    """Test loading palette from dict."""
    data = {"colors": ["#111111", "#222222"]}
    p = load_palette(data)
    assert p.colors == ["#111111", "#222222"]


def test_palette_loader_from_palette():
    """Test loading palette from existing Palette object."""
    original = Palette(colors=["#111111", "#222222"])
    p = load_palette(original)
    assert p is original  # should return same object


def test_palette_loader_from_path_string():
    """Test loading palette from path string."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"colors": ["#111111", "#222222"]}, f)
        path = f.name
    
    try:
        p = load_palette(path)
        assert p.colors == ["#111111", "#222222"]
    finally:
        Path(path).unlink()


def test_palette_loader_from_json_string():
    """Test loading palette from JSON string."""
    json_str = '{"colors": ["#111111", "#222222"]}'
    p = load_palette(json_str)
    assert p.colors == ["#111111", "#222222"]


def test_palette_loader_from_hex_string():
    """Test loading palette from hex color string."""
    p = load_palette("#ff0000")
    assert p.colors == ["#ff0000"]


def test_palette_get_method():
    """Test Palette.get() method with various indices."""
    p = Palette(colors=["#111111", "#222222", "#333333"])
    assert p.get(0) == "#111111"
    assert p.get(1) == "#222222"
    assert p.get(2) == "#333333"
    assert p.get(3) == "#111111"  # wraps around
    assert p.get(-1) == "#333333"  # negative indexing


def test_palette_empty_colors():
    """Test Palette behavior with empty colors list."""
    p = Palette(colors=[])
    assert p.get(0) == "#000000"  # fallback
    assert p.get(5) == "#000000"  # fallback


def test_flatten_elements_from_mixed_inputs():
    """Test flattening mixed inputs (elements and scenes)."""
    @dataclass
    class ElementObj:
        kind: str
        text: str
        def to_dict(self): return {"type": self.kind, "text": self.text}

    @dataclass
    class SceneObj:
        elements: list

    # mix: single element dict, element object, and a scene (with dict+obj inside)
    el1 = {"type": "text", "text": "A"}
    el2 = ElementObj(kind="text", text="B")
    scn = SceneObj(elements=[{"type": "rect", "w": 10}, ElementObj(kind="text", text="C")])

    out = flatten_elements([el1, el2, scn])
    assert isinstance(out, list) and len(out) == 4
    assert out[0]["text"] == "A"
    assert out[1]["text"] == "B"
    assert out[2]["type"] == "rect"
    assert out[3]["text"] == "C"


def test_flatten_elements_from_scene_dict():
    """Test flattening scene dict with elements."""
    scene_dict = {
        "elements": [
            {"type": "text", "text": "Hello"},
            {"type": "image", "src": "test.png"}
        ]
    }
    
    out = flatten_elements([scene_dict])
    assert len(out) == 2
    assert out[0]["text"] == "Hello"
    assert out[1]["src"] == "test.png"


def test_flatten_elements_from_scene_with_to_elements():
    """Test flattening scene object with to_elements() method."""
    class SceneWithMethod:
        def to_elements(self):
            return [
                {"type": "text", "text": "Method"},
                {"type": "rect", "w": 20}
            ]
    
    scene = SceneWithMethod()
    out = flatten_elements([scene])
    assert len(out) == 2
    assert out[0]["text"] == "Method"
    assert out[1]["w"] == 20


def test_flatten_elements_with_none_values():
    """Test flattening with None values."""
    elements = [
        {"type": "text", "text": "A"},
        None,
        {"type": "text", "text": "B"}
    ]
    
    out = flatten_elements(elements)
    assert len(out) == 2
    assert out[0]["text"] == "A"
    assert out[1]["text"] == "B"


def test_flatten_elements_with_none_iterable():
    """Test flattening with None iterable."""
    out = flatten_elements(None)
    assert out == []


def test_flatten_elements_with_empty_list():
    """Test flattening with empty list."""
    out = flatten_elements([])
    assert out == []


def test_flatten_elements_with_scene_none_elements():
    """Test flattening scene with None elements."""
    class SceneWithNoneElements:
        elements = None
    
    scene = SceneWithNoneElements()
    out = flatten_elements([scene])
    assert out == []


def test_flatten_elements_with_scene_empty_elements():
    """Test flattening scene with empty elements."""
    class SceneWithEmptyElements:
        elements = []
    
    scene = SceneWithEmptyElements()
    out = flatten_elements([scene])
    assert out == []


def test_flatten_elements_with_object_to_dict():
    """Test flattening object with to_dict() method."""
    class ElementWithDict:
        def __init__(self, data):
            self.data = data
        
        def to_dict(self):
            return self.data
    
    element = ElementWithDict({"type": "custom", "value": 42})
    out = flatten_elements([element])
    assert len(out) == 1
    assert out[0]["type"] == "custom"
    assert out[0]["value"] == 42


def test_flatten_elements_with_unknown_object():
    """Test flattening unknown object (should use __dict__)."""
    class UnknownElement:
        def __init__(self):
            self.type = "unknown"
            self.value = 123
    
    element = UnknownElement()
    out = flatten_elements([element])
    assert len(out) == 1
    assert out[0]["type"] == "unknown"
    assert out[0]["value"] == 123


def test_flatten_elements_preserves_order():
    """Test that flattening preserves the order of elements."""
    scene1 = {"elements": [{"id": "1"}, {"id": "2"}]}
    scene2 = {"elements": [{"id": "3"}, {"id": "4"}]}
    element = {"id": "5"}
    
    out = flatten_elements([scene1, element, scene2])
    assert [e["id"] for e in out] == ["1", "2", "5", "3", "4"]


if __name__ == "__main__":
    pytest.main([__file__])
