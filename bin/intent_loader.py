#!/usr/bin/env python3
"""
Intent Templates Loader

Provides functions to load intent templates and determine CTA requirements
for outline and script generation stages.
"""

import os
import sys
from typing import Any, Dict

import yaml

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
        raise FileNotFoundError(
            f"Intent templates configuration not found: {config_path}"
        )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _intent_templates_cache = yaml.safe_load(f)
        log.info(
            f"Loaded {len(_intent_templates_cache.get('intents', {}))} intent templates"
        )
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

    if intent not in templates.get("intents", {}):
        available_intents = list(templates.get("intents", {}).keys())
        raise KeyError(
            f"Intent '{intent}' not found. Available intents: {available_intents}"
        )

    template = templates["intents"][intent]

    # Add global defaults if not specified
    defaults = templates.get("defaults", {})
    for key, default_value in defaults.items():
        if key not in template:
            template[key] = default_value

    # Ensure beats have defaults for needs_citations
    for beat in template.get("beats", []):
        if "needs_citations" not in beat:
            beat["needs_citations"] = defaults.get("needs_citations", True)

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
    cta_policy = template.get("cta_policy", "optional")

    # Map policy to requirement
    if cta_policy == "require":
        return "require"
    elif cta_policy == "omit":
        return "omit"
    elif cta_policy == "recommend":
        return "recommend"
    else:
        return "optional"


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
        "tone": template.get("tone", "conversational"),
        "visual_density_target": template.get("visual_density_target", 3),
        "evidence_load": template.get("evidence_load", "medium"),
        "description": template.get("description", ""),
        "cta_policy": template.get("cta_policy", "optional"),
    }

    return metadata


def get_intent_beats(intent: str) -> list:
    """
    Get the beat structure for a specific intent template.

    Args:
        intent: Name of the intent template

    Returns:
        List of beat dictionaries with id, label, target_ms, and needs_citations

    Raises:
        KeyError: If the specified intent doesn't exist
    """
    template = load_intent_template(intent)
    return template.get("beats", [])


def get_beats_needing_citations(intent: str) -> list:
    """
    Get beats that require citations for the specified intent.

    Args:
        intent: Name of the intent template

    Returns:
        List of beat dictionaries that need citations

    Raises:
        KeyError: If the specified intent doesn't exist
    """
    beats = get_intent_beats(intent)
    return [beat for beat in beats if beat.get("needs_citations", True)]


def get_citation_requirements(intent: str) -> Dict[str, Any]:
    """
    Get citation requirements for the specified intent.

    Args:
        intent: Name of the intent template

    Returns:
        Dictionary with citation requirements and statistics

    Raises:
        KeyError: If the specified intent doesn't exist
    """
    beats = get_intent_beats(intent)
    beats_needing_citations = get_beats_needing_citations(intent)

    total_beats = len(beats)
    beats_with_citations = len(beats_needing_citations)

    return {
        "total_beats": total_beats,
        "beats_needing_citations": beats_with_citations,
        "coverage_percentage": (
            (beats_with_citations / total_beats * 100) if total_beats > 0 else 0
        ),
        "beats": beats_needing_citations,
    }


def list_available_intents() -> list:
    """
    Get a list of all available intent template names.

    Returns:
        List of intent template names
    """
    templates = load_intent_templates()
    return list(templates.get("intents", {}).keys())


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
        required_fields = ["cta_policy", "tone", "beats"]
        for field in required_fields:
            if field not in template:
                log.warning(f"Intent '{intent}' missing required field: {field}")
                return False

        # Validate beats structure
        beats = template.get("beats", [])
        if not beats:
            log.warning(f"Intent '{intent}' has no beats defined")
            return False

        for beat in beats:
            # Check required beat fields
            if "id" not in beat or "label" not in beat:
                log.warning(
                    f"Beat in intent '{intent}' missing required fields: {beat}"
                )
                return False

            # Check if needs_citations is defined (should be boolean)
            if "needs_citations" in beat and not isinstance(
                beat["needs_citations"], bool
            ):
                log.warning(
                    f"Beat '{beat['id']}' in intent '{intent}' has invalid needs_citations value: {beat['needs_citations']}"
                )
                return False

        log.info(f"Intent '{intent}' validation passed")
        return True

    except Exception as e:
        log.error(f"Intent '{intent}' validation failed: {e}")
        return False


def get_intent_summary() -> Dict[str, Any]:
    """
    Get a summary of all intent templates with their key characteristics.

    Returns:
        Dictionary containing summary information for all intents
    """
    templates = load_intent_templates()
    intents = templates.get("intents", {})

    summary = {}
    for intent_name, intent_data in intents.items():
        summary[intent_name] = {
            "cta_policy": intent_data.get("cta_policy", "unknown"),
            "evidence_load": intent_data.get("evidence_load", "unknown"),
            "tone": intent_data.get("tone", "unknown"),
            "beat_count": len(intent_data.get("beats", [])),
            "beats_needing_citations": len(
                [
                    b
                    for b in intent_data.get("beats", [])
                    if b.get("needs_citations", True)
                ]
            ),
            "description": intent_data.get("description", "No description available"),
        }

    return summary


if __name__ == "__main__":
    # Simple CLI for testing
    import argparse

    parser = argparse.ArgumentParser(description="Intent Templates Loader CLI")
    parser.add_argument("--intent", help="Intent template to load")
    parser.add_argument(
        "--list", action="store_true", help="List all available intents"
    )
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
