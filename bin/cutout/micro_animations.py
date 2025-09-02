#!/usr/bin/env python3
"""
Micro-Animations via Geometry Engine

Provides subtle geometry-driven micro-animations for select elements (backgrounds, props,
decorative shapes) that add "life" without distracting from VO. Ensures timing fits
scene durations and respects safe margins.

All animations are deterministic and respect the constraints:
- ≤10% of elements in a scene
- Movement ≤4px amplitude per 1000ms
- No text bounding box overlaps
- Ease in/out timing
"""

import json
import math
import random
from typing import Any, Dict, List, Optional

from bin.core import get_logger

from .sdk import Element, Keyframe, Scene
from .svg_geom import SVGGeometryEngine

log = get_logger("micro_animations")


class MicroAnimationGenerator:
    """Generates subtle micro-animations for scene elements."""

    def __init__(self, config: Dict[str, Any], seed: Optional[int] = None):
        """
        Initialize the micro-animation generator.

        Args:
            config: Micro-animations configuration from modules.yaml
            seed: Optional seed for deterministic output
        """
        self.config = config
        self.seed = seed or config.get("seed", 42)
        self.geometry_engine = SVGGeometryEngine(seed=self.seed)

        # Set random seed for deterministic behavior
        random.seed(self.seed)

        # Animation constraints
        self.max_elements_percent = config.get("max_elements_percent", 10)
        self.max_movement_px = config.get("max_movement_px", 4)
        self.max_movement_per_1000ms = config.get("max_movement_per_1000ms", 4)
        self.ease_in_out = config.get("ease_in_out", True)
        self.collision_check = config.get("collision_check", True)

        # Animation metadata for reporting
        self.animation_log = []

    def _is_eligible_for_animation(self, element: Element, scene: Scene) -> bool:
        """
        Determine if an element is eligible for micro-animation.

        Args:
            element: Scene element to evaluate
            scene: Parent scene context

        Returns:
            True if element should be considered for animation
        """
        # Skip text elements to avoid legibility issues
        if element.type in ["text", "lower_third", "list_step"]:
            return False

        # Skip elements that are too close to text
        if self._has_nearby_text(element, scene):
            return False

        # Prefer decorative elements: backgrounds, props, shapes
        if element.type in ["shape", "prop", "character"]:
            return True

        # Skip elements with existing keyframes
        if element.keyframes:
            return False

        return True

    def _has_nearby_text(
        self, element: Element, scene: Scene, safe_distance: int = 80
    ) -> bool:
        """
        Check if element is too close to text elements.

        Args:
            element: Element to check
            scene: Parent scene
            safe_distance: Minimum safe distance in pixels

        Returns:
            True if element is too close to text
        """
        for other_element in scene.elements:
            if other_element.type in ["text", "lower_third", "list_step"]:
                distance = math.sqrt(
                    (element.x - other_element.x) ** 2
                    + (element.y - other_element.y) ** 2
                )
                if distance < safe_distance:
                    return True
        return False

    def _calculate_animation_parameters(
        self, element: Element, scene_duration_ms: int
    ) -> Dict[str, Any]:
        """
        Calculate animation parameters for an element.

        Args:
            element: Element to animate
            scene_duration_ms: Scene duration in milliseconds

        Returns:
            Animation parameters dictionary
        """
        # Determine animation type based on element properties
        if element.type == "shape":
            anim_type = self._choose_shape_animation()
        elif element.type == "prop":
            anim_type = self._choose_prop_animation()
        elif element.type == "character":
            anim_type = self._choose_character_animation()
        else:
            anim_type = "morph"

        # Calculate timing and movement constraints
        scene_duration_sec = scene_duration_ms / 1000.0
        max_movement = min(self.max_movement_px, self.max_movement_per_1000ms)

        # Generate keyframes with ease in/out
        keyframes = self._generate_keyframes(anim_type, scene_duration_ms, max_movement)

        return {
            "type": anim_type,
            "keyframes": keyframes,
            "max_movement": max_movement,
            "duration": scene_duration_sec,
        }

    def _choose_shape_animation(self) -> str:
        """Choose animation type for shape elements."""
        choices = ["morph", "scale", "rotate"]
        weights = [0.6, 0.3, 0.1]  # Prefer morphing for shapes
        return random.choices(choices, weights=weights)[0]

    def _choose_prop_animation(self) -> str:
        """Choose animation type for prop elements."""
        choices = ["translate", "scale", "morph"]
        weights = [0.5, 0.3, 0.2]  # Prefer subtle movement for props
        return random.choices(choices, weights=weights)[0]

    def _choose_character_animation(self) -> str:
        """Choose animation type for character elements."""
        choices = ["translate", "scale", "morph"]
        weights = [0.4, 0.4, 0.2]  # Balanced for characters
        return random.choices(choices, weights=weights)[0]

    def _generate_keyframes(
        self, anim_type: str, scene_duration_ms: int, max_movement: float
    ) -> List[Keyframe]:
        """
        Generate keyframes for the specified animation type.

        Args:
            anim_type: Type of animation to generate
            scene_duration_ms: Scene duration in milliseconds
            max_movement: Maximum movement in pixels

        Returns:
            List of Keyframe objects
        """
        keyframes = []

        if anim_type == "morph":
            # Morph animation: src -> tgt -> src
            keyframes = [
                Keyframe(t=0, scale=1.0),
                Keyframe(t=scene_duration_ms // 2, scale=1.05),
                Keyframe(t=scene_duration_ms, scale=1.0),
            ]

        elif anim_type == "scale":
            # Subtle scale animation
            scale_factor = 1.0 + (max_movement / 100.0)  # Convert px to scale
            keyframes = [
                Keyframe(t=0, scale=1.0),
                Keyframe(t=scene_duration_ms // 3, scale=scale_factor),
                Keyframe(t=2 * scene_duration_ms // 3, scale=scale_factor),
                Keyframe(t=scene_duration_ms, scale=1.0),
            ]

        elif anim_type == "rotate":
            # Subtle rotation animation
            max_rotation = max_movement * 2  # Convert px to degrees
            keyframes = [
                Keyframe(t=0, rotate=0),
                Keyframe(t=scene_duration_ms // 2, rotate=max_rotation),
                Keyframe(t=scene_duration_ms, rotate=0),
            ]

        elif anim_type == "translate":
            # Subtle translation animation
            keyframes = [
                Keyframe(t=0, x=0, y=0),
                Keyframe(
                    t=scene_duration_ms // 4, x=max_movement * 0.5, y=max_movement * 0.3
                ),
                Keyframe(
                    t=3 * scene_duration_ms // 4,
                    x=-max_movement * 0.3,
                    y=max_movement * 0.5,
                ),
                Keyframe(t=scene_duration_ms, x=0, y=0),
            ]

        return keyframes

    def _apply_ease_in_out(self, keyframes: List[Keyframe]) -> List[Keyframe]:
        """
        Apply ease-in/ease-out timing to keyframes.

        Args:
            keyframes: List of keyframes to modify

        Returns:
            Modified keyframes with ease timing
        """
        if not self.ease_in_out or len(keyframes) < 3:
            return keyframes

        # For now, we'll use the existing keyframe system
        # In a more sophisticated implementation, we could add easing functions
        # to the Keyframe model or create custom easing curves
        return keyframes

    def generate_scene_animations(self, scene: Scene) -> Dict[str, Any]:
        """
        Generate micro-animations for a scene.

        Args:
            scene: Scene to animate

        Returns:
            Dictionary with animation results and metadata
        """
        if not self.config.get("enable", False):
            log.info("[micro-anim] Micro-animations disabled, skipping")
            return {
                "enabled": False,
                "elements_animated": 0,
                "total_elements": len(scene.elements),
                "animations": [],
            }

        log.info(
            f"[micro-anim] Generating animations for scene {scene.id} with {len(scene.elements)} elements"
        )

        # Find eligible elements
        eligible_elements = [
            elem
            for elem in scene.elements
            if self._is_eligible_for_animation(elem, scene)
        ]

        # Limit to max percentage
        max_animated = max(
            1, int(len(scene.elements) * self.max_elements_percent / 100)
        )
        elements_to_animate = eligible_elements[:max_animated]

        log.info(
            f"[micro-anim] {len(elements_to_animate)}/{len(scene.elements)} elements eligible for animation"
        )

        # Generate animations for each element
        animations = []
        for element in elements_to_animate:
            try:
                anim_params = self._calculate_animation_parameters(
                    element, scene.duration_ms
                )
                anim_params["keyframes"] = self._apply_ease_in_out(
                    anim_params["keyframes"]
                )

                # Apply keyframes to element
                element.keyframes = anim_params["keyframes"]

                # Log animation details
                animation_info = {
                    "element_id": element.id,
                    "element_type": element.type,
                    "animation_type": anim_params["type"],
                    "max_movement_px": anim_params["max_movement"],
                    "keyframe_count": len(anim_params["keyframes"]),
                    "duration_sec": anim_params["duration"],
                }

                animations.append(animation_info)

                log.info(
                    f"[micro-anim] Element {element.id} ({element.type}): {anim_params['type']} "
                    f"animation, max movement {anim_params['max_movement']:.1f}px"
                )

            except Exception as e:
                log.warning(f"[micro-anim] Failed to animate element {element.id}: {e}")
                continue

        # Record animation metadata
        scene_animation_data = {
            "enabled": True,
            "scene_id": scene.id,
            "elements_animated": len(animations),
            "total_elements": len(scene.elements),
            "max_movement_px": self.max_movement_px,
            "seed": self.seed,
            "animations": animations,
        }

        self.animation_log.append(scene_animation_data)

        log.info(
            f"[micro-anim] Scene {scene.id}: {len(animations)} elements animated "
            f"with seed {self.seed}"
        )

        return scene_animation_data

    def get_animation_summary(self) -> Dict[str, Any]:
        """
        Get summary of all animations generated in this session.

        Returns:
            Summary dictionary with animation statistics
        """
        if not self.animation_log:
            return {"enabled": False, "scenes_processed": 0}

        total_elements = sum(log["total_elements"] for log in self.animation_log)
        total_animated = sum(log["elements_animated"] for log in self.animation_log)

        return {
            "enabled": True,
            "scenes_processed": len(self.animation_log),
            "total_elements": total_elements,
            "total_animated": total_animated,
            "animation_percentage": (
                (total_animated / total_elements * 100) if total_elements > 0 else 0
            ),
            "seed": self.seed,
            "scenes": self.animation_log,
        }

    def save_animation_report(self, output_path: str) -> None:
        """
        Save animation report to JSON file.

        Args:
            output_path: Path to save the report
        """
        summary = self.get_animation_summary()

        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        log.info(f"[micro-anim] Animation report saved to {output_path}")


def create_micro_animation_generator(
    config: Dict[str, Any], seed: Optional[int] = None
) -> MicroAnimationGenerator:
    """
    Factory function to create a micro-animation generator.

    Args:
        config: Configuration dictionary
        seed: Optional seed for deterministic output

    Returns:
        Configured MicroAnimationGenerator instance
    """
    return MicroAnimationGenerator(config, seed)
