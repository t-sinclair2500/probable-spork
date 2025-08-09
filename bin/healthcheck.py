#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import time

import sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from bin.core import BASE, load_config


def cpu_temp():
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True).strip()
        return out
    except Exception:
        return "unknown"


def disk_free():
    total, used, free = shutil.disk_usage(BASE)
    return {"total_gb": round(total / 1e9, 2), "free_gb": round(free / 1e9, 2)}


def main():
    cfg = load_global_config()
    rep = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cpu_temp": cpu_temp(),
        "disk": disk_free(),
        "model": cfg["llm"]["model"],
    }
    print(json.dumps(rep))


if __name__ == "__main__":
    main()
