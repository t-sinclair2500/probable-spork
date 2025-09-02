#!/usr/bin/env python3
"""
Viral Growth Engine Demo

Demonstrates the complete viral growth pipeline with sample data.
"""

import json
import sys

from pathlib import Path

# Add the bin directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def create_sample_brief():
    """Create a sample brief for demonstration."""
    return {
        "title": "AI Side Hustles",
        "keywords": ["ai", "automation", "income", "side hustle", "passive income"],
        "benefit": "extra income",
        "year": "2025",
        "audience": ["entrepreneurs", "tech workers", "students"],
    }


def demo_viral_lab():
    """Run a complete viral lab demonstration."""
    print("🚀 VIRAL GROWTH ENGINE DEMO")
    print("=" * 50)

    # Create sample brief
    brief = create_sample_brief()
    print(f"📋 Topic: {brief['title']}")
    print(f"🎯 Keywords: {', '.join(brief['keywords'])}")
    print(f"💰 Benefit: {brief['benefit']}")

    # Run viral lab
    from bin.viral.run import run_viral_lab

    result = run_viral_lab("demo-viral", 1337)

    print("\n" + "=" * 50)
    print("📊 DEMO RESULTS")
    print("=" * 50)

    # Show top hooks
    print("\n🎣 TOP HOOKS:")
    meta = json.loads(Path("videos/demo-viral.metadata.json").read_text())
    hooks = meta["viral"]["variants"]["hooks"][:3]
    for hook in hooks:
        score = hook["score"]
        print(f"  • {hook['text']}")
        print(
            f"    Score: {score['final']:.2f} (heur: {score['heur']:.2f}, llm: {score['llm']:.2f})"
        )

    # Show top titles
    print("\n📝 TOP TITLES:")
    titles = meta["viral"]["variants"]["titles"][:3]
    for title in titles:
        score = title["score"]
        print(f"  • {title['text']}")
        print(
            f"    Score: {score['final']:.2f} (heur: {score['heur']:.2f}, llm: {score['llm']:.2f})"
        )

    # Show thumbnails
    print("\n🖼️ THUMBNAILS:")
    thumbs = meta["viral"]["variants"]["thumbs"]
    for thumb in thumbs:
        print(f"  • {thumb['id']}: {thumb['file']}")

    # Show selections
    selected = meta["viral"]["selected"]
    print("\n✅ SELECTED:")
    print(f"  Hooks: {selected['hook_ids']}")
    print(f"  Title: {selected['title_id']}")
    print(f"  Thumbnail: {selected['thumb_id']}")

    print("\n💡 Next steps:")
    print("  python3 bin/viral/chooser.py --slug demo-viral --list")
    print("  python3 bin/viral/chooser.py --slug demo-viral --interactive")


def demo_chooser():
    """Demonstrate the chooser functionality."""
    print("\n🎛️ CHOOSER DEMO")
    print("=" * 30)

    # List variants
    import subprocess

    result = subprocess.run(
        ["python3", "bin/viral/chooser.py", "--slug", "demo-viral", "--list"],
        capture_output=True,
        text=True,
    )

    print("Available variants:")
    print(result.stdout)

    # Manual selection
    print("Manual selection example:")
    subprocess.run(
        [
            "python3",
            "bin/viral/chooser.py",
            "--slug",
            "demo-viral",
            "--pick-title",
            "title_1",
            "--pick-thumb",
            "thumb_1",
            "--pick-hooks",
            "hook_1,hook_2",
            "--note",
            "Demo selection for testing",
        ]
    )


if __name__ == "__main__":
    demo_viral_lab()
    demo_chooser()
