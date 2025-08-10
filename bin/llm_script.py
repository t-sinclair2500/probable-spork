#!/usr/bin/env python3
import json
import os
import re
import time

import requests
import sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from bin.core import BASE, load_config, log_state, single_lock


def call_ollama(prompt, cfg):
    url = cfg.llm.endpoint
    model = cfg.llm.model
    payload = {"model": model, "prompt": prompt, "stream": False}
    r = requests.post(url, json=payload, timeout=1800)
    r.raise_for_status()
    return r.json().get("response", "")


def main(brief=None):
    cfg = load_config()
    os.makedirs(os.path.join(BASE, "scripts"), exist_ok=True)
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("llm_script", "START", f"brief={brief_title}")
        print(f"Running with brief: {brief_title}")
    else:
        log_state("llm_script", "START", "brief=none")
        print("Running without brief - using default behavior")
    
    # Pick the newest outline
    outlines = [p for p in os.listdir(os.path.join(BASE, "scripts")) if p.endswith(".outline.json")]
    if not outlines:
        log_state("llm_script", "SKIP", "no outlines")
        print("No outlines")
        return
    outlines.sort(reverse=True)
    opath = os.path.join(BASE, "scripts", outlines[0])
    data = json.load(open(opath, "r", encoding="utf-8"))
    
    with open(os.path.join(BASE, "prompts", "script_writer.txt"), "r", encoding="utf-8") as f:
        template = f.read()
    
    # Use brief settings if available, otherwise fall back to config defaults
    if brief:
        tone = brief.get('tone', cfg.pipeline.tone)
        target_len_sec = brief.get('video', {}).get('target_length_max', cfg.pipeline.video_length_seconds)
    else:
        tone = cfg.pipeline.tone
        target_len_sec = cfg.pipeline.video_length_seconds
    
    # Simple prompt: feed outline JSON and instructions
    prompt = (
        "OUTLINE:\n"
        + json.dumps(data)
        + "\n\n"
        + template
        + f"\nTone: {tone}. Target length (sec): {target_len_sec}. Return plain text only."
    )
    
    # Enhance prompt with brief context if available
    if brief:
        brief_context = f"\nBRIEF CONTEXT:\nTitle: {brief.get('title', 'N/A')}\nAudience: {', '.join(brief.get('audience', []))}\nKeywords: {', '.join(brief.get('keywords_include', []))}"
        prompt = prompt + brief_context
    
    try:
        text = call_ollama(prompt, cfg)
    except Exception:
        # Fallback: synthesize a simple script from outline beats
        lines = []
        title = (data.get("title_options") or ["Untitled"])[0]
        lines.append(f"Title: {title}")
        for sec in data.get("sections", []):
            label = sec.get("label", "Section")
            lines.append(f"\n{label}")
            for b in sec.get("beats", []):
                br = (sec.get("broll") or [""])[0] if isinstance(sec.get("broll"), list) else ""
                tag = f" [B-ROLL: {br}]" if br else ""
                lines.append(f"- {b}.{tag}")
        lines.append("\nCTA: Subscribe for more!")
        text = "\n".join(lines)
    
    # Save script text + minimal metadata
    base = opath.replace(".outline.json", "")
    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write(text)
    
    # Use brief metadata if available
    if brief:
        meta = {
            "title": brief.get('title', data["title_options"][0] if data.get("title_options") else "Untitled"),
            "description": f"Auto-generated with local LLM based on brief: {brief.get('title', 'N/A')}",
            "tags": brief.get('keywords_include', data.get("tags", ["education"])),
            "brief": brief.get('title', 'N/A'),
            "audience": brief.get('audience', []),
            "tone": brief.get('tone', 'N/A'),
        }
    else:
        meta = {
            "title": data["title_options"][0] if data.get("title_options") else "Untitled",
            "description": "Auto-generated with local LLM.",
            "tags": data.get("tags", ["education"]),
        }
    
    with open(base + ".metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    
    # Include brief context in final log
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("llm_script", "OK", f"{os.path.basename(base)}.txt;brief={brief_title}")
    else:
        log_state("llm_script", "OK", os.path.basename(base) + ".txt")
    
    print("Wrote script and metadata.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LLM script generation")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
            print(f"Loaded brief: {brief.get('title', 'Untitled')}")
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Warning: Failed to parse brief data: {e}")
    
    with single_lock():
        main(brief)
