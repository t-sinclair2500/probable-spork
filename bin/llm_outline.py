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
from bin.core import BASE, load_config, log_state, single_lock, get_logger


def call_ollama(prompt, cfg, models_config=None):
    """Call Ollama with specified model configuration."""
    try:
        # Use new model_runner system
        from bin.model_runner import model_session
        
        # Get model name from config - use research model for outline generation
        if models_config and 'research' in models_config.get('models', {}):
            model_name = models_config['models']['research']['name']
        else:
            # Fallback to global config
            model_name = cfg.llm.model
        
        # Use model session for deterministic load/unload
        with model_session(model_name) as session:
            system_prompt = "You are a helpful assistant for creating video outlines with research rigor."
            return session.chat(system=system_prompt, user=prompt)
            
    except Exception as e:
        # Fallback to legacy system
        url = cfg.llm.endpoint
        model = cfg.llm.model
        payload = {"model": model, "prompt": prompt, "stream": False}
        r = requests.post(url, json=payload, timeout=1200)
        r.raise_for_status()
        return r.json().get("response", "")


def get_intent_from_brief(brief):
    """Extract intent from brief, with fallback to narrative_history."""
    if brief and brief.get('intent'):
        return brief['intent']
    return 'narrative_history'  # Default intent


def apply_intent_template_to_outline(outline_data, intent_template, target_len_sec):
    """Apply intent template structure to outline data."""
    from bin.intent_loader import get_intent_beats, get_intent_metadata
    
    # Get template beats and metadata
    template_beats = get_intent_beats(intent_template)
    metadata = get_intent_metadata(intent_template)
    
    # Convert target length to milliseconds
    target_ms = int(target_len_sec * 1000)
    
    # Calculate total template duration
    template_duration = sum(beat.get('target_ms', 0) for beat in template_beats)
    
    # Scale beats to match target duration
    scale_factor = target_ms / template_duration if template_duration > 0 else 1
    
    # Apply template structure
    sections = []
    for i, template_beat in enumerate(template_beats):
        scaled_duration = int(template_beat['target_ms'] * scale_factor)
        
        section = {
            "id": i + 1,
            "label": template_beat['label'],
            "beats": [f"{template_beat['label']} beat {i + 1}"],
            "broll": [f"visual_{i + 1}"],
            "target_ms": scaled_duration,
            "needs_citations": metadata['evidence_load'] in ['medium', 'high']
        }
        sections.append(section)
    
    # Update outline with template structure
    outline_data['sections'] = sections
    outline_data['intent'] = intent_template
    outline_data['tone'] = metadata['tone']
    outline_data['evidence_load'] = metadata['evidence_load']
    outline_data['cta_policy'] = metadata['cta_policy']
    
    return outline_data


def main(brief=None, models_config=None):
    cfg = load_config()
    log = get_logger("llm_outline")
    os.makedirs(os.path.join(BASE, "scripts"), exist_ok=True)
    
    # Determine intent from brief
    intent = get_intent_from_brief(brief)
    log.info(f"[outline] Selected intent: {intent}")
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("llm_outline", "START", f"brief={brief_title};intent={intent}")
    else:
        log_state("llm_outline", "START", f"brief=none;intent={intent}")
    
    qpath = os.path.join(BASE, "data", "topics_queue.json")
    topics = json.load(open(qpath, "r")) if os.path.exists(qpath) else []
    
    # Use brief settings if available, otherwise fall back to config defaults
    if brief:
        tone = brief.get('tone', cfg.pipeline.tone)
        target_len_sec = brief.get('video', {}).get('target_length_max', cfg.pipeline.video_length_seconds)
        
        # Use brief title as primary topic
        if brief and brief.get('title'):
            topic = brief['title']
            seed_keywords = brief.get('keywords_include', ['productivity', 'tips'])
        elif topics:
            topic = topics[0]["topic"]
            seed_keywords = topics[0].get("keywords", brief.get('keywords_include', ['productivity', 'tips']) if brief else ['productivity', 'tips'])
        else:
            topic = brief.get('title', 'Productivity tips') if brief else 'Productivity tips'
            seed_keywords = brief.get('keywords_include', ['productivity', 'tips']) if brief else ['productivity', 'tips']
    else:
        tone = cfg.pipeline.tone
        target_len_sec = cfg.pipeline.video_length_seconds
        topic = topics[0]["topic"] if topics else "Productivity tips that save time"
        seed_keywords = topics[0].get("keywords") if topics else ["productivity", "tips"]
    
    # Load intent template
    try:
        from bin.intent_loader import load_intent_template, get_intent_metadata
        intent_template = load_intent_template(intent)
        intent_metadata = get_intent_metadata(intent)
        
        log.info(f"[outline] Loaded intent template: {intent} (evidence_load: {intent_metadata['evidence_load']}, CTA: {intent_metadata['cta_policy']})")
        
        # Use template tone if not specified in brief
        if not brief or not brief.get('tone'):
            tone = intent_metadata['tone']
            
    except Exception as e:
        log.warning(f"[outline] Failed to load intent template '{intent}': {e}, using fallback")
        intent_template = None
        intent_metadata = None
    
    with open(os.path.join(BASE, "prompts", "outline.txt"), "r", encoding="utf-8") as f:
        template = f.read()
    
    # Enhance prompt with intent context
    intent_context = ""
    if intent_template:
        intent_context = f"\nINTENT: {intent}\nTONE: {intent_metadata['tone']}\nEVIDENCE_LOAD: {intent_metadata['evidence_load']}\nCTA_POLICY: {intent_metadata['cta_policy']}"
    
    prompt = (
        template.replace("{topic}", topic)
        .replace("{seed_keywords}", ", ".join(seed_keywords))
        .replace("{target_length_min}", str(target_len_sec))
        .replace("{target_length_max}", str(target_len_sec))
        + f"\nTone: {tone}. Target length (sec): {target_len_sec}."
        + intent_context
    )
    
    # Enhance prompt with brief context if available
    if brief:
        from bin.core import create_brief_context
        brief_context = create_brief_context(brief)
        prompt = brief_context + prompt
    
    try:
        out = call_ollama(prompt, cfg, models_config)
        data = json.loads(out)
        
        # Apply intent template structure if available
        if intent_template:
            data = apply_intent_template_to_outline(data, intent, target_len_sec)
            log.info(f"[outline] Applied intent template: {len(data['sections'])} sections, {sum(1 for s in data['sections'] if s.get('needs_citations', False))} beats need citations")
        
    except Exception as e:
        log.warning(f"[outline] LLM generation failed: {e}, using fallback outline")
        # Fallback outline - use brief keywords if available
        if brief and brief.get('keywords_include'):
            fallback_keywords = brief['keywords_include'][:3]
        else:
            fallback_keywords = ["productivity", "tips"]
        
        # Create fallback outline with intent template structure if available
        if intent_template:
            # Use intent template structure for fallback
            template_beats = get_intent_beats(intent)
            metadata = get_intent_metadata(intent)
            
            # Convert target length to milliseconds
            target_ms = int(target_len_sec * 1000)
            
            # Calculate total template duration
            template_duration = sum(beat.get('target_ms', 0) for beat in template_beats)
            
            # Scale beats to match target duration
            scale_factor = target_ms / template_duration if template_duration > 0 else 1
            
            # Apply template structure
            sections = []
            for i, template_beat in enumerate(template_beats):
                scaled_duration = int(template_beat['target_ms'] * scale_factor)
                
                section = {
                    "id": i + 1,
                    "label": template_beat['label'],
                    "beats": [f"{template_beat['label']} content"],
                    "broll": [f"visual_{i + 1}"],
                    "target_ms": scaled_duration,
                    "needs_citations": metadata['evidence_load'] in ['medium', 'high']
                }
                sections.append(section)
            
            data = {
                "title_options": [f"{topic}: {intent.replace('_', ' ').title()}"],
                "sections": sections,
                "tags": fallback_keywords,
                "tone": tone,
                "target_len_sec": target_len_sec,
                "intent": intent,
                "cta_policy": metadata['cta_policy'],
                "evidence_load": metadata['evidence_load']
            }
        else:
            # Generic fallback if no intent template
            data = {
                "title_options": [f"{topic}: 5 Quick Tips"],
                "sections": [
                    {
                        "id": 1,
                        "label": "Hook",
                        "beats": ["Big promise", "Why watch"],
                        "broll": ["typing", "clock"],
                        "target_ms": 8000,
                        "needs_citations": False
                    },
                    {"id": 2, "label": "Point 1", "beats": ["Tip 1"], "broll": ["keyboard"], "target_ms": 10000, "needs_citations": False},
                    {"id": 3, "label": "Point 2", "beats": ["Tip 2"], "broll": ["monitor"], "target_ms": 10000, "needs_citations": False},
                    {"id": 4, "label": "Point 3", "beats": ["Tip 3"], "broll": ["notebook"], "target_ms": 10000, "needs_citations": False},
                    {"id": 5, "label": "Recap", "beats": ["Summary"], "broll": ["checklist"], "target_ms": 6000, "needs_citations": False},
                    {"id": 6, "label": "CTA", "beats": ["Subscribe"], "broll": ["subscribe button"], "target_ms": 6000, "needs_citations": False},
                ],
                "tags": fallback_keywords,
                "tone": tone,
                "target_len_sec": target_len_sec,
                "intent": intent,
                "cta_policy": "optional"
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
    
    # Log final state with intent and beats info
    beats_count = len(data.get('sections', []))
    citations_count = sum(1 for s in data.get('sections', []) if s.get('needs_citations', False))
    log_state("llm_outline", "OK", f"{os.path.basename(outline_path)};intent={intent};beats={beats_count};citations={citations_count}")
    
    print(f"Wrote outline {outline_path}")
    print(f"Intent: {intent}, Beats: {beats_count}, Citations needed: {citations_count}")


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
