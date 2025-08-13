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
        
        # Get model name from config - use scriptwriter model for script generation
        if models_config and 'scriptwriter' in models_config.get('models', {}):
            model_name = models_config['models']['scriptwriter']['name']
        else:
            # Fallback to global config
            model_name = cfg.llm.model
        
        # Use model session for deterministic load/unload
        with model_session(model_name) as session:
            system_prompt = "You are a helpful assistant for writing video scripts with proper tone and CTA enforcement."
            return session.chat(system=system_prompt, user=prompt)
            
    except Exception as e:
        # Fallback to legacy system
        url = cfg.llm.endpoint
        model = cfg.llm.model
        payload = {"model": model, "prompt": prompt, "stream": False}
        r = requests.post(url, json=payload, timeout=1800)
        r.raise_for_status()
        return r.json().get("response", "")


def enforce_cta_policy(script_text, cta_policy, intent):
    """Enforce CTA policy based on intent template."""
    if cta_policy == "omit":
        # Remove CTA sections for narrative_history
        lines = script_text.split('\n')
        filtered_lines = []
        skip_next = False
        
        for line in lines:
            if any(cta_indicator in line.lower() for cta_indicator in ['subscribe', 'like', 'comment', 'cta:', 'call to action']):
                skip_next = True
                continue
            if skip_next and line.strip() == '':
                skip_next = False
                continue
            if not skip_next:
                filtered_lines.append(line)
        
        script_text = '\n'.join(filtered_lines)
        return script_text, "CTA omitted per policy"
    
    elif cta_policy == "require":
        # Ensure CTA is present
        if not any(cta_indicator in script_text.lower() for cta_indicator in ['subscribe', 'like', 'comment', 'cta:', 'call to action']):
            script_text += "\n\nCTA: Subscribe for more content like this!"
            return script_text, "CTA added per policy"
    
    return script_text, "CTA policy applied"


def add_citation_placeholders(script_text, sections):
    """Add citation placeholders where beats need citations."""
    lines = script_text.split('\n')
    modified_lines = []
    
    for line in lines:
        modified_lines.append(line)
        
        # Check if this line corresponds to a section that needs citations
        for section in sections:
            if section.get('needs_citations', False):
                # Look for lines that might contain factual claims
                if any(claim_indicator in line.lower() for claim_indicator in ['in', 'on', 'during', 'when', 'first', 'discovered', 'invented', 'founded']):
                    # Add citation placeholder
                    modified_lines.append(" [CITATION NEEDED]")
                    break
    
    return '\n'.join(modified_lines)


def main(brief=None, models_config=None):
    cfg = load_config()
    log = get_logger("llm_script")
    os.makedirs(os.path.join(BASE, "scripts"), exist_ok=True)
    
    # Determine intent from brief
    intent = "narrative_history"  # Default
    if brief and brief.get('intent'):
        intent = brief['intent']
    
    log.info(f"[script] Selected intent: {intent}")
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("llm_script", "START", f"brief={brief_title};intent={intent}")
        print(f"Running with brief: {brief_title}")
    else:
        log_state("llm_script", "START", f"brief=none;intent={intent}")
        print("Running without brief - using default behavior")
    
    # Pick the outline that matches the brief, or newest if no match
    outlines = [p for p in os.listdir(os.path.join(BASE, "scripts")) if p.endswith(".outline.json")]
    if not outlines:
        log_state("llm_script", "SKIP", "no outlines")
        print("No outlines")
        return
    
    # If we have a brief, try to find a matching outline
    if brief and brief.get('title'):
        brief_title = brief['title'].lower()
        # Try multiple matching strategies
        matching_outlines = []
        
        # Strategy 1: Exact match with underscores
        exact_match = brief_title.replace(' ', '_').replace('&', 'and')
        matching_outlines = [p for p in outlines if exact_match in p.lower()]
        
        # Strategy 2: Partial match with key terms
        if not matching_outlines:
            key_terms = ['eames', 'ray', 'charles']
            matching_outlines = [p for p in outlines if any(term in p.lower() for term in key_terms)]
        
        # Strategy 3: Date-based match (most recent)
        if not matching_outlines:
            # Find outlines from today
            import datetime
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            matching_outlines = [p for p in outlines if today in p]
        
        if matching_outlines:
            log.info(f"Found {len(matching_outlines)} matching outlines for brief: {brief_title}")
            outlines = matching_outlines
        else:
            log.warning(f"No matching outlines found for brief: {brief_title}, using newest")
    
    outlines.sort(reverse=True)
    opath = os.path.join(BASE, "scripts", outlines[0])
    data = json.load(open(opath, "r", encoding="utf-8"))
    
    # Extract intent and CTA policy from outline
    outline_intent = data.get('intent', intent)
    cta_policy = data.get('cta_policy', 'optional')
    evidence_load = data.get('evidence_load', 'medium')
    tone = data.get('tone', 'conversational')
    
    log.info(f"[script] Using outline intent: {outline_intent}, CTA policy: {cta_policy}, evidence_load: {evidence_load}")
    
    with open(os.path.join(BASE, "prompts", "script_writer.txt"), "r", encoding="utf-8") as f:
        template = f.read()
    
    # Use brief settings if available, otherwise fall back to config defaults
    if brief:
        tone = brief.get('tone', tone)  # Use outline tone as fallback
        target_len_sec = brief.get('video', {}).get('target_length_max', cfg.pipeline.video_length_seconds)
        
        # Override word count targets if brief specifies them
        if brief.get('blog', {}).get('words_min') and brief.get('blog', {}).get('words_max'):
            word_target = f"{brief['blog']['words_min']}-{brief['blog']['words_max']} words"
        else:
            word_target = "900-1200 words"
    else:
        target_len_sec = cfg.pipeline.video_length_seconds
        word_target = "900-1200 words"
    
    # Enhance prompt with intent and CTA context
    intent_context = f"\nINTENT: {outline_intent}\nTONE: {tone}\nCTA_POLICY: {cta_policy}\nEVIDENCE_LOAD: {evidence_load}"
    
    # Get CTA policy description
    cta_descriptions = {
        'require': 'Must include a clear call-to-action',
        'optional': 'May include a call-to-action if appropriate',
        'omit': 'Should not include a call-to-action',
        'recommend': 'Must include a clear recommendation or endorsement'
    }
    cta_policy_description = cta_descriptions.get(cta_policy, 'CTA policy not specified')
    
    # Simple prompt: feed outline JSON and instructions
    prompt = (
        "OUTLINE:\n"
        + json.dumps(data)
        + "\n\n"
        + template
        + f"\nTone: {tone}. Target length (sec): {target_len_sec}. Target: {word_target}. Return plain text only."
        + intent_context
    )
    
    # Replace template variables in the prompt
    prompt = prompt.replace("{tone}", tone)
    prompt = prompt.replace("{cta_policy}", cta_policy)
    prompt = prompt.replace("{cta_policy_description}", cta_policy_description)
    prompt = prompt.replace("{evidence_load}", evidence_load)
    
    # Enhance prompt with brief context if available
    if brief:
        from bin.core import create_brief_context
        brief_context = create_brief_context(brief)
        prompt = brief_context + prompt
    
    try:
        text = call_ollama(prompt, cfg, models_config)
        
        # Enforce CTA policy
        text, cta_action = enforce_cta_policy(text, cta_policy, outline_intent)
        log.info(f"[script] CTA enforcement: {cta_action}")
        
        # Add citation placeholders if needed
        if evidence_load in ['medium', 'high']:
            text = add_citation_placeholders(text, data.get('sections', []))
            log.info(f"[script] Added citation placeholders for {evidence_load} evidence load")
        
    except Exception as e:
        log.warning(f"[script] LLM generation failed: {e}, using fallback script")
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
        
        # Apply CTA policy to fallback
        if cta_policy != "omit":
            lines.append("\nCTA: Subscribe for more!")
        else:
            lines.append("\nClosing thoughts...")
        
        text = "\n".join(lines)
        
        # Add citation placeholders if needed
        if evidence_load in ['medium', 'high']:
            text = add_citation_placeholders(text, data.get('sections', []))
    
    # Filter out any content that contains excluded keywords
    if brief and brief.get('keywords_exclude'):
        from bin.core import filter_content_by_brief
        filtered_text, rejection_reasons = filter_content_by_brief(text, brief)
        if rejection_reasons:
            log_state("llm_script", "REJECTED", f"Script contains excluded keywords: {rejection_reasons}")
            # Generate a replacement script without excluded terms
            replacement_prompt = prompt + f"\n\nIMPORTANT: Do not use these terms: {', '.join(brief['keywords_exclude'])}"
            try:
                text = call_ollama(replacement_prompt, cfg, models_config)
                # Re-apply CTA policy and citation placeholders
                text, cta_action = enforce_cta_policy(text, cta_policy, outline_intent)
                if evidence_load in ['medium', 'high']:
                    text = add_citation_placeholders(text, data.get('sections', []))
            except Exception:
                log_state("llm_script", "FALLBACK", "Using fallback script after keyword rejection")
                # Keep the original fallback text
    
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
            "intent": outline_intent,
            "cta_policy": cta_policy,
            "evidence_load": evidence_load
        }
    else:
        meta = {
            "title": data["title_options"][0] if data.get("title_options") else "Untitled",
            "description": "Auto-generated with local LLM.",
            "tags": data.get("tags", ["education"]),
            "intent": outline_intent,
            "cta_policy": cta_policy,
            "evidence_load": evidence_load
        }
    
    with open(base + ".metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    
    # Log final state with intent and CTA action
    log_state("llm_script", "OK", f"{os.path.basename(base)}.txt;intent={outline_intent};cta_action={cta_action}")
    
    print("Wrote script and metadata.")
    print(f"Intent: {outline_intent}, CTA: {cta_action}, Evidence: {evidence_load}")


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
