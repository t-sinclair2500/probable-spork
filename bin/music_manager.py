#!/usr/bin/env python3
"""
Music Library Management CLI

Command-line interface for managing the music library, importing tracks,
viewing statistics, and testing the music selection system.
"""

import argparse
import os
import sys

from pathlib import Path

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger, load_config
from bin.music_integration import MusicIntegrationManager

log = get_logger("music_manager")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Music Library Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import music from a directory
  python bin/music_manager.py import --source /path/to/music --license "royalty-free"
  
  # View library statistics
  python bin/music_manager.py stats
  
  # Validate library integrity
  python bin/music_manager.py validate
  
  # Test music selection
  python bin/music_manager.py test --script scripts/test.txt --tone conversational --duration 30
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import music tracks")
    import_parser.add_argument(
        "--source", required=True, help="Source directory containing music files"
    )
    import_parser.add_argument(
        "--license", default="unknown", help="License type for imported tracks"
    )
    import_parser.add_argument(
        "--source-name", default="local", help="Source name for imported tracks"
    )

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="View music library statistics")

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate music library integrity"
    )

    # Test command
    test_parser = subparsers.add_parser("test", help="Test music selection system")
    test_parser.add_argument(
        "--script", required=True, help="Path to script file for content analysis"
    )
    test_parser.add_argument("--tone", default="conversational", help="Video tone")
    test_parser.add_argument(
        "--duration", type=float, default=30.0, help="Video duration in seconds"
    )
    test_parser.add_argument(
        "--pacing-wpm", type=int, default=165, help="Words per minute pacing"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List all tracks in library")
    list_parser.add_argument("--mood", help="Filter by mood")
    list_parser.add_argument("--bpm-min", type=int, help="Minimum BPM")
    list_parser.add_argument("--bpm-max", type=int, help="Maximum BPM")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a track from library")
    remove_parser.add_argument("track_id", help="Track ID to remove")

    # Setup command
    setup_parser = subparsers.add_parser(
        "setup", help="Setup music library with sample tracks"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize music manager
    try:
        config = load_config()
        manager = MusicIntegrationManager(config)
    except Exception as e:
        log.error(f"Failed to initialize music manager: {e}")
        return 1

    # Execute command
    try:
        if args.command == "import":
            return handle_import(manager, args)
        elif args.command == "stats":
            return handle_stats(manager)
        elif args.command == "validate":
            return handle_validate(manager)
        elif args.command == "test":
            return handle_test(manager, args)
        elif args.command == "list":
            return handle_list(manager, args)
        elif args.command == "remove":
            return handle_remove(manager, args)
        elif args.command == "setup":
            return handle_setup(manager)
        else:
            log.error(f"Unknown command: {args.command}")
            return 1

    except Exception as e:
        log.error(f"Command failed: {e}")
        return 1


def handle_import(manager: MusicIntegrationManager, args: argparse.Namespace) -> int:
    """Handle music import command."""
    source_dir = args.source
    if not os.path.exists(source_dir):
        log.error(f"Source directory not found: {source_dir}")
        return 1

    license_info = {"license": args.license, "source": args.source_name}

    log.info(f"Importing music from: {source_dir}")
    imported_count = manager.create_music_library_from_directory(
        source_dir, license_info
    )

    if imported_count > 0:
        log.info(f"Successfully imported {imported_count} tracks")
        return 0
    else:
        log.warning("No tracks were imported")
        return 1


def handle_stats(manager: MusicIntegrationManager) -> int:
    """Handle statistics command."""
    stats = manager.get_music_statistics()

    if "error" in stats:
        log.error(f"Failed to get statistics: {stats['error']}")
        return 1

    print("\n=== Music Library Statistics ===")
    print(f"Total Tracks: {stats['total_tracks']}")
    print(f"Average Duration: {stats['avg_duration']:.1f} seconds")

    if stats["moods"]:
        print("\nMoods:")
        for mood, count in sorted(stats["moods"].items()):
            print(f"  {mood}: {count}")

    if stats["bpm_ranges"]:
        print("\nBPM Ranges:")
        for range_name, count in stats["bpm_ranges"].items():
            print(f"  {range_name}: {count}")

    return 0


def handle_validate(manager: MusicIntegrationManager) -> int:
    """Handle validation command."""
    validation = manager.validate_music_library()

    if "error" in validation:
        log.error(f"Validation failed: {validation['error']}")
        return 1

    print("\n=== Music Library Validation ===")
    print(f"Total Tracks: {validation['total_tracks']}")
    print(f"Valid Tracks: {validation['valid_tracks']}")
    print(f"Health Score: {validation['health_score']:.1f}%")

    if validation["issues"]:
        print(f"\nIssues Found ({len(validation['issues'])}):")
        for issue in validation["issues"]:
            print(f"  - {issue}")
        return 1
    else:
        print("\n✓ No issues found - library is healthy!")
        return 0


def handle_test(manager: MusicIntegrationManager, args: argparse.Namespace) -> int:
    """Handle test command."""
    script_path = args.script
    if not os.path.exists(script_path):
        log.error(f"Script file not found: {script_path}")
        return 1

    # Read script content
    with open(script_path, "r") as f:
        script_text = f.read()

    # Create video metadata
    video_metadata = {
        "tone": args.tone,
        "duration": args.duration,
        "pacing_wpm": args.pacing_wpm,
    }

    print("\n=== Testing Music Selection ===")
    print(f"Script: {script_path}")
    print(f"Tone: {args.tone}")
    print(f"Duration: {args.duration}s")
    print(f"Pacing: {args.pacing_wpm} WPM")
    print(f"Script Preview: {script_text[:100]}...")

    # Test music selection
    try:
        selected_track = manager.agent.select_music_for_video(
            script_text, args.tone, args.duration, args.pacing_wpm
        )

        if selected_track:
            print("\n✓ Music Selected:")
            print(f"  Title: {selected_track.title}")
            print(f"  Artist: {selected_track.artist}")
            print(f"  BPM: {selected_track.bpm}")
            print(f"  Mood: {selected_track.mood}")
            print(f"  Duration: {selected_track.duration:.1f}s")
            return 0
        else:
            print("\n✗ No suitable music track found")
            return 1

    except Exception as e:
        log.error(f"Music selection test failed: {e}")
        return 1


def handle_list(manager: MusicIntegrationManager, args: argparse.Namespace) -> int:
    """Handle list command."""
    tracks = manager.library.list_tracks()

    if not tracks:
        print("No tracks in library")
        return 0

    # Apply filters
    if args.mood:
        tracks = [t for t in tracks if t.get("mood", "").lower() == args.mood.lower()]

    if args.bpm_min is not None:
        tracks = [t for t in tracks if t.get("bpm", 0) >= args.bpm_min]

    if args.bpm_max is not None:
        tracks = [t for t in tracks if t.get("bpm", 0) <= args.bpm_max]

    print(f"\n=== Music Library ({len(tracks)} tracks) ===")

    for track in tracks:
        print(f"\n{track['title']} - {track['artist']}")
        print(f"  File: {track['file_path']}")
        print(f"  BPM: {track.get('bpm', 'Unknown')}")
        print(f"  Mood: {track.get('mood', 'Unknown')}")
        print(f"  Genre: {track.get('genre', 'Unknown')}")
        print(f"  Duration: {track.get('duration', 0):.1f}s")
        print(f"  License: {track.get('license', 'Unknown')}")

    return 0


def handle_remove(manager: MusicIntegrationManager, args: argparse.Namespace) -> int:
    """Handle remove command."""
    track_id = args.track_id

    if manager.library.remove_track(track_id):
        log.info(f"Successfully removed track: {track_id}")
        return 0
    else:
        log.error(f"Failed to remove track: {track_id}")
        return 1


def handle_setup(manager: MusicIntegrationManager) -> int:
    """Handle setup command."""
    print("\n=== Setting Up Music Library ===")

    # Create music directory
    music_dir = Path("assets/music")
    music_dir.mkdir(parents=True, exist_ok=True)

    # Create sample tracks (these would be placeholder files)
    sample_tracks = [
        {
            "file_path": "assets/music/sample_energetic.mp3",
            "title": "Energetic Uplift",
            "artist": "Sample Artist",
            "bpm": 130,
            "mood": "energetic",
            "genre": "electronic",
            "license": "royalty-free",
            "source": "sample",
        },
        {
            "file_path": "assets/music/sample_calm.mp3",
            "title": "Calm Reflection",
            "artist": "Sample Artist",
            "bpm": 70,
            "mood": "calm",
            "genre": "ambient",
            "license": "royalty-free",
            "source": "sample",
        },
    ]

    print("Creating sample music library structure...")
    print("Note: This creates metadata only. You'll need to add actual music files.")

    for track_info in sample_tracks:
        # Create placeholder file if it doesn't exist
        file_path = Path(track_info["file_path"])
        if not file_path.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Create a minimal MP3 file (1 second of silence)
            try:
                import subprocess

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-t",
                    "1",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    str(file_path),
                ]
                subprocess.run(cmd, capture_output=True, check=False)
                print(f"  Created placeholder: {file_path}")
            except Exception:
                print(f"  Warning: Could not create placeholder for {file_path}")

        # Add to library
        try:
            track_id = manager.library.add_track(**track_info)
            if track_id:
                print(f"  Added to library: {track_info['title']}")
        except Exception as e:
            print(f"  Warning: Could not add {track_info['title']}: {e}")

    print("\n✓ Music library setup complete!")
    print("To add your own music:")
    print("  1. Place MP3/WAV files in assets/music/")
    print(
        "  2. Run: python bin/music_manager.py import --source assets/music --license 'your-license'"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
