#!/usr/bin/env python3
"""
Viral Growth Engine Demo - Shorts & SEO Packaging

Demonstrates the complete viral growth pipeline including shorts generation and SEO packaging.
"""

import json
import sys

from pathlib import Path

# Add the bin directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_sample_metadata():
    """Create sample metadata for demonstration."""
    return {
        "title": "AI Side Hustles That Actually Work",
        "description": "Discover proven AI side hustles that can generate real income in 2025.",
        "scene_map": [
            {
                "id": "s1",
                "start_s": 0.0,
                "actual_duration_s": 25.0,
                "speech": "Why are so many people struggling to make money with AI?",
                "title": "The AI Money Problem",
            },
            {
                "id": "s2",
                "start_s": 25.0,
                "actual_duration_s": 30.0,
                "speech": "Here are 3 proven strategies that work.",
                "title": "3 Proven Strategies",
            },
            {
                "id": "s3",
                "start_s": 55.0,
                "actual_duration_s": 20.0,
                "speech": "Let me show you exactly how to get started.",
                "title": "Getting Started",
            },
        ],
        "viral": {
            "selected": {"hook_ids": ["hook_1", "hook_2"]},
            "variants": {
                "hooks": [
                    {
                        "id": "hook_1",
                        "text": "Why AI side hustles fail (and how to fix it)",
                        "score": {"final": 8.5},
                    },
                    {
                        "id": "hook_2",
                        "text": "3 AI side hustles that actually work",
                        "score": {"final": 8.2},
                    },
                ],
                "titles": [
                    {
                        "id": "title_1",
                        "text": "AI Side Hustles That Actually Work",
                        "score": {"final": 8.8},
                    }
                ],
            },
        },
    }


def demo_shorts_generation():
    """Demonstrate shorts generation."""
    print("🎬 SHORTS GENERATION DEMO")
    print("=" * 40)

    # Create sample metadata
    meta = create_sample_metadata()
    slug = "demo-shorts"

    # Save sample metadata
    meta_path = Path("videos") / f"{slug}.metadata.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"📋 Created sample metadata for: {slug}")
    print(f"🎯 Scenes: {len(meta['scene_map'])}")
    print(f"🎣 Selected hooks: {len(meta['viral']['selected']['hook_ids'])}")

    # Test segment selection
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from bin.utils.config import _read_yaml
    from bin.viral.shorts import _pick_segments

    cfg = _read_yaml("conf/shorts.yaml")
    picks = _pick_segments(slug, cfg)

    print("\n📊 Selected segments:")
    for i, (start, end, rationale) in enumerate(picks, 1):
        duration = end - start
        print(f"  {i}. {start:.1f}s - {end:.1f}s ({duration:.1f}s) - {rationale}")

    print("\n💡 Next steps:")
    print(f"  python3 bin/viral/shorts.py --slug {slug}")
    print(f"  (Requires: videos/{slug}_cc.mp4, voiceovers/{slug}.srt)")


def demo_seo_packaging():
    """Demonstrate SEO packaging."""
    print("\n📝 SEO PACKAGING DEMO")
    print("=" * 40)

    # Create sample brief
    brief = {
        "title": "AI Side Hustles That Actually Work",
        "keywords": ["ai", "automation", "income", "side hustle", "passive income"],
        "summary": "Discover proven AI side hustles that can generate real income in 2025.",
        "cta": "Subscribe for more AI insights",
    }

    slug = "demo-seo"
    brief_path = Path("conf/briefs") / f"{slug}.yaml"
    brief_path.parent.mkdir(parents=True, exist_ok=True)

    import yaml

    brief_path.write_text(yaml.dump(brief, default_flow_style=False), encoding="utf-8")

    # Create sample references
    refs = [
        {"url": "https://openai.com/blog/", "title": "OpenAI Blog"},
        {"url": "https://www.anthropic.com/", "title": "Anthropic Research"},
    ]

    refs_path = Path("data") / slug / "references.json"
    refs_path.parent.mkdir(parents=True, exist_ok=True)
    refs_path.write_text(json.dumps(refs, indent=2), encoding="utf-8")

    print(f"📋 Created sample brief and references for: {slug}")
    print(f"🎯 Keywords: {', '.join(brief['keywords'])}")
    print(f"🔗 References: {len(refs)}")

    # Test SEO generation
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from bin.packaging.seo_packager import _format_chapters, _keywords

    meta = create_sample_metadata()
    chapters = _format_chapters(
        meta["scene_map"], {"merge_below_s": 6, "max_first_chapter_start_s": 5}
    )
    keywords = _keywords(meta, brief)

    print("\n📊 Generated chapters:")
    for timecode, title in chapters:
        print(f"  {timecode} - {title}")

    print(f"\n🏷️ Generated keywords: {', '.join(keywords[:10])}")

    print("\n💡 Next steps:")
    print(f"  python3 bin/packaging/seo_packager.py --slug {slug}")
    print(f"  python3 bin/packaging/end_screens.py --slug {slug}")


def demo_integration():
    """Demonstrate full integration."""
    print("\n🔗 INTEGRATION DEMO")
    print("=" * 40)

    print("Pipeline integration:")
    print("  1. viral_lab → generates hooks/titles/thumbnails")
    print("  2. shorts_lab → creates 9:16 clips with captions")
    print("  3. seo_packaging → generates description/tags/chapters")
    print("  4. end_screens → creates CTA overlays")

    print("\n🎯 Configuration files:")
    print("  conf/shorts.yaml - Shorts generation settings")
    print("  conf/seo.yaml - SEO packaging templates")

    print("\n📁 Output structure:")
    print("  videos/<slug>/shorts/ - Generated vertical clips")
    print("  videos/<slug>.metadata.json - Updated with SEO data")
    print("  assets/generated/<slug>/ - End screens and CTAs")

    print("\n🚀 Run full pipeline:")
    print("  python3 bin/run_pipeline.py --slug demo-viral")


if __name__ == "__main__":
    demo_shorts_generation()
    demo_seo_packaging()
    demo_integration()
