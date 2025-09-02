from __future__ import annotations

import json

from pathlib import Path


def format_qa_summary(qa_json_path: str | None) -> str:
    if not qa_json_path or not Path(qa_json_path).exists():
        return "QA: no report yet."
    try:
        data = json.loads(Path(qa_json_path).read_text(encoding="utf-8"))
    except Exception as e:
        return f"QA: failed to read report: {e}"
    lines = [f"QA results for slug: {data.get('slug','?')}"]
    for r in data.get("results", []):
        lines.append(f"- {r['gate']}: {r['status']}")
    return "\n".join(lines)



