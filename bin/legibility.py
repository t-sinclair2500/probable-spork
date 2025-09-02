#!/usr/bin/env python3
"""
Legibility Validation and Background Injection

Ensures text legibility by:
1. Validating WCAG-AA contrast ratios
2. Auto-injecting safe backgrounds when missing
3. Providing actionable feedback for contrast issues

Used by acceptance pipeline to ensure all text meets accessibility standards.
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger, load_config

log = get_logger("legibility")


class LegibilityValidator:
    """Validates text legibility and manages background injection"""

    def __init__(self, config=None):
        self.config = config or load_config()
        self.safe_backgrounds = self._load_safe_backgrounds()
        self.wcag_aa_threshold = 4.5  # WCAG-AA contrast ratio threshold

    def _load_safe_backgrounds(self) -> List[str]:
        """Load safe background colors from design language"""
        try:
            design_language_path = os.path.join(ROOT, "design", "design_language.json")
            if os.path.exists(design_language_path):
                with open(design_language_path, "r", encoding="utf-8") as f:
                    design_language = json.load(f)

                # Extract background colors
                backgrounds = design_language.get("backgrounds", [])
                if backgrounds:
                    log.info(
                        f"[legibility-defaults] Loaded {len(backgrounds)} safe background colors"
                    )
                    return backgrounds
                else:
                    log.warning(
                        "[legibility-defaults] No background colors found in design language"
                    )
            else:
                log.warning("[legibility-defaults] Design language file not found")
        except Exception as e:
            log.warning(f"[legibility-defaults] Failed to load design language: {e}")

        # Fallback to safe defaults
        fallback_backgrounds = [
            "#FFFFFF",  # White
            "#F9FAFB",  # Light gray
            "#F3F4F6",  # Lighter gray
            "#E5E7EB",  # Medium light gray
            "#FEF3C7",  # Light yellow
            "#DBEAFE",  # Light blue
            "#D1FAE5",  # Light green
        ]
        log.info(
            f"[legibility-defaults] Using {len(fallback_backgrounds)} fallback background colors"
        )
        return fallback_backgrounds

    def validate_contrast_for_acceptance(
        self, text_color: str, background_color: str, element_id: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Validate text contrast for acceptance pipeline.

        Args:
            text_color: Text color in hex format
            background_color: Background color in hex format
            element_id: Element identifier for logging

        Returns:
            Dict with contrast validation results
        """
        log.info(
            f"[legibility-defaults] Validating contrast for {element_id}: {text_color} on {background_color}"
        )

        try:
            # Convert hex colors to RGB
            text_rgb = self._hex_to_rgb(text_color)
            bg_rgb = self._hex_to_rgb(background_color)

            if not text_rgb or not bg_rgb:
                return {
                    "valid": False,
                    "error": "Invalid color format",
                    "error_type": "invalid_color_format",
                    "element_id": element_id,
                    "text_color": text_color,
                    "background_color": background_color,
                }

            # Calculate contrast ratio
            contrast_ratio = self._calculate_contrast_ratio(text_rgb, bg_rgb)

            # Check WCAG-AA compliance
            wcag_aa_pass = contrast_ratio >= self.wcag_aa_threshold

            # Determine contrast level
            if contrast_ratio >= 7.0:
                contrast_level = "AAA"
            elif contrast_ratio >= 4.5:
                contrast_level = "AA"
            elif contrast_ratio >= 3.0:
                contrast_level = "A"
            else:
                contrast_level = "Fail"

            result = {
                "valid": wcag_aa_pass,
                "contrast_ratio": round(contrast_ratio, 2),
                "wcag_aa_pass": wcag_aa_pass,
                "wcag_aa_threshold": self.wcag_aa_threshold,
                "contrast_level": contrast_level,
                "text_color": text_color,
                "background_color": background_color,
                "element_id": element_id,
                "recommendations": [],
            }

            # Provide recommendations if contrast is insufficient
            if not wcag_aa_pass:
                result["recommendations"] = self._generate_contrast_recommendations(
                    text_color, background_color, contrast_ratio
                )

            log.info(
                f"[legibility-defaults] Contrast validation: {contrast_ratio:.2f} "
                f"({'PASS' if wcag_aa_pass else 'FAIL'}) for {element_id}"
            )

            return result

        except Exception as e:
            log.error(
                f"[legibility-defaults] Contrast validation error for {element_id}: {str(e)}"
            )
            return {
                "valid": False,
                "error": f"Contrast validation error: {str(e)}",
                "error_type": "validation_error",
                "element_id": element_id,
                "text_color": text_color,
                "background_color": background_color,
            }

    def inject_safe_background(
        self, text_color: str, element_id: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Inject a safe background color for text overlay.

        Args:
            text_color: Text color in hex format
            element_id: Element identifier for logging

        Returns:
            Dict with injection results and recommended background
        """
        log.info(
            f"[legibility-defaults] Injecting safe background for {element_id} with text color {text_color}"
        )

        try:
            # Find the best background color for this text
            best_background = self._find_best_background(text_color)

            if not best_background:
                return {
                    "success": False,
                    "error": "No suitable background color found",
                    "error_type": "no_suitable_background",
                    "element_id": element_id,
                    "text_color": text_color,
                }

            # Validate the combination
            validation = self.validate_contrast_for_acceptance(
                text_color, best_background, element_id
            )

            result = {
                "success": True,
                "injected_background": best_background,
                "text_color": text_color,
                "element_id": element_id,
                "contrast_validation": validation,
                "injection_method": "auto_background_injection",
            }

            log.info(
                f"[legibility-defaults] Background injection successful: {best_background} "
                f"for {element_id} (contrast: {validation['contrast_ratio']:.2f})"
            )

            return result

        except Exception as e:
            log.error(
                f"[legibility-defaults] Background injection failed for {element_id}: {str(e)}"
            )
            return {
                "success": False,
                "error": f"Background injection error: {str(e)}",
                "error_type": "injection_error",
                "element_id": element_id,
                "text_color": text_color,
            }

    def _find_best_background(self, text_color: str) -> Optional[str]:
        """Find the best background color for given text color"""
        try:
            text_rgb = self._hex_to_rgb(text_color)
            if not text_rgb:
                return None

            best_background = None
            best_contrast = 0.0

            for bg_color in self.safe_backgrounds:
                bg_rgb = self._hex_to_rgb(bg_color)
                if bg_rgb:
                    contrast = self._calculate_contrast_ratio(text_rgb, bg_rgb)
                    if contrast > best_contrast:
                        best_contrast = contrast
                        best_background = bg_color

            # Ensure minimum contrast threshold
            if best_contrast >= self.wcag_aa_threshold:
                return best_background
            else:
                log.warning(
                    f"[legibility-defaults] Best contrast {best_contrast:.2f} below threshold "
                    f"{self.wcag_aa_threshold}"
                )
                return None

        except Exception as e:
            log.error(f"[legibility-defaults] Error finding best background: {str(e)}")
            return None

    def _hex_to_rgb(self, hex_color: str) -> Optional[Tuple[int, int, int]]:
        """Convert hex color to RGB tuple"""
        try:
            # Remove # if present
            hex_color = hex_color.lstrip("#")

            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return (r, g, b)
            elif len(hex_color) == 3:
                r = int(hex_color[0] + hex_color[0], 16)
                g = int(hex_color[1] + hex_color[1], 16)
                b = int(hex_color[2] + hex_color[2], 16)
                return (r, g, b)
            else:
                return None

        except Exception:
            return None

    def _calculate_contrast_ratio(
        self, color1: Tuple[int, int, int], color2: Tuple[int, int, int]
    ) -> float:
        """Calculate contrast ratio between two RGB colors"""
        try:
            # Calculate relative luminance for both colors
            lum1 = self._calculate_relative_luminance(color1)
            lum2 = self._calculate_relative_luminance(color2)

            # Ensure lum1 is the lighter color
            if lum1 < lum2:
                lum1, lum2 = lum2, lum1

            # Calculate contrast ratio
            contrast_ratio = (lum1 + 0.05) / (lum2 + 0.05)

            return contrast_ratio

        except Exception as e:
            log.error(f"[legibility-defaults] Contrast calculation error: {str(e)}")
            return 0.0

    def _calculate_relative_luminance(self, rgb: Tuple[int, int, int]) -> float:
        """Calculate relative luminance for RGB color"""
        try:
            r, g, b = rgb

            # Convert to sRGB values (0-1)
            r_srgb = r / 255.0
            g_srgb = g / 255.0
            b_srgb = b / 255.0

            # Apply gamma correction
            def gamma_correct(c):
                if c <= 0.03928:
                    return c / 12.92
                else:
                    return ((c + 0.055) / 1.055) ** 2.4

            r_gamma = gamma_correct(r_srgb)
            g_gamma = gamma_correct(g_srgb)
            b_gamma = gamma_correct(b_srgb)

            # Calculate relative luminance
            luminance = 0.2126 * r_gamma + 0.7152 * g_gamma + 0.0722 * b_gamma

            return luminance

        except Exception as e:
            log.error(f"[legibility-defaults] Luminance calculation error: {str(e)}")
            return 0.0

    def _generate_contrast_recommendations(
        self, text_color: str, background_color: str, current_contrast: float
    ) -> List[str]:
        """Generate recommendations for improving contrast"""
        recommendations = []

        if current_contrast < self.wcag_aa_threshold:
            recommendations.append(
                f"Current contrast {current_contrast:.2f} is below WCAG-AA threshold {self.wcag_aa_threshold}"
            )

            # Suggest background injection
            best_bg = self._find_best_background(text_color)
            if best_bg:
                recommendations.append(
                    f"Consider using background color {best_bg} for better contrast"
                )

            # General recommendations
            if current_contrast < 3.0:
                recommendations.append(
                    "Consider using darker text or lighter background"
                )
            else:
                recommendations.append(
                    "Consider using slightly darker text or lighter background"
                )

            # Check if we can suggest a better text color
            if background_color in self.safe_backgrounds:
                recommendations.append(
                    "Current background is in safe palette - consider adjusting text color"
                )

        return recommendations

    def validate_scenescript_legibility(
        self, scenescript_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate legibility for entire SceneScript.

        Args:
            scenescript_data: SceneScript data structure

        Returns:
            Dict with overall legibility validation results
        """
        log.info("[legibility-defaults] Starting SceneScript legibility validation")

        try:
            scenes = scenescript_data.get("scenes", [])
            if not scenes:
                return {
                    "valid": False,
                    "error": "No scenes found in SceneScript",
                    "error_type": "no_scenes",
                }

            overall_results = {
                "valid": True,
                "total_elements": 0,
                "validated_elements": 0,
                "failed_elements": 0,
                "warnings": [],
                "element_results": [],
                "background_injections": [],
            }

            for scene_idx, scene in enumerate(scenes):
                scene_id = scene.get("scene_id", f"scene_{scene_idx}")
                elements = scene.get("elements", [])

                for element_idx, element in enumerate(elements):
                    if element.get("type") == "text":
                        element_id = element.get(
                            "element_id", f"{scene_id}_element_{element_idx}"
                        )
                        overall_results["total_elements"] += 1

                        # Get text and background colors
                        text_color = element.get("color", "#000000")
                        background_color = element.get("background_color")

                        if not background_color:
                            # No background specified - inject safe one
                            injection_result = self.inject_safe_background(
                                text_color, element_id
                            )
                            if injection_result["success"]:
                                overall_results["background_injections"].append(
                                    injection_result
                                )
                                background_color = injection_result[
                                    "injected_background"
                                ]
                                log.info(
                                    f"[legibility-defaults] Injected background {background_color} for {element_id}"
                                )
                            else:
                                overall_results["warnings"].append(
                                    f"Failed to inject background for {element_id}: {injection_result['error']}"
                                )
                                background_color = "#FFFFFF"  # Fallback to white

                        # Validate contrast
                        contrast_result = self.validate_contrast_for_acceptance(
                            text_color, background_color, element_id
                        )

                        element_result = {
                            "element_id": element_id,
                            "scene_id": scene_id,
                            "text_color": text_color,
                            "background_color": background_color,
                            "contrast_result": contrast_result,
                        }

                        overall_results["element_results"].append(element_result)
                        overall_results["validated_elements"] += 1

                        if not contrast_result["valid"]:
                            overall_results["failed_elements"] += 1
                            overall_results["valid"] = False

                        # Check if we need to inject background
                        if not background_color and contrast_result["valid"]:
                            # Element passed but no background - this shouldn't happen
                            log.warning(
                                f"[legibility-defaults] Element {element_id} passed without background"
                            )

            # Summary
            if overall_results["failed_elements"] > 0:
                overall_results["summary"] = (
                    f"{overall_results['failed_elements']} of {overall_results['validated_elements']} elements failed contrast validation"
                )
            else:
                overall_results["summary"] = (
                    f"All {overall_results['validated_elements']} elements passed contrast validation"
                )

            log.info(
                f"[legibility-defaults] SceneScript validation completed: "
                f"{overall_results['validated_elements']} elements, "
                f"{overall_results['failed_elements']} failed"
            )

            return overall_results

        except Exception as e:
            log.error(f"[legibility-defaults] SceneScript validation error: {str(e)}")
            return {
                "valid": False,
                "error": f"SceneScript validation error: {str(e)}",
                "error_type": "validation_error",
            }


def validate_contrast_for_acceptance(
    text_color: str, background_color: str, element_id: str = "unknown"
) -> Dict[str, Any]:
    """Convenience function for acceptance pipeline"""
    validator = LegibilityValidator()
    return validator.validate_contrast_for_acceptance(
        text_color, background_color, element_id
    )


def inject_safe_background(
    text_color: str, element_id: str = "unknown"
) -> Dict[str, Any]:
    """Convenience function for acceptance pipeline"""
    validator = LegibilityValidator()
    return validator.inject_safe_background(text_color, element_id)


def validate_scenescript_legibility(scenescript_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for acceptance pipeline"""
    validator = LegibilityValidator()
    return validator.validate_scenescript_legibility(scenescript_data)


if __name__ == "__main__":
    # Command line interface for testing
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate text legibility and inject backgrounds"
    )
    parser.add_argument("--text-color", required=True, help="Text color in hex format")
    parser.add_argument(
        "--background-color", help="Background color in hex format (optional)"
    )
    parser.add_argument("--element-id", default="test", help="Element identifier")

    args = parser.parse_args()

    validator = LegibilityValidator()

    if args.background_color:
        # Validate existing combination
        result = validator.validate_contrast_for_acceptance(
            args.text_color, args.background_color, args.element_id
        )
        print(f"Contrast validation: {result}")
    else:
        # Inject safe background
        result = validator.inject_safe_background(args.text_color, args.element_id)
        print(f"Background injection: {result}")

    if not result.get("valid", False) and not result.get("success", False):
        sys.exit(1)
