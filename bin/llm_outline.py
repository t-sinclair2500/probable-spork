#!/usr/bin/env python3
"""
LLM Outline Generator

Generates video outlines using LLM models with research rigor and intent templates.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, log_state, single_lock
from bin.model_runner import model_session
from bin.intent_loader import (
    load_intent_template, 
    get_intent_metadata, 
    get_intent_beats,
    get_beats_needing_citations,
    get_citation_requirements
)

log = get_logger("llm_outline")


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
    
    # Calculate target duration per beat
    total_target_ms = target_len_sec * 1000
    total_template_ms = sum(beat.get('target_ms', 0) for beat in template_beats)
    
    if total_template_ms > 0:
        # Scale beats to match target duration
        scale_factor = total_target_ms / total_template_ms
        for beat in template_beats:
            beat['target_ms'] = int(beat.get('target_ms', 0) * scale_factor)
    
    # Apply template structure
    outline_data['sections'] = []
    for beat in template_beats:
        section = {
            'id': beat['id'],
            'title': beat['label'],
            'target_duration_ms': beat['target_ms'],
            'needs_citations': beat.get('needs_citations', True),
            'content': f"[{beat['label']} content will be generated]",
            'notes': f"Target duration: {beat['target_ms']}ms, Citations required: {beat.get('needs_citations', True)}"
        }
        outline_data['sections'].append(section)
    
    # Add intent metadata
    outline_data['intent'] = intent_template
    outline_data['tone'] = metadata.get('tone', 'conversational')
    outline_data['evidence_load'] = metadata.get('evidence_load', 'medium')
    outline_data['cta_policy'] = metadata.get('cta_policy', 'optional')
    
    return outline_data


def generate_outline(topic: str, target_len_sec: int = 60, brief: Dict = None, 
                    models_config: Dict = None) -> Dict:
    """
    Generate a video outline using LLM.
    
    Args:
        topic: Main topic for the video
        target_len_sec: Target duration in seconds
        brief: Brief configuration
        models_config: Models configuration
        
    Returns:
        Generated outline data
    """
    log.info(f"[outline] Generating outline for topic: {topic}")
    
    # Determine intent from brief
    intent = get_intent_from_brief(brief)
    log.info(f"[outline] Selected intent: {intent}")
    
    # Log start state
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("llm_outline", "START", f"brief={brief_title};intent={intent}")
    else:
        log_state("llm_outline", "START", f"brief=none;intent={intent}")
    
    try:
        # Get model name from config - use research model for outline generation
        if models_config and 'research' in models_config.get('models', {}):
            model_name = models_config['models']['research']['name']
        else:
            # Fallback to default model
            model_name = 'llama3.2:3b'
        
        log.info(f"[outline] Using model: {model_name}")
        
        # Load intent template
        intent_template = None
        intent_metadata = None
        try:
            intent_template = load_intent_template(intent)
            intent_metadata = get_intent_metadata(intent)
            log.info(f"[outline] Loaded intent template: {intent} (evidence_load: {intent_metadata['evidence_load']}, CTA: {intent_metadata['cta_policy']})")
        except Exception as e:
            log.warning(f"[outline] Failed to load intent template '{intent}': {e}, using fallback")
            intent_template = None
            intent_metadata = None
        
        # Get citation requirements
        citation_reqs = None
        if intent_template:
            try:
                citation_reqs = get_citation_requirements(intent)
                log.info(f"[outline] Citation requirements: {citation_reqs['beats_needing_citations']}/{citation_reqs['total_beats']} beats need citations ({citation_reqs['coverage_percentage']:.1f}% coverage)")
            except Exception as e:
                log.warning(f"[outline] Could not get citation requirements: {e}")
        
        # Set tone and evidence load
        tone = intent_metadata['tone'] if intent_metadata else "conversational, informative"
        evidence_load = intent_metadata['evidence_load'] if intent_metadata else "medium"
        
        # Load prompt template
        prompt_path = os.path.join(BASE, "prompts", "outline_generation.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
        
        # Format prompt with variables
        intent_context = ""
        if intent_template:
            intent_context = f"\nINTENT: {intent}\nTONE: {intent_metadata['tone']}\nEVIDENCE_LOAD: {intent_metadata['evidence_load']}\nCTA_POLICY: {intent_metadata['cta_policy']}"
        
        system_prompt = template.format(
            brief_context=create_brief_context(brief) if brief else "",
            target_len_sec=target_len_sec,
            topic=topic,
            tone=tone,
            evidence_load=evidence_load,
            intent=intent,
            cta_policy=intent_metadata.get('cta_policy', 'optional') if intent_metadata else 'optional'
        )

        # Load user prompt template
        user_prompt_path = os.path.join(BASE, "prompts", "user_outline.txt")
        with open(user_prompt_path, "r", encoding="utf-8") as f:
            user_prompt_template = f.read()
        
        user_prompt = user_prompt_template.format(topic=topic)
        
        # Generate outline using LLM
        with model_session(model_name) as session:
            response = session.chat(
                system=system_prompt,
                user=user_prompt,
                temperature=0.3
            )
            
            # Parse response
            try:
                data = json.loads(response.strip())
            except json.JSONDecodeError:
                log.error("Failed to parse LLM response as JSON")
                # Create fallback outline
                data = create_fallback_outline(topic, target_len_sec, intent)
        
        # Apply intent template structure if available
        if intent_template:
            data = apply_intent_template_to_outline(data, intent, target_len_sec)
            log.info(f"[outline] Applied intent template: {len(data['sections'])} sections, {sum(1 for s in data['sections'] if s.get('needs_citations', False))} beats need citations")
        
        # Validate and enhance outline
        data = validate_and_enhance_outline(data, target_len_sec)
        
        # Create fallback outline with intent template structure if available
        if not data.get('sections'):
            if intent_template:
                # Use intent template structure for fallback
                template_beats = get_intent_beats(intent)
                metadata = get_intent_metadata(intent)
                
                data = {
                    'title': f"{topic}: {intent.replace('_', ' ').title()}",
                    'topic': topic,
                    'target_duration_sec': target_len_sec,
                    'intent': intent,
                    'tone': metadata.get('tone', 'conversational'),
                    'evidence_load': metadata.get('evidence_load', 'medium'),
                    'cta_policy': metadata.get('cta_policy', 'optional'),
                    'sections': []
                }
                
                # Create sections from template beats
                for beat in template_beats:
                    section = {
                        'id': beat['id'],
                        'title': beat['label'],
                        'target_duration_ms': beat.get('target_ms', 0),
                        'needs_citations': beat.get('needs_citations', True),
                        'content': f"[{beat['label']} content]",
                        'notes': f"Template-based section, citations required: {beat.get('needs_citations', True)}"
                    }
                    data['sections'].append(section)
                
                log.info(f"[outline] Created fallback outline using intent template: {len(data['sections'])} sections")
            else:
                # Generic fallback if no intent template
                data = {
                    'title': f"{topic}: Video Outline",
                    'topic': topic,
                    'target_duration_sec': target_len_sec,
                    'intent': intent,
                    'sections': [
                        {
                            'id': 'intro',
                            'title': 'Introduction',
                            'target_duration_ms': 10000,
                            'needs_citations': False,
                            'content': 'Introduce the topic and set context',
                            'notes': 'Hook the audience, no citations needed'
                        },
                        {
                            'id': 'main',
                            'title': 'Main Content',
                            'target_duration_ms': (target_len_sec - 20) * 1000,
                            'needs_citations': True,
                            'content': 'Present main information and evidence',
                            'notes': 'Research and citations required'
                        },
                        {
                            'id': 'conclusion',
                            'title': 'Conclusion',
                            'target_duration_ms': 10000,
                            'needs_citations': False,
                            'content': 'Summarize and wrap up',
                            'notes': 'No citations needed for conclusion'
                        }
                    ]
                }
        
        # Add metadata
        data['generated_at'] = str(Path.cwd())
        data['model_used'] = model_name
        data['intent'] = intent
        
        # Log final state with intent and beats info
        beats_count = len(data.get('sections', []))
        citations_count = sum(1 for s in data.get('sections', []) if s.get('needs_citations', False))
        
        log_state("llm_outline", "OK", f"{os.path.basename(topic)};intent={intent};beats={beats_count};citations={citations_count}")
        
        # Print summary
        print(f"Generated outline for: {topic}")
        print(f"Intent: {intent}, Beats: {beats_count}, Citations needed: {citations_count}")
        
        return data
        
    except Exception as e:
        log.error(f"Outline generation failed: {e}")
        log_state("llm_outline", "ERROR", f"generation failed: {e}")
        raise


def create_fallback_outline(topic: str, target_len_sec: int, intent: str) -> Dict:
    """Create a fallback outline when LLM generation fails."""
    log.warning(f"[outline] Creating fallback outline for {topic}")
    
    return {
        'title': f"{topic}: {intent.replace('_', ' ').title()}",
        'topic': topic,
        'target_duration_sec': target_len_sec,
        'intent': intent,
        'sections': [
            {
                'id': 'intro',
                'title': 'Introduction',
                'target_duration_ms': 10000,
                'needs_citations': False,
                'content': 'Introduce the topic',
                'notes': 'Fallback section'
            },
            {
                'id': 'content',
                'title': 'Main Content',
                'target_duration_ms': (target_len_sec - 20) * 1000,
                'needs_citations': True,
                'content': 'Present main information',
                'notes': 'Fallback section with citations required'
            },
            {
                'id': 'conclusion',
                'title': 'Conclusion',
                'target_duration_ms': 10000,
                'needs_citations': False,
                'content': 'Wrap up',
                'notes': 'Fallback section'
            }
        ]
    }


def validate_and_enhance_outline(data: Dict, target_len_sec: int) -> Dict:
    """Validate and enhance the generated outline."""
    if not isinstance(data, dict):
        return create_fallback_outline(data.get('topic', 'Unknown'), target_len_sec, 'narrative_history')
    
    # Ensure required fields
    if 'sections' not in data:
        data['sections'] = []
    
    # Validate sections
    valid_sections = []
    total_duration = 0
    
    for section in data['sections']:
        if isinstance(section, dict) and 'title' in section:
            # Ensure section has required fields
            section.setdefault('id', f"section_{len(valid_sections) + 1}")
            section.setdefault('target_duration_ms', 10000)
            section.setdefault('needs_citations', True)
            section.setdefault('content', section.get('title', ''))
            section.setdefault('notes', '')
            
            # Validate duration
            duration = section.get('target_duration_ms', 0)
            if duration > 0:
                total_duration += duration
                valid_sections.append(section)
    
    data['sections'] = valid_sections
    
    # Adjust durations if needed
    if total_duration > 0:
        target_ms = target_len_sec * 1000
        if abs(total_duration - target_ms) > 5000:  # More than 5 seconds off
            scale_factor = target_ms / total_duration
            for section in data['sections']:
                section['target_duration_ms'] = int(section['target_duration_ms'] * scale_factor)
    
    return data


def save_outline(data: Dict, output_path: str):
    """Save outline to file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info(f"[outline] Saved outline to {output_path}")
    except Exception as e:
        log.error(f"Failed to save outline: {e}")
        raise


def main(brief=None, models_config=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate video outline using LLM")
    parser.add_argument("--brief", help="Path to brief file")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("--topic", help="Topic for outline generation")
    parser.add_argument("--duration", type=int, default=60, help="Target duration in seconds")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--mode", choices=['reuse', 'live'], default='reuse',
                       help='Mode: reuse (cache only) or live (with API calls)')
    parser.add_argument("--slug", required=True, help="Topic slug for outline generation")
    args = parser.parse_args()
    
    # Load brief data
    if brief is None:
        if args.brief:
            with open(args.brief, 'r') as f:
                brief = json.load(f)
        elif args.brief_data:
            brief = json.loads(args.brief_data)
        else:
            brief = {"keywords_include": [args.slug]}
    
    # Determine topic
    topic = args.topic or brief.get('topic') or args.slug
    
    log.info(f"[outline] Starting outline generation for slug: {args.slug}, topic: {topic}, duration: {args.duration}s")
    
    # Generate outline
    outline_data = generate_outline(topic, args.duration, brief, models_config)
    
    # Save outline
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(BASE, "scripts", f"{args.slug}.outline.json")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    save_outline(outline_data, output_path)
    
    log.info(f"[outline] Outline generation completed for {args.slug}")
    log.info(f"[outline] Output saved to {output_path}")
    
    return outline_data


if __name__ == "__main__":
    main()
