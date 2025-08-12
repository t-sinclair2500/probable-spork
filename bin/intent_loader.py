#!/usr/bin/env python3
"""
Intent Templates Loader

Provides functions to load intent templates and determine CTA requirements
for outline and script generation stages.
"""

import os
import sys
import yaml
from typing import Dict, Any, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger

log = get_logger("intent_loader")

# Cache for loaded templates
_intent_templates_cache = None


def load_intent_templates() -> Dict[str, Any]:
    """
    Load intent templates from configuration file.
    
    Returns:
        Dictionary containing all intent templates and metadata
        
    Raises:
        FileNotFoundError: If intent_templates.yaml doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    global _intent_templates_cache
    
    if _intent_templates_cache is not None:
        return _intent_templates_cache
    
    config_path = os.path.join(ROOT, "conf", "intent_templates.yaml")
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Intent templates configuration not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            _intent_templates_cache = yaml.safe_load(f)
        log.info(f"Loaded {len(_intent_templates_cache.get('intents', {}))} intent templates")
        return _intent_templates_cache
    except yaml.YAMLError as e:
        log.error(f"Failed to parse intent templates YAML: {e}")
        raise
    except Exception as e:
        log.error(f"Failed to load intent templates: {e}")
        raise


def load_intent_template(intent: str) -> Dict[str, Any]:
    """
    Load a specific intent template by name.
    
    Args:
        intent: Name of the intent template to load
        
    Returns:
        Dictionary containing the intent template configuration
        
    Raises:
        KeyError: If the specified intent doesn't exist
        FileNotFoundError: If intent_templates.yaml doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    templates = load_intent_templates()
    
    if intent not in templates.get('intents', {}):
        available_intents = list(templates.get('intents', {}).keys())
        raise KeyError(f"Intent '{intent}' not found. Available intents: {available_intents}")
    
    template = templates['intents'][intent]
    
    # Add global defaults if not specified
    defaults = templates.get('defaults', {})
    for key, default_value in defaults.items():
        if key not in template:
            template[key] = default_value
    
    log.info(f"Loaded intent template: {intent}")
    return template


def cta_required(intent: str) -> str:
    """
    Determine if a call-to-action is required for the specified intent.
    
    Args:
        intent: Name of the intent template
        
    Returns:
        String indicating CTA requirement: 'require', 'optional', 'omit', or 'recommend'
        
    Raises:
        KeyError: If the specified intent doesn't exist
    """
    template = load_intent_template(intent)
    cta_policy = template.get('cta_policy', 'optional')
    
    # Map policy to requirement
    if cta_policy == 'require':
        return 'require'
    elif cta_policy == 'omit':
        return 'omit'
    elif cta_policy == 'recommend':
        return 'recommend'
    else:
        return 'optional'


def get_intent_metadata(intent: str) -> Dict[str, Any]:
    """
    Get metadata for a specific intent template.
    
    Args:
        intent: Name of the intent template
        
    Returns:
        Dictionary containing intent metadata (tone, visual_density_target, evidence_load, description)
        
    Raises:
        KeyError: If the specified intent doesn't exist
    """
    template = load_intent_template(intent)
    
    metadata = {
        'tone': template.get('tone', 'conversational'),
        'visual_density_target': template.get('visual_density_target', 3),
        'evidence_load': template.get('evidence_load', 'medium'),
        'description': template.get('description', ''),
        'cta_policy': template.get('cta_policy', 'optional')
    }
    
    return metadata


def get_intent_beats(intent: str) -> list:
    """
    Get the beat structure for a specific intent template.
    
    Args:
        intent: Name of the intent template
        
    Returns:
        List of beat dictionaries with id, label, and target_ms
        
    Raises:
        KeyError: If the specified intent doesn't exist
    """
    template = load_intent_template(intent)
    return template.get('beats', [])


def list_available_intents() -> list:
    """
    Get a list of all available intent template names.
    
    Returns:
        List of intent template names
    """
    templates = load_intent_templates()
    return list(templates.get('intents', {}).keys())


def validate_intent(intent: str) -> bool:
    """
    Validate that an intent template exists and has required fields.
    
    Args:
        intent: Name of the intent template to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        template = load_intent_template(intent)
        
        # Check required fields
        required_fields = ['cta_policy', 'tone', 'beats']
        for field in required_fields:
            if field not in template:
                log.warning(f"Intent '{intent}' missing required field: {field}")
                return False
        
        # Validate beats structure
        beats = template.get('beats', [])
        if not beats:
            log.warning(f"Intent '{intent}' has no beats defined")
            return False
        
        for beat in beats:
            if not all(key in beat for key in ['id', 'label', 'target_ms']):
                log.warning(f"Intent '{intent}' has invalid beat structure")
                return False
        
        return True
        
    except Exception as e:
        log.error(f"Failed to validate intent '{intent}': {e}")
        return False


if __name__ == "__main__":
    # Simple CLI for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Intent Templates Loader CLI")
    parser.add_argument("--intent", help="Intent template to load")
    parser.add_argument("--list", action="store_true", help="List all available intents")
    parser.add_argument("--validate", help="Validate a specific intent template")
    
    args = parser.parse_args()
    
    if args.list:
        intents = list_available_intents()
        print("Available intents:")
        for intent in intents:
            print(f"  - {intent}")
    
    elif args.validate:
        is_valid = validate_intent(args.validate)
        print(f"Intent '{args.validate}' is {'valid' if is_valid else 'invalid'}")
    
    elif args.intent:
        try:
            template = load_intent_template(args.intent)
            cta_req = cta_required(args.intent)
            print(f"Intent: {args.intent}")
            print(f"CTA Required: {cta_req}")
            print(f"Tone: {template.get('tone')}")
            print(f"Beats: {len(template.get('beats', []))}")
        except Exception as e:
            print(f"Error: {e}")
    
    else:
        parser.print_help()
