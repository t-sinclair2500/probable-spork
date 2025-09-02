#!/usr/bin/env python3
"""
Test script for Quality Gates system

This script creates sample data and runs the QA gates to demonstrate
the acceptance harness functionality.
"""

import json
import os

from pathlib import Path


def create_test_data(slug: str):
    """Create sample test data for QA gates."""

    # Create directories
    Path("scripts").mkdir(exist_ok=True)
    Path("videos").mkdir(exist_ok=True)
    Path("voiceovers").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    Path(f"data/{slug}").mkdir(exist_ok=True)
    Path("scenescripts").mkdir(exist_ok=True)

    # Create sample script
    script_content = """This is a sample script for testing the quality gates system.

It contains a call to action: subscribe to our channel for more content like this.

The script should have proper pacing and no banned tokens like [CITATION NEEDED].

This content is sponsored by our partners and contains affiliate links.
"""

    with open(f"scripts/{slug}.txt", "w") as f:
        f.write(script_content)

    # Create sample video metadata
    video_meta = {
        "title": f"Test Video for {slug}",
        "description": "This is a test video with proper disclosure #ad and affiliate links with UTM tracking: https://example.com?utm_source=youtube&utm_medium=video&utm_campaign=test",
        "script": script_content,
        "scene_map": [
            {"planned_duration_s": 10.0, "actual_duration_s": 10.2},
            {"planned_duration_s": 15.0, "actual_duration_s": 14.8},
        ],
    }

    with open(f"videos/{slug}.metadata.json", "w") as f:
        json.dump(video_meta, f, indent=2)

    # Create sample grounded beats
    grounded_beats = [
        {
            "beat": "Introduction",
            "is_factual": True,
            "citations": ["https://example.com/source1"],
        },
        {
            "beat": "Main content",
            "is_factual": True,
            "citations": ["https://example.com/source2", "https://example.com/source3"],
        },
    ]

    with open(f"data/{slug}/grounded_beats.json", "w") as f:
        json.dump(grounded_beats, f, indent=2)

    # Create sample scenescript
    scenescript = {
        "scenes": [
            {
                "id": "scene1",
                "elements": [
                    {"type": "text", "color": "#FFFFFF", "bbox": [0.1, 0.1, 0.8, 0.2]}
                ],
            }
        ]
    }

    with open(f"scenescripts/{slug}.json", "w") as f:
        json.dump(scenescript, f, indent=2)

    print(f"Created test data for slug: {slug}")


def main():
    """Main test function."""
    test_slug = "qa-test-demo"

    print("Creating test data...")
    create_test_data(test_slug)

    print("\nRunning QA gates...")
    os.system(f"python3 bin/qa/run_gates.py --slug {test_slug}")

    print("\nQA Report:")
    report_path = f"reports/{test_slug}/qa_report.txt"
    if Path(report_path).exists():
        with open(report_path, "r") as f:
            print(f.read())

    print(
        "\nNote: Audio and video gates will still fail because actual media files are not created."
    )
    print(
        "This is expected behavior - the QA system correctly identifies missing media files."
    )


if __name__ == "__main__":
    main()
