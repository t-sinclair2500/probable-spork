#!/usr/bin/env python3
"""
Test Storyboard/Animatics API Alignment

Verifies that the storyboard and animatics systems use:
1. A unified Palette object with .colors adapter
2. A single flatten_elements() utility everywhere before rasterization
"""

import os

# Ensure repo root on path
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.cutout.sdk import Element, Scene
from bin.utils.flatten import flatten_elements
from bin.utils.palette import Palette, ensure_palette


class TestPaletteAdapter:
    """Test that palette adapter works correctly for all input types."""

    def test_dict_palette_becomes_palette_with_colors(self):
        """Test that dict palette becomes Palette with .colors."""
        # Test various dict formats
        test_cases = [
            {"colors": ["#ff0000", "#00ff00", "#0000ff"]},
            {"palette": ["#ff0000", "#00ff00"]},
            {"primary": ["#ff0000"], "accent": ["#00ff00"]},
            {"color1": "#ff0000", "color2": "#00ff00"},
        ]

        for palette_dict in test_cases:
            palette_obj = ensure_palette(palette_dict)
            assert isinstance(palette_obj, Palette)
            assert hasattr(palette_obj, "colors")
            assert isinstance(palette_obj.colors, list)
            assert all(isinstance(c, str) for c in palette_obj.colors)
            assert all(c.startswith("#") for c in palette_obj.colors)

    def test_list_palette_becomes_palette_with_colors(self):
        """Test that list palette becomes Palette with .colors."""
        palette_list = ["#ff0000", "#00ff00", "#0000ff"]
        palette_obj = ensure_palette(palette_list)

        assert isinstance(palette_obj, Palette)
        assert hasattr(palette_obj, "colors")
        assert palette_obj.colors == palette_list

    def test_already_palette_returns_same(self):
        """Test that already Palette objects are returned unchanged."""
        original_palette = Palette(colors=["#ff0000", "#00ff00"])
        result_palette = ensure_palette(original_palette)

        assert result_palette is original_palette
        assert result_palette.colors == ["#ff0000", "#00ff00"]

    def test_palette_get_method(self):
        """Test that Palette.get() method works correctly."""
        palette = Palette(colors=["#ff0000", "#00ff00", "#0000ff"])

        assert palette.get(0) == "#ff0000"
        assert palette.get(1) == "#00ff00"
        assert palette.get(2) == "#0000ff"
        assert palette.get(3) == "#ff0000"  # Wraps around
        assert palette.get(-1) == "#0000ff"  # Negative indexing


class TestFlattenElements:
    """Test that flatten_elements works correctly for mixed inputs."""

    def test_scenes_and_elements_mix_flattens_deterministically(self):
        """Test that Scenes and Elements mix flattens deterministically."""
        # Create test scenes
        scene1 = Scene(
            id="scene1",
            duration_ms=3000,
            bg="background1",
            elements=[
                Element(id="elem1", type="text", content="Hello"),
                Element(id="elem2", type="prop", content="Prop"),
            ],
        )

        scene2 = Scene(
            id="scene2",
            duration_ms=2000,
            bg="background2",
            elements=[Element(id="elem3", type="text", content="World")],
        )

        # Create standalone elements
        elem4 = Element(id="elem4", type="shape", content="Shape")
        elem5 = Element(id="elem5", type="character", content="Char")

        # Test mixed input
        mixed_input = [scene1, elem4, scene2, elem5]
        flattened = flatten_elements(mixed_input)

        # Should preserve order: scene1 elements, then elem4, then scene2 elements, then elem5
        expected_order = ["elem1", "elem2", "elem4", "elem3", "elem5"]
        actual_order = [elem.get("id") for elem in flattened]

        assert actual_order == expected_order
        assert len(flattened) == 5
        assert all(isinstance(elem, dict) for elem in flattened)

    def test_dict_scenes_flatten_correctly(self):
        """Test that dict scenes flatten correctly."""
        scene_dict = {
            "id": "test_scene",
            "duration_ms": 3000,
            "bg": "background",
            "elements": [
                {"id": "elem1", "type": "text", "content": "Hello"},
                {"id": "elem2", "type": "prop", "content": "Prop"},
            ],
        }

        flattened = flatten_elements([scene_dict])

        assert len(flattened) == 2
        assert flattened[0]["id"] == "elem1"
        assert flattened[1]["id"] == "elem2"
        assert all(isinstance(elem, dict) for elem in flattened)

    def test_none_and_empty_handling(self):
        """Test that None and empty items are handled correctly."""
        scene = Scene(
            id="test_scene",
            duration_ms=3000,
            bg="background",
            elements=[
                Element(id="elem1", type="text", content="Hello"),
                Element(id="elem2", type="prop", content="Prop"),
            ],
        )

        # Test that None items in the input list are ignored
        flattened = flatten_elements([None, scene, None])

        assert len(flattened) == 2  # elem1 and elem2, None ignored
        assert flattened[0]["id"] == "elem1"
        assert flattened[1]["id"] == "elem2"

    def test_element_objects_convert_to_dict(self):
        """Test that Element objects convert to dict correctly."""
        elem = Element(id="test_elem", type="text", content="Test")
        flattened = flatten_elements([elem])

        assert len(flattened) == 1
        assert isinstance(flattened[0], dict)
        assert flattened[0]["id"] == "test_elem"
        assert flattened[0]["type"] == "text"
        assert flattened[0]["content"] == "Test"


class TestAnimaticsIntegration:
    """Test integration with animatics generation."""

    def test_palette_integration_with_animatics(self):
        """Test that palette adapter integrates correctly with animatics."""
        # Simulate the palette loading pattern from animatics_generate.py
        palette_sources = [
            {"colors": ["#ff0000", "#00ff00", "#0000ff"]},
            ["#ff0000", "#00ff00"],
            {"primary": ["#ff0000"], "accent": ["#00ff00"]},
        ]

        for palette_src in palette_sources:
            # This is the pattern used in animatics_generate.py
            palette_obj = ensure_palette(palette_src)

            # Should be able to access .colors without AttributeError
            colors = palette_obj.colors
            assert isinstance(colors, list)
            assert len(colors) > 0

            # Should be able to use in rasterization context
            assert all(isinstance(c, str) for c in colors)
            assert all(c.startswith("#") for c in colors)

    def test_flatten_integration_with_animatics(self):
        """Test that flatten utility integrates correctly with animatics."""
        # Simulate the scene structure from animatics
        scenes = [
            Scene(
                id="scene1",
                duration_ms=3000,
                bg="bg1",
                elements=[
                    Element(id="elem1", type="text", content="Hello"),
                    Element(id="elem2", type="prop", content="Prop"),
                ],
            ),
            Scene(
                id="scene2",
                duration_ms=2000,
                bg="bg2",
                elements=[Element(id="elem3", type="text", content="World")],
            ),
        ]

        # This is the pattern used in animatics_generate.py
        all_elements = flatten_elements(scenes)

        # Should be ready for rasterization
        assert isinstance(all_elements, list)
        assert len(all_elements) == 3
        assert all(isinstance(elem, dict) for elem in all_elements)

        # Should have all required fields for rasterization
        for elem in all_elements:
            assert "id" in elem
            assert "type" in elem
            assert "content" in elem


class TestBackwardCompatibility:
    """Test that the new API maintains backward compatibility."""

    def test_legacy_dict_access_patterns(self):
        """Test that legacy dict access patterns still work with adapter."""
        # Old pattern: palette["colors"]
        palette_dict = {"colors": ["#ff0000", "#00ff00"]}
        palette_obj = ensure_palette(palette_dict)

        # New pattern: palette.colors
        colors = palette_obj.colors
        assert colors == ["#ff0000", "#00ff00"]

        # Should work in both contexts
        assert palette_obj.colors == palette_dict["colors"]

    def test_legacy_list_access_patterns(self):
        """Test that legacy list access patterns still work with adapter."""
        # Old pattern: palette[0]
        palette_list = ["#ff0000", "#00ff00"]
        palette_obj = ensure_palette(palette_list)

        # New pattern: palette.get(0)
        assert palette_obj.get(0) == palette_list[0]
        assert palette_obj.get(1) == palette_list[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
