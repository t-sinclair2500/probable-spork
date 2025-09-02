#!/usr/bin/env python3
"""
Fixture Preparation Tool for Asset Testing

This tool prepares test fixtures for the asset reuse testing strategy:
- Copies best assets from existing downloads to generic fixture pool
- Generates synthetic assets when no real assets are available
- Ensures idempotent operations with hash-based deduplication
"""

import argparse
import json
import os
import shutil
import sys
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

# Ensure repo root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, sha1_file  # noqa: E402

log = get_logger("prepare_fixtures")


class FixtureManager:
    """Manages test fixture creation and organization"""

    def __init__(self, config):
        self.config = config
        # Handle both dict and config object
        if hasattr(config, "testing"):
            self.testing_cfg = (
                getattr(config.testing, "__dict__", {})
                if hasattr(config.testing, "__dict__")
                else {}
            )
        else:
            self.testing_cfg = (
                config.get("testing", {}) if hasattr(config, "get") else {}
            )
        self.fixture_dir = os.path.join(
            BASE, self.testing_cfg.get("fixture_dir", "assets/fixtures")
        )
        self.generic_dir = os.path.join(self.fixture_dir, "_generic")

        # Ensure directories exist
        os.makedirs(self.generic_dir, exist_ok=True)

    def copy_from_slug(self, slug: str) -> int:
        """Copy best assets from assets/{slug}/ to generic fixture pool"""
        slug_dir = os.path.join(BASE, "assets", slug)
        if not os.path.exists(slug_dir):
            log.error(f"Source slug directory does not exist: {slug_dir}")
            return 0

        license_path = os.path.join(slug_dir, "license.json")
        if not os.path.exists(license_path):
            log.warning(f"No license.json found in {slug_dir}")
            return 0

        # Load license info to find assets
        with open(license_path, "r") as f:
            license_data = json.load(f)

        copied = 0
        existing_hashes = self._get_existing_hashes()

        for file_name in os.listdir(slug_dir):
            if file_name in ["license.json", "sources_used.txt"]:
                continue

            src_path = os.path.join(slug_dir, file_name)
            if not os.path.isfile(src_path):
                continue

            # Check if we already have this asset (by hash)
            file_hash = sha1_file(src_path)
            if file_hash in existing_hashes:
                log.info(
                    f"Asset {file_name} already exists in fixtures (hash: {file_hash[:8]})"
                )
                continue

            # Copy to generic fixtures
            dest_path = os.path.join(self.generic_dir, file_name)
            shutil.copy2(src_path, dest_path)
            log.info(f"Copied {file_name} to generic fixtures")
            copied += 1

        # Update fixtures license file
        self._update_fixtures_license(license_data)

        return copied

    def make_synthetic(self, count: int) -> int:
        """Generate synthetic assets for testing"""
        created = 0
        existing_hashes = self._get_existing_hashes()

        for i in range(count):
            # Create synthetic image
            width, height = 1920, 1080
            colors = [
                (52, 152, 219),  # Blue
                (46, 204, 113),  # Green
                (155, 89, 182),  # Purple
                (241, 196, 15),  # Yellow
                (230, 126, 34),  # Orange
                (231, 76, 60),  # Red
            ]

            color = colors[i % len(colors)]
            img = Image.new("RGB", (width, height), color)
            draw = ImageDraw.Draw(img)

            # Add text overlay
            try:
                # Try to use a system font
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 72)
            except (OSError, IOError):
                # Fallback to default font
                font = ImageFont.load_default()

            text = f"TEST ASSET #{i+1}\n{width}x{height}\nFixture Generated"

            # Calculate text position (centered)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (width - text_width) // 2
            y = (height - text_height) // 2

            # Draw text with outline for visibility
            outline_color = (255, 255, 255) if sum(color) < 400 else (0, 0, 0)
            for adj in range(-2, 3):
                for adj2 in range(-2, 3):
                    draw.text((x + adj, y + adj2), text, font=font, fill=outline_color)
            draw.text((x, y), text, font=font, fill=(255, 255, 255))

            # Save with deterministic name
            filename = f"synthetic_{i+1:03d}_1920x1080.jpg"
            filepath = os.path.join(self.generic_dir, filename)

            # Check if already exists by hash
            if os.path.exists(filepath):
                existing_hash = sha1_file(filepath)
                if existing_hash in existing_hashes:
                    log.info(f"Synthetic asset {filename} already exists")
                    continue

            img.save(filepath, "JPEG", quality=85)
            log.info(f"Created synthetic asset: {filename}")
            created += 1

        return created

    def _get_existing_hashes(self) -> set:
        """Get hashes of all existing fixture files"""
        hashes = set()
        if os.path.exists(self.generic_dir):
            for filename in os.listdir(self.generic_dir):
                if filename.endswith((".jpg", ".jpeg", ".png", ".mp4", ".mov")):
                    filepath = os.path.join(self.generic_dir, filename)
                    try:
                        hashes.add(sha1_file(filepath))
                    except Exception as e:
                        log.warning(f"Failed to hash {filename}: {e}")
        return hashes

    def _update_fixtures_license(self, source_license: Dict):
        """Update or create fixtures license file"""
        fixtures_license_path = os.path.join(self.fixture_dir, "license.json")

        if os.path.exists(fixtures_license_path):
            with open(fixtures_license_path, "r") as f:
                fixtures_license = json.load(f)
        else:
            fixtures_license = {
                "source": "fixtures",
                "created_at": None,
                "assets": [],
                "sources": [],
            }

        # Add source info if not already present
        source_info = {
            "original_slug": source_license.get("slug", "unknown"),
            "providers": list(
                set(
                    asset.get("provider", "unknown")
                    for asset in source_license.get("assets", [])
                )
            ),
            "added_at": source_license.get("created_at"),
        }

        if source_info not in fixtures_license["sources"]:
            fixtures_license["sources"].append(source_info)

        # Update timestamp
        import time

        fixtures_license["created_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )

        with open(fixtures_license_path, "w") as f:
            json.dump(fixtures_license, f, indent=2)

        log.info(f"Updated fixtures license: {fixtures_license_path}")

    def list_fixtures(self) -> Dict[str, int]:
        """List current fixture inventory"""
        inventory = {"images": 0, "videos": 0, "total_size_mb": 0}

        if not os.path.exists(self.generic_dir):
            return inventory

        total_size = 0
        for filename in os.listdir(self.generic_dir):
            filepath = os.path.join(self.generic_dir, filename)
            if not os.path.isfile(filepath):
                continue

            total_size += os.path.getsize(filepath)

            if filename.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                inventory["images"] += 1
            elif filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
                inventory["videos"] += 1

        inventory["total_size_mb"] = round(total_size / (1024 * 1024), 2)
        return inventory


def main():
    parser = argparse.ArgumentParser(
        description="Prepare test fixtures for asset testing"
    )
    parser.add_argument(
        "--from-slug", type=str, help="Copy assets from specific slug directory"
    )
    parser.add_argument(
        "--make-synthetic", type=int, help="Create N synthetic test images"
    )
    parser.add_argument(
        "--list", action="store_true", help="List current fixture inventory"
    )

    args = parser.parse_args()

    if not any([args.from_slug, args.make_synthetic, args.list]):
        parser.print_help()
        return 1

    try:
        config = load_config()
        manager = FixtureManager(config)

        if args.list:
            inventory = manager.list_fixtures()
            print("Fixture Inventory:")
            print(f"  Images: {inventory['images']}")
            print(f"  Videos: {inventory['videos']}")
            print(f"  Total Size: {inventory['total_size_mb']} MB")
            print(f"  Location: {manager.generic_dir}")

        if args.from_slug:
            copied = manager.copy_from_slug(args.from_slug)
            print(f"Copied {copied} assets from slug '{args.from_slug}' to fixtures")

        if args.make_synthetic:
            created = manager.make_synthetic(args.make_synthetic)
            print(f"Created {created} synthetic test assets")

        return 0

    except Exception as e:
        log.error(f"Fixture preparation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
