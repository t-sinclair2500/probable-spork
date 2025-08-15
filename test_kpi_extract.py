#!/usr/bin/env python3
"""Test script to extract KPI values from pacing report"""

import json
import sys

if len(sys.argv) < 2:
    print("Usage: python test_kpi_extract.py <slug>")
    sys.exit(1)

slug = sys.argv[1]
report_path = f"runs/{slug}/pacing_report.json"

try:
    with open(report_path, 'r') as f:
        data = json.load(f)
    
    # Extract KPI metrics
    kpi_metrics = data.get("kpi_metrics", data)
    
    print(f"words_per_sec: {kpi_metrics.get('words_per_sec')}")
    print(f"avg_scene_s: {kpi_metrics.get('avg_scene_s')}")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
