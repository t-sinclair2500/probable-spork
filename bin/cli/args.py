import argparse


def build_common_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--slug", required=False, help="Slug identifier (required for most steps)")
    ap.add_argument("--brief", default=None, help="Path to brief YAML/MD")
    ap.add_argument("--brief-data", default=None, help="Inline JSON for brief overrides")
    ap.add_argument("--mode", choices=["reuse", "live"], default=None, help="Research mode override")
    ap.add_argument("--from-step", default=None, help="Start from step name")
    ap.add_argument("--dry-run", action="store_true", help="Do not execute subprocesses")
    ap.add_argument("--force", action="store_true", help="Ignore idempotence and re-run steps")
    ap.add_argument("--yt-only", action="store_true", help="Only run assembly/publish (no ingestion)")
    ap.add_argument("--profile", choices=["m2_8gb_optimized", "pi_8gb"], default=None, help="Config profile overlay")
    return ap

