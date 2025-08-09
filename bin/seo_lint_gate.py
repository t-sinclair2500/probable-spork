#!/usr/bin/env python3
import json
import sys

from bin.seo_lint import lint as seo_lint


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: seo_lint_gate.py <title> <meta_desc> [--allow-fail]"}))
        sys.exit(2)
    title = sys.argv[1]
    meta = sys.argv[2]
    allow_fail = "--allow-fail" in sys.argv[3:]
    issues = seo_lint(title, meta)
    if issues and not allow_fail:
        print(json.dumps({"ok": False, "issues": issues}))
        sys.exit(1)
    print(json.dumps({"ok": True, "issues": issues}))


if __name__ == "__main__":
    main()
