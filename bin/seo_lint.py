#!/usr/bin/env python3
import json
import re
import sys

from bin.core import slugify


def lint(title: str, meta_desc: str):
    issues = []
    if len(title) > 65:
        issues.append("Title >65 chars")
    if len(meta_desc) > 160:
        issues.append("Meta description >160 chars")
    if not re.match(r"^[a-z0-9-]+$", slugify(title)):
        issues.append("Slug contains invalid chars after slugify")
    return issues


if __name__ == "__main__":
    title = sys.argv[1] if len(sys.argv) > 1 else "Example Post Title"
    md = sys.argv[2] if len(sys.argv) > 2 else "Short description up to 160 chars."
    print(json.dumps(lint(title, md)))
