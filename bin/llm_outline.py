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
    r = requests.post(url, json=payload, timeout=1200)
    r.raise_for_status()
    return r.json().get("response", "")


def main(brief=None):
    cfg = load_config()
    os.makedirs(os.path.join(BASE, "scripts"), exist_ok=True)
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("llm_outline", "START", f"brief={brief_title}")
        # Assuming log is available, otherwise this line will cause an error
        # log.info(f"Running with brief: {brief_title}") 
    else:
        log_state("llm_outline", "START", "brief=none")
        # Assuming log is available, otherwise this line will cause an error
        # log.info("Running without brief - using default behavior")
    
    qpath = os.path.join(BASE, "data", "topics_queue.json")
    topics = json.load(open(qpath, "r")) if os.path.exists(qpath) else []
    
    # Use brief settings if available, otherwise fall back to config defaults
    if brief:
        tone = brief.get('tone', cfg.pipeline.tone)
        target_len_sec = brief.get('video', {}).get('target_length_max', cfg.pipeline.video_length_seconds)
        
        # Override topic if brief has specific focus
        if brief.get('title') and not topics:
            topic = brief['title']
            seed_keywords = brief.get('keywords_include', ['productivity', 'tips'])
        elif topics:
            topic = topics[0]["topic"]
            seed_keywords = topics[0].get("keywords", brief.get('keywords_include', ['productivity', 'tips']))
        else:
            topic = brief.get('title', 'Productivity tips')
            seed_keywords = brief.get('keywords_include', ['productivity', 'tips'])
    else:
        tone = cfg.pipeline.tone
        target_len_sec = cfg.pipeline.video_length_seconds
        topic = topics[0]["topic"] if topics else "Productivity tips that save time"
        seed_keywords = topics[0].get("keywords") if topics else ["productivity", "tips"]
    
    with open(os.path.join(BASE, "prompts", "outline.txt"), "r", encoding="utf-8") as f:
        template = f.read()
    
    prompt = (
        template.replace("{topic}", topic).replace("{seed_keywords}", ", ".join(seed_keywords))
        + f"\nTone: {tone}. Target length (sec): {target_len_sec}."
    )
    
    # Enhance prompt with brief context if available
    if brief:
        from bin.core import create_brief_context
        brief_context = create_brief_context(brief)
        prompt = brief_context + prompt
    
    try:
        out = call_ollama(prompt, cfg)
        data = json.loads(out)
    except Exception:
        # Fallback outline - use brief keywords if available
        if brief and brief.get('keywords_include'):
            fallback_keywords = brief['keywords_include'][:3]
        else:
            fallback_keywords = ["productivity", "tips"]
            
        data = {
            "title_options": [f"{topic}: 5 Quick Tips"],
            "sections": [
                {
                    "id": 1,
                    "label": "Hook",
                    "beats": ["Big promise", "Why watch"],
                    "broll": ["typing", "clock"],
                },
                {"id": 2, "label": "Point 1", "beats": ["Tip 1"], "broll": ["keyboard"]},
                {"id": 3, "label": "Point 2", "beats": ["Tip 2"], "broll": ["monitor"]},
                {"id": 4, "label": "Point 3", "beats": ["Tip 3"], "broll": ["notebook"]},
                {"id": 5, "label": "Recap", "beats": ["Summary"], "broll": ["checklist"]},
                {"id": 6, "label": "CTA", "beats": ["Subscribe"], "broll": ["subscribe button"]},
            ],
            "tags": fallback_keywords,
            "tone": tone,
            "target_len_sec": target_len_sec,
        }
    
    # Filter out any content that contains excluded keywords
    if brief and brief.get('keywords_exclude'):
        from bin.core import filter_content_by_brief
        exclude_terms = brief['keywords_exclude']
        
        # Check title options
        if 'title_options' in data:
            filtered_titles = []
            for title in data['title_options']:
                if not any(exclude_term.lower() in title.lower() for exclude_term in exclude_terms):
                    filtered_titles.append(title)
                else:
                    log_state("llm_outline", "FILTERED", f"Title filtered due to excluded keywords: {title}")
            data['title_options'] = filtered_titles
        
        # Check tags
        if 'tags' in data:
            filtered_tags = []
            for tag in data['tags']:
                if not any(exclude_term.lower() in tag.lower() for exclude_term in exclude_terms):
                    filtered_tags.append(tag)
                else:
                    log_state("llm_outline", "FILTERED", f"Tag filtered due to excluded keywords: {tag}")
            data['tags'] = filtered_tags
    
    date_tag = time.strftime("%Y-%m-%d")
    outline_path = os.path.join(
        BASE, "scripts", f"{date_tag}_{re.sub(r'[^a-z0-9]+','-',topic.lower())}.outline.json"
    )
    with open(outline_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    # Include brief context in final log
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("llm_outline", "OK", f"{os.path.basename(outline_path)};brief={brief_title}")
    else:
        log_state("llm_outline", "OK", os.path.basename(outline_path))
    
    print(f"Wrote outline {outline_path}")


if __name__ == "__main__":
    import argparse
    import logging
    log = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(description="LLM outline generation")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
            log.info(f"Loaded brief: {brief.get('title', 'Untitled')}")
        except (json.JSONDecodeError, TypeError) as e:
            log.warning(f"Failed to parse brief data: {e}")
    
    with single_lock():
        main(brief)
