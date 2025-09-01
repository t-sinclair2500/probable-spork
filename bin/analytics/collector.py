from __future__ import annotations
import json
import time
from pathlib import Path
from collections import Counter


def collect(window_seconds: int = 7 * 24 * 3600) -> dict:
    p = Path("jobs/state.jsonl")
    now = time.time()
    counts = Counter()
    steps = Counter()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            counts[rec.get("status", "UNKNOWN")] += 1
            steps[rec.get("step", "?")] += 1
    out = {
        "status_counts": dict(counts),
        "step_counts": dict(steps),
        "generated_at": int(now),
    }
    outp = Path("data/analytics/recent.json")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))

