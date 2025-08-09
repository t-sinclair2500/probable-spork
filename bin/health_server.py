#!/usr/bin/env python3
from flask import Flask, jsonify
import os, json, time
from bin.core import cpu_temp_c, disk_free_gb, load_config, BASE

app = Flask(__name__)

@app.get("/health")
def health():
    cfg = load_config()
    # read last state line
    state_path = os.path.join(BASE, "jobs", "state.jsonl")
    last = {}
    if os.path.exists(state_path):
        with open(state_path,"r",encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
            if lines: last = json.loads(lines[-1])
    return jsonify({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cpu_temp_c": cpu_temp_c(),
        "disk_free_gb": disk_free_gb(BASE),
        "last_state": last,
        "model": cfg.llm.model
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8088)
