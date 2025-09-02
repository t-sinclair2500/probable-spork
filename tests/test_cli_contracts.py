from bin.cli.args import build_common_parser


def test_cli_flags_present():
    ap = build_common_parser()
    args = ap.parse_args(
        [
            "--slug",
            "s1",
            "--mode",
            "reuse",
            "--dry-run",
            "--force",
            "--profile",
            "m2_8gb_optimized",
        ]
    )
    assert args.slug == "s1"
    assert args.mode == "reuse"
    assert args.force
    assert args.profile == "m2_8gb_optimized"
