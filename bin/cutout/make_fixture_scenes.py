#!/usr/bin/env python3
"""
SceneScript Fixture Generator

Creates a demo SceneScript file with various scene types and elements for development and testing.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path to import SDK
sys.path.insert(0, str(Path(__file__).parent.parent))

from cutout.sdk import SceneScript, Scene, Element, Keyframe, Paths


def create_demo_scenes() -> List[Scene]:
    """Create demo scenes with various element types."""
    
    # Scene 1: Hook with text and character
    scene1 = Scene(
        id="hook",
        duration_ms=4000,
        bg="gradient1",
        elements=[
            Element(
                id="title",
                type="text",
                content="Welcome to Our Guide",
                x=640,
                y=200,
                width=800,
                height=100,
                style={"font_size": "hook", "color": "primary"}
            ),
            Element(
                id="narrator",
                type="character",
                x=200,
                y=400,
                width=150,
                height=200,
                keyframes=[
                    Keyframe(t=0, x=200, y=400, opacity=0.0),
                    Keyframe(t=500, x=200, y=400, opacity=1.0),
                    Keyframe(t=3500, x=200, y=400, opacity=1.0),
                    Keyframe(t=4000, x=200, y=400, opacity=0.0)
                ]
            )
        ]
    )
    
    # Scene 2: List steps
    scene2 = Scene(
        id="step1",
        duration_ms=3500,
        bg="paper",
        elements=[
            Element(
                id="step_title",
                type="text",
                content="Step 1: Preparation",
                x=640,
                y=150,
                width=600,
                height=80,
                style={"font_size": "body", "color": "secondary"}
            ),
            Element(
                id="step1_item",
                type="list_step",
                content="Gather your materials",
                x=400,
                y=300,
                width=500,
                height=60,
                keyframes=[
                    Keyframe(t=0, x=400, y=300, opacity=0.0, scale=0.8),
                    Keyframe(t=300, x=400, y=300, opacity=1.0, scale=1.0)
                ]
            ),
            Element(
                id="step1_icon",
                type="shape",
                x=300,
                y=300,
                width=60,
                height=60,
                style={"shape": "circle", "color": "accent"}
            )
        ]
    )
    
    # Scene 3: Counter and prop
    scene3 = Scene(
        id="step2",
        duration_ms=5000,
        bg="gradient1",
        elements=[
            Element(
                id="counter",
                type="counter",
                content="2",
                x=640,
                y=200,
                width=100,
                height=100,
                style={"font_size": "hook", "color": "primary"},
                keyframes=[
                    Keyframe(t=0, scale=0.5, opacity=0.0),
                    Keyframe(t=500, scale=1.2, opacity=1.0),
                    Keyframe(t=1000, scale=1.0, opacity=1.0)
                ]
            ),
            Element(
                id="step2_text",
                type="text",
                content="Apply the technique",
                x=640,
                y=350,
                width=600,
                height=80,
                style={"font_size": "body", "color": "text"}
            ),
            Element(
                id="phone_prop",
                type="prop",
                x=400,
                y=450,
                width=120,
                height=80,
                keyframes=[
                    Keyframe(t=0, x=400, y=450, rotate=0),
                    Keyframe(t=2500, x=400, y=450, rotate=5),
                    Keyframe(t=5000, x=400, y=450, rotate=0)
                ]
            )
        ]
    )
    
    # Scene 4: Lower third
    scene4 = Scene(
        id="step3",
        duration_ms=4500,
        bg="paper",
        elements=[
            Element(
                id="lower_third_bg",
                type="shape",
                x=640,
                y=600,
                width=800,
                height=80,
                style={"shape": "rectangle", "color": "primary", "opacity": 0.9}
            ),
            Element(
                id="lower_third_text",
                type="lower_third",
                content="Pro tip: Take your time",
                x=640,
                y=600,
                width=800,
                height=80,
                style={"font_size": "body", "color": "white"}
            ),
            Element(
                id="step3_main",
                type="text",
                content="Practice makes perfect",
                x=640,
                y=300,
                width=700,
                height=100,
                style={"font_size": "hook", "color": "secondary"}
            )
        ]
    )
    
    # Scene 5: Complex animation
    scene5 = Scene(
        id="step4",
        duration_ms=6000,
        bg="gradient1",
        elements=[
            Element(
                id="animated_text",
                type="text",
                content="Final step",
                x=640,
                y=200,
                width=400,
                height=80,
                style={"font_size": "body", "color": "accent"},
                keyframes=[
                    Keyframe(t=0, x=640, y=200, opacity=0.0, scale=0.5),
                    Keyframe(t=500, x=640, y=200, opacity=1.0, scale=1.0),
                    Keyframe(t=3000, x=640, y=200, opacity=1.0, scale=1.0),
                    Keyframe(t=3500, x=640, y=200, opacity=1.0, scale=1.1),
                    Keyframe(t=4000, x=640, y=200, opacity=1.0, scale=1.0),
                    Keyframe(t=5500, x=640, y=200, opacity=1.0, scale=1.0),
                    Keyframe(t=6000, x=640, y=200, opacity=0.0, scale=0.8)
                ]
            ),
            Element(
                id="checkmark",
                type="shape",
                x=800,
                y=200,
                width=60,
                height=60,
                style={"shape": "checkmark", "color": "success"},
                keyframes=[
                    Keyframe(t=2000, x=800, y=200, opacity=0.0, scale=0.0),
                    Keyframe(t=2500, x=800, y=200, opacity=1.0, scale=1.2),
                    Keyframe(t=3000, x=800, y=200, opacity=1.0, scale=1.0)
                ]
            )
        ]
    )
    
    # Scene 6: CTA with multiple elements
    scene6 = Scene(
        id="cta",
        duration_ms=7000,
        bg="gradient1",
        elements=[
            Element(
                id="cta_title",
                type="text",
                content="Ready to start?",
                x=640,
                y=200,
                width=600,
                height=100,
                style={"font_size": "hook", "color": "primary"}
            ),
            Element(
                id="cta_subtitle",
                type="text",
                content="Follow these steps",
                x=640,
                y=320,
                width=500,
                height=60,
                style={"font_size": "body", "color": "text"}
            ),
            Element(
                id="cta_button",
                type="shape",
                x=640,
                y=450,
                width=200,
                height=60,
                style={"shape": "rectangle", "color": "accent", "corner_radius": 8},
                keyframes=[
                    Keyframe(t=0, x=640, y=450, scale=1.0),
                    Keyframe(t=3000, x=640, y=450, scale=1.0),
                    Keyframe(t=3500, x=640, y=450, scale=1.1),
                    Keyframe(t=4000, x=640, y=450, scale=1.0),
                    Keyframe(t=6000, x=640, y=450, scale=1.0),
                    Keyframe(t=6500, x=640, y=450, scale=1.1),
                    Keyframe(t=7000, x=640, y=450, scale=1.0)
                ]
            ),
            Element(
                id="cta_button_text",
                type="text",
                content="Get Started",
                x=640,
                y=450,
                width=200,
                height=60,
                style={"font_size": "body", "color": "white", "text_align": "center"}
            )
        ]
    )
    
    return [scene1, scene2, scene3, scene4, scene5, scene6]


def main():
    """Generate demo SceneScript fixture."""
    
    # Create demo scenes
    scenes = create_demo_scenes()
    
    # Create SceneScript
    scene_script = SceneScript(
        slug="demo",
        fps=30,
        scenes=scenes,
        metadata={
            "description": "Demo SceneScript for development and testing",
            "created_by": "make_fixture_scenes.py",
            "version": "1.0.0"
        }
    )
    
    # Ensure scenescripts directory exists
    scenescripts_dir = Path("scenescripts")
    scenescripts_dir.mkdir(exist_ok=True)
    
    # Save to demo.json
    output_path = scenescripts_dir / "demo.json"
    
    try:
        with open(output_path, 'w') as f:
            json.dump(scene_script.model_dump(), f, indent=2)
        
        print(f"✅ Generated demo SceneScript: {output_path}")
        print(f"   - {len(scenes)} scenes")
        print(f"   - Total duration: {sum(s.duration_ms for s in scenes) / 1000:.1f}s")
        print(f"   - Element types: {set(e.type for s in scenes for e in s.elements)}")
        
    except Exception as e:
        print(f"ERROR: Failed to save demo SceneScript: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
