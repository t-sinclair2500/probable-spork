#!/usr/bin/env python3
"""
Viral Growth Engine - Main Runner

Generates hooks, titles, and thumbnails for content optimization.
"""

import argparse
import json
import sys
import time

from pathlib import Path

# Ensure repository root is on sys.path (needed for `import bin.*`)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bin.viral import hooks, thumbnails, titles


def _load_meta(slug: str) -> dict:
    """Load metadata for a slug."""
    p = Path("videos") / f"{slug}.metadata.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    else:
        return {"slug": slug}


def _save_meta(slug: str, meta: dict):
    """Save metadata for a slug."""
    p = Path("videos") / f"{slug}.metadata.json"
    p.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _load_brief(slug: str) -> dict:
    """Load brief data for a slug."""
    # Try to load from brief file
    brief_path = Path("conf") / "brief.yaml"
    if brief_path.exists():
        try:
            import yaml

            with open(brief_path, "r") as f:
                return yaml.safe_load(f)
        except Exception:
            pass

    # Fallback to basic brief
    return {
        "title": slug.replace("-", " ").title(),
        "keywords": [slug],
        "benefit": "better results",
        "year": time.strftime("%Y"),
    }


def run_viral_lab(slug: str, seed: int = None) -> dict:
    """Run the complete viral lab for a slug."""
    print(f"🎯 Running Viral Lab for slug: {slug}")

    # Load configuration
    try:
        import yaml

        with open("conf/viral.yaml", "r") as f:
            viral_cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Could not load viral.yaml: {e}")
        viral_cfg = {}

    # Use seed from config or current time
    if seed is None:
        seed = viral_cfg.get("seed", int(time.time()))

    print(f"🌱 Using seed: {seed}")

    # Load brief
    brief = _load_brief(slug)
    print(f"📋 Brief: {brief.get('title', 'Untitled')}")

    # Generate hooks
    print("\n🎣 Generating hooks...")
    hooks_result = hooks.score_and_select_hooks(slug, brief, seed)
    print(
        f"✅ Generated {len(hooks_result['variants'])} hooks, selected: {hooks_result['selected']}"
    )

    # Generate titles
    print("\n📝 Generating titles...")
    titles_result = titles.generate_titles(slug, brief, seed)
    print(
        f"✅ Generated {len(titles_result['variants'])} titles, selected: {titles_result['selected']}"
    )

    # Get selected texts for thumbnails
    selected_hook = next(
        (h for h in hooks_result["variants"] if h["id"] == hooks_result["selected"][0]),
        None,
    )
    selected_title = next(
        (t for t in titles_result["variants"] if t["id"] == titles_result["selected"]),
        None,
    )

    hook_text = selected_hook["text"] if selected_hook else "Amazing Content"
    title_text = selected_title["text"] if selected_title else "Great Title"

    # Generate thumbnails
    print("\n🖼️ Generating thumbnails...")
    thumbs_result = thumbnails.generate_thumbnails(slug, title_text, hook_text)
    print(f"✅ Generated {len(thumbs_result)} thumbnails")

    # Prepare metadata update
    meta = _load_meta(slug)
    viral = meta.setdefault("viral", {})
    viral["variants"] = {
        "hooks": hooks_result["variants"],
        "titles": titles_result["variants"],
        "thumbs": thumbs_result,
    }
    viral["selected"] = {
        "hook_ids": hooks_result["selected"],
        "title_id": titles_result["selected"],
        "thumb_id": thumbs_result[0]["id"] if thumbs_result else None,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seed": seed,
    }

    # Save metadata
    _save_meta(slug, meta)

    print("\n🎉 Viral Lab complete!")
    print(f"📁 Metadata saved to: videos/{slug}.metadata.json")
    print(f"🖼️ Thumbnails saved to: videos/{slug}/thumbs/")

    return {
        "slug": slug,
        "hooks": len(hooks_result["variants"]),
        "titles": len(titles_result["variants"]),
        "thumbnails": len(thumbs_result),
        "selected_hooks": hooks_result["selected"],
        "selected_title": titles_result["selected"],
        "selected_thumbnail": thumbs_result[0]["id"] if thumbs_result else None,
    }


def main():
    """Main CLI entry point."""
    ap = argparse.ArgumentParser(description="Viral Growth Engine")
    ap.add_argument("--slug", required=True, help="Content slug")
    ap.add_argument("--seed", type=int, help="Random seed for deterministic generation")
    ap.add_argument("--list", action="store_true", help="List generated variants")
    args = ap.parse_args()

    if args.list:
        # List existing variants
        meta = _load_meta(args.slug)
        viral = meta.get("viral", {})
        variants = viral.get("variants", {})

        if "hooks" in variants:
            print(f"\n=== HOOKS ({len(variants['hooks'])}) ===")
            for h in variants["hooks"]:
                score = h.get("score", {})
                print(f"{h['id']}: {h['text']} (final: {score.get('final', 0):.2f})")

        if "titles" in variants:
            print(f"\n=== TITLES ({len(variants['titles'])}) ===")
            for t in variants["titles"]:
                score = t.get("score", {})
                print(f"{t['id']}: {t['text']} (final: {score.get('final', 0):.2f})")

        if "thumbs" in variants:
            print(f"\n=== THUMBNAILS ({len(variants['thumbs'])}) ===")
            for th in variants["thumbs"]:
                print(f"{th['id']}: {th['file']}")

        selected = viral.get("selected", {})
        if selected:
            print("\n=== SELECTED ===")
            print(f"Hooks: {selected.get('hook_ids', [])}")
            print(f"Title: {selected.get('title_id', 'None')}")
            print(f"Thumbnail: {selected.get('thumb_id', 'None')}")

        return

    # Run viral lab
    result = run_viral_lab(args.slug, args.seed)

    print("\n📊 Summary:")
    print(
        f"  Hooks: {result['hooks']} generated, {len(result['selected_hooks'])} selected"
    )
    print(f"  Titles: {result['titles']} generated, 1 selected")
    print(f"  Thumbnails: {result['thumbnails']} generated")

    print("\n💡 Next steps:")
    print(f"  python3 bin/viral/chooser.py --slug {args.slug} --list")
    print(f"  python3 bin/viral/chooser.py --slug {args.slug} --interactive")


if __name__ == "__main__":
    main()
