from __future__ import annotations

import argparse
import json
import time

from pathlib import Path


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


def _print_variants(variants: list, variant_type: str):
    """Print variants in a readable format."""
    print(f"\n=== {variant_type.upper()} VARIANTS ===")
    for item in variants:
        score_info = ""
        if "score" in item:
            score = item["score"]
            score_info = f" (heur: {score.get('heur', 0):.2f}, llm: {score.get('llm', 0):.2f}, final: {score.get('final', 0):.2f})"
        print(f"{item['id']}: {item['text']}{score_info}")


def _print_thumbnails(thumbs: list):
    """Print thumbnail variants."""
    print("\n=== THUMBNAIL VARIANTS ===")
    for item in thumbs:
        print(f"{item['id']}: {item['file']}")


def main():
    """Main CLI entry point."""
    ap = argparse.ArgumentParser(description="Choose viral variants for content")
    ap.add_argument("--slug", required=True, help="Content slug")
    ap.add_argument("--pick-title", help="title_id")
    ap.add_argument("--pick-thumb", help="thumb_id")
    ap.add_argument("--pick-hooks", help="comma-separated hook ids e.g., hook_1,hook_3")
    ap.add_argument("--note", default="", help="rationale/notes for selection")
    ap.add_argument("--list", action="store_true", help="List available variants")
    ap.add_argument(
        "--interactive", action="store_true", help="Interactive selection mode"
    )
    args = ap.parse_args()

    meta = _load_meta(args.slug)
    viral = meta.setdefault("viral", {})
    variants = viral.setdefault("variants", {})
    sel = viral.setdefault("selected", {})

    # List mode
    if args.list:
        if "hooks" in variants:
            _print_variants(variants["hooks"], "hooks")
        if "titles" in variants:
            _print_variants(variants["titles"], "titles")
        if "thumbs" in variants:
            _print_thumbnails(variants["thumbs"])
        return

    # Interactive mode
    if args.interactive:
        print(f"Interactive selection for slug: {args.slug}")

        # Show current selections
        print("\nCurrent selections:")
        print(f"  Hooks: {sel.get('hook_ids', [])}")
        print(f"  Title: {sel.get('title_id', 'None')}")
        print(f"  Thumbnail: {sel.get('thumb_id', 'None')}")

        # Show available variants
        if "hooks" in variants:
            _print_variants(variants["hooks"], "hooks")
            hook_input = input(
                "\nEnter hook IDs (comma-separated, e.g., hook_1,hook_3): "
            ).strip()
            if hook_input:
                sel["hook_ids"] = [
                    h.strip() for h in hook_input.split(",") if h.strip()
                ]

        if "titles" in variants:
            _print_variants(variants["titles"], "titles")
            title_input = input("\nEnter title ID: ").strip()
            if title_input:
                sel["title_id"] = title_input

        if "thumbs" in variants:
            _print_thumbnails(variants["thumbs"])
            thumb_input = input("\nEnter thumbnail ID: ").strip()
            if thumb_input:
                sel["thumb_id"] = thumb_input

        note_input = input("\nEnter selection rationale (optional): ").strip()
        if note_input:
            sel["reason"] = note_input

        sel["selected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        sel["operator"] = "interactive"

        _save_meta(args.slug, meta)
        print(f"\n✅ Selections updated for slug={args.slug}")
        return

    # Command-line mode
    if args.pick_title:
        sel["title_id"] = args.pick_title
    if args.pick_thumb:
        sel["thumb_id"] = args.pick_thumb
    if args.pick_hooks:
        sel["hook_ids"] = [h.strip() for h in args.pick_hooks.split(",") if h.strip()]
    if args.note:
        sel["reason"] = args.note

    # Add metadata
    sel["selected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    sel["operator"] = "cli"

    _save_meta(args.slug, meta)
    print(f"✅ Selections updated for slug={args.slug}")


if __name__ == "__main__":
    main()
