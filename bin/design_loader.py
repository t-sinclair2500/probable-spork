#!/usr/bin/env python3
"""
Design Loader Module

Loads the centralized design language definition and provides utilities for
accessing colors, assets, and scene templates. Validates that all assets
and templates conform to the design language rules.
"""

import json
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bin.core import get_logger

log = get_logger("design_loader")


class DesignLoader:
    """Centralized design language loader and validator."""

    def __init__(self, design_root: Optional[str] = None):
        """Initialize the design loader.

        Args:
            design_root: Path to design assets root (defaults to project_root/design)
        """
        if design_root is None:
            design_root = project_root / "design"

        self.design_root = Path(design_root)
        self.design_language_path = self.design_root / "design_language.json"
        self.svg_root = project_root / "assets" / "design" / "svg"
        self.scenes_root = project_root / "assets" / "design" / "scenes"

        self.design_language = self._load_design_language()
        self._validate_structure()

    def _load_design_language(self) -> Dict[str, Any]:
        """Load the design language definition."""
        try:
            with open(self.design_language_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            log.error(f"Design language file not found: {self.design_language_path}")
            raise
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in design language file: {e}")
            raise

    def _validate_structure(self):
        """Validate that the design directory structure exists."""
        required_dirs = [
            self.design_root,
            self.svg_root,
            self.svg_root / "backgrounds",
            self.svg_root / "objects",
            self.svg_root / "characters",
            self.scenes_root,
        ]

        for dir_path in required_dirs:
            if not dir_path.exists():
                log.warning(f"Required directory missing: {dir_path}")
                dir_path.mkdir(parents=True, exist_ok=True)
                log.info(f"Created directory: {dir_path}")

    def get_color(self, name: str) -> str:
        """Get a color by name from the design language.

        Args:
            name: Color name (e.g., 'primary_blue', 'accent_cream')

        Returns:
            Hex color code

        Raises:
            KeyError: If color name not found
        """
        if name not in self.design_language["colors"]:
            raise KeyError(f"Color '{name}' not found in design language")
        return self.design_language["colors"][name]

    def get_all_colors(self) -> Dict[str, str]:
        """Get all colors from the design language."""
        return self.design_language["colors"].copy()

    def get_font(self, category: str) -> str:
        """Get a font family by category.

        Args:
            category: Font category ('headings', 'body', 'fallback')

        Returns:
            Font family string

        Raises:
            KeyError: If font category not found
        """
        if category not in self.design_language["fonts"]:
            raise KeyError(f"Font category '{category}' not found in design language")
        return self.design_language["fonts"][category]

    def get_asset_path(self, filename: str) -> Path:
        """Get the full path to an SVG asset.

        Args:
            filename: Asset filename (e.g., 'backgrounds/solid_primary_blue.svg')

        Returns:
            Full path to the asset file

        Raises:
            FileNotFoundError: If asset file doesn't exist
        """
        asset_path = self.svg_root / filename
        if not asset_path.exists():
            raise FileNotFoundError(f"Asset not found: {asset_path}")
        return asset_path

    def get_scene_template(self, scene_id: str) -> Dict[str, Any]:
        """Get a scene template by ID.

        Args:
            scene_id: Scene template ID (e.g., 'intro_fullscreen')

        Returns:
            Scene template dictionary

        Raises:
            FileNotFoundError: If scene template doesn't exist
        """
        template_path = self.scenes_root / f"{scene_id}.json"
        if not template_path.exists():
            raise FileNotFoundError(f"Scene template not found: {template_path}")

        try:
            with open(template_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in scene template {scene_id}: {e}")
            raise

    def get_all_scene_templates(self) -> List[str]:
        """Get list of all available scene template IDs."""
        if not self.scenes_root.exists():
            return []

        templates = []
        for template_file in self.scenes_root.glob("*.json"):
            templates.append(template_file.stem)
        return sorted(templates)

    def validate_svg_colors(self, svg_path: Path) -> List[str]:
        """Validate that an SVG only uses colors from the design language.

        Args:
            svg_path: Path to SVG file

        Returns:
            List of invalid colors found
        """
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()

            # Get all allowed colors
            allowed_colors = set(self.design_language["colors"].values())
            invalid_colors = []

            # Check fill attributes
            for element in root.iter():
                fill = element.get("fill")
                if (
                    fill
                    and fill not in allowed_colors
                    and not fill.startswith("url(")
                    and fill != "none"
                ):
                    invalid_colors.append(fill)

                stroke = element.get("stroke")
                if stroke and stroke not in allowed_colors and stroke != "none":
                    invalid_colors.append(stroke)

            return list(set(invalid_colors))

        except ET.ParseError as e:
            log.error(f"Failed to parse SVG {svg_path}: {e}")
            return [f"Parse error: {e}"]

    def validate_all_assets(self) -> Dict[str, List[str]]:
        """Validate all SVG assets for color compliance.

        Returns:
            Dictionary mapping asset paths to lists of validation errors
        """
        validation_results = {}

        for svg_file in self.svg_root.rglob("*.svg"):
            relative_path = svg_file.relative_to(self.svg_root)
            invalid_colors = self.validate_svg_colors(svg_file)

            if invalid_colors:
                validation_results[str(relative_path)] = invalid_colors

        return validation_results

    def validate_scene_templates(self) -> Dict[str, List[str]]:
        """Validate all scene templates for asset and color references.

        Returns:
            Dictionary mapping scene IDs to lists of validation errors
        """
        validation_results = {}

        for scene_id in self.get_all_scene_templates():
            try:
                template = self.get_scene_template(scene_id)
                errors = []

                # Check background asset exists
                if "background" in template and "asset" in template["background"]:
                    asset_path = template["background"]["asset"]
                    try:
                        self.get_asset_path(asset_path)
                    except FileNotFoundError:
                        errors.append(f"Background asset not found: {asset_path}")

                # Check element assets exist
                for element in template.get("elements", []):
                    if element.get("type") == "svg" and "asset" in element:
                        asset_path = element["asset"]
                        try:
                            self.get_asset_path(asset_path)
                        except FileNotFoundError:
                            errors.append(f"Element asset not found: {asset_path}")

                # Check colors are valid
                for element in template.get("elements", []):
                    if "color" in element:
                        color = element["color"]
                        if color not in self.design_language["colors"].values():
                            errors.append(f"Invalid color: {color}")

                if errors:
                    validation_results[scene_id] = errors

            except Exception as e:
                validation_results[scene_id] = [f"Template error: {e}"]

        return validation_results

    def run_validation(self) -> bool:
        """Run complete validation of design system.

        Returns:
            True if all validations pass, False otherwise
        """
        log.info("Running design system validation...")

        # Validate SVG assets
        asset_errors = self.validate_all_assets()
        if asset_errors:
            log.error("SVG asset validation failed:")
            for asset, errors in asset_errors.items():
                log.error(f"  {asset}: {errors}")
        else:
            log.info("✓ All SVG assets validated successfully")

        # Validate scene templates
        template_errors = self.validate_scene_templates()
        if template_errors:
            log.error("Scene template validation failed:")
            for scene, errors in template_errors.items():
                log.error(f"  {scene}: {errors}")
        else:
            log.info("✓ All scene templates validated successfully")

        # Check asset counts
        self._check_asset_counts()

        return len(asset_errors) == 0 and len(template_errors) == 0

    def _check_asset_counts(self):
        """Check that minimum asset counts are met."""
        log.info("Checking asset counts...")

        # Count backgrounds
        background_count = len(list((self.svg_root / "backgrounds").glob("*.svg")))
        log.info(f"  Backgrounds: {background_count}/10")

        # Count objects
        object_count = len(list((self.svg_root / "objects").glob("*.svg")))
        log.info(f"  Objects: {object_count}/50")

        # Count characters
        character_count = len(list((self.svg_root / "characters").glob("*.svg")))
        log.info(f"  Characters: {character_count}/4")

        # Count scene templates
        template_count = len(self.get_all_scene_templates())
        log.info(f"  Scene templates: {template_count}/5")


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Design Loader and Validator")
    parser.add_argument("--test", action="store_true", help="Run validation test")
    parser.add_argument("--colors", action="store_true", help="List all colors")
    parser.add_argument("--fonts", action="store_true", help="List all fonts")
    parser.add_argument(
        "--templates", action="store_true", help="List all scene templates"
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate all assets and templates"
    )

    args = parser.parse_args()

    try:
        loader = DesignLoader()

        if args.colors:
            print("Available colors:")
            for name, hex_code in loader.get_all_colors().items():
                print(f"  {name}: {hex_code}")

        if args.fonts:
            print("Available fonts:")
            for category, font_family in loader.design_language["fonts"].items():
                print(f"  {category}: {font_family}")

        if args.templates:
            print("Available scene templates:")
            for template_id in loader.get_all_scene_templates():
                print(f"  {template_id}")

        if args.validate or args.test:
            success = loader.run_validation()
            if success:
                print("\n✓ All validations passed!")
                return 0
            else:
                print("\n✗ Some validations failed!")
                return 1

        if not any([args.colors, args.fonts, args.templates, args.validate, args.test]):
            # Default: show summary
            print("Design System Summary:")
            print(f"  Colors: {len(loader.get_all_colors())}")
            print(f"  Fonts: {len(loader.design_language['fonts'])}")
            print(f"  Scene templates: {len(loader.get_all_scene_templates())}")
            print("\nUse --help for available options")

        return 0

    except Exception as e:
        log.error(f"Design loader error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
