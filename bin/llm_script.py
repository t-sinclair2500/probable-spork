#!/usr/bin/env python3
"""
LLM Script Writer

Generates video scripts using LLM models with research rigor and intent templates.
"""

import argparse
import json
import os
import re
import sys
from typing import Dict

from pathlib import Path

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, log_state, create_brief_context
from bin.intent_loader import (
    get_citation_requirements,
    get_intent_metadata,
    load_intent_template,
)
from bin.model_runner import model_session

log = get_logger("llm_script")


def enforce_cta_policy(script_text, cta_policy, intent):
    """Enforce CTA policy based on intent template."""
    if cta_policy == "omit":
        # Remove any CTA-like content
        cta_patterns = [
            r"\b(?:subscribe|like|comment|share|follow|click|visit|download|buy|purchase)\b",
            r"\b(?:don\'t forget to|remember to|make sure to|be sure to)\b",
            r"\b(?:if you enjoyed|if you found this helpful|if you learned something)\b",
        ]

        for pattern in cta_patterns:
            script_text = re.sub(
                pattern, "[CTA REMOVED]", script_text, flags=re.IGNORECASE
            )

        return script_text, "omitted"

    elif cta_policy == "require":
        # Ensure CTA is present
        if not any(
            word in script_text.lower()
            for word in ["subscribe", "like", "comment", "share", "follow"]
        ):
            script_text += (
                "\n\nDon't forget to like and subscribe for more content like this!"
            )
            return script_text, "added"

        return script_text, "present"

    elif cta_policy == "recommend":
        # Ensure recommendation is present
        if not any(
            word in script_text.lower()
            for word in ["recommend", "suggest", "best", "top", "choice"]
        ):
            script_text += "\n\nI highly recommend checking out this topic further if you're interested."
            return script_text, "added"

        return script_text, "present"

    else:  # optional
        return script_text, "optional"


def generate_script(
    outline_path: str,
    target_len_sec: int = 60,
    brief: Dict = None,
    models_config: Dict = None,
) -> Dict:
    """
    Generate a video script using LLM.

    Args:
        outline_path: Path to outline file
        target_len_sec: Target duration in seconds
        brief: Brief configuration
        models_config: Models configuration

    Returns:
        Generated script data
    """
    log.info(f"[script] Generating script from outline: {outline_path}")

    # Determine intent from brief
    intent = "narrative_history"  # Default
    if brief and brief.get("intent"):
        intent = brief["intent"]

    log.info(f"[script] Selected intent: {intent}")

    # Log start state
    if brief:
        brief_title = brief.get("title", "Untitled")
        log_state("llm_script", "START", f"brief={brief_title};intent={intent}")
    else:
        log_state("llm_script", "START", f"brief=none;intent={intent}")

    try:
        # Load outline
        if not os.path.exists(outline_path):
            raise FileNotFoundError(f"Outline not found: {outline_path}")

        with open(outline_path, "r", encoding="utf-8") as f:
            outline_data = json.load(f)

        # Extract intent and CTA policy from outline
        outline_intent = outline_data.get("intent", intent)
        cta_policy = outline_data.get("cta_policy", "optional")
        evidence_load = outline_data.get("evidence_load", "medium")

        log.info(
            f"[script] Using outline intent: {outline_intent}, CTA policy: {cta_policy}, evidence_load: {evidence_load}"
        )

        # Load intent template for additional context
        intent_template = None
        intent_metadata = None
        try:
            intent_template = load_intent_template(outline_intent)
            intent_metadata = get_intent_metadata(outline_intent)
            log.info(f"[script] Loaded intent template: {outline_intent}")
        except Exception as e:
            log.warning(
                f"[script] Failed to load intent template '{outline_intent}': {e}"
            )
            intent_template = None
            intent_metadata = None

        # Get citation requirements
        citation_reqs = None
        if intent_template:
            try:
                citation_reqs = get_citation_requirements(outline_intent)
                log.info(
                    f"[script] Citation requirements: {citation_reqs['beats_needing_citations']}/{citation_reqs['total_beats']} beats need citations"
                )
            except Exception as e:
                log.warning(f"[script] Could not get citation requirements: {e}")

        # Set tone and evidence load from template if available
        tone = (
            intent_metadata["tone"]
            if intent_metadata
            else "conversational, informative"
        )
        evidence_load = (
            intent_metadata["evidence_load"] if intent_metadata else evidence_load
        )

        # Get model name from config
        if models_config and "scriptwriter" in models_config.get("models", {}):
            model_name = models_config["models"]["scriptwriter"]["name"]
        else:
            # Fallback to research model
            model_name = (
                models_config["models"]["research"]["name"]
                if models_config and "research" in models_config.get("models", {})
                else "llama3.2:3b"
            )

        log.info(f"[script] Using model: {model_name}")

        # Load prompt template
        prompt_path = os.path.join(BASE, "prompts", "script_generation.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()

        # Format prompt with variables
        system_prompt = template.format(
            brief_context=create_brief_context(brief) if brief else "",
            target_len_sec=target_len_sec,
            tone=tone,
            evidence_load=evidence_load,
            cta_policy=cta_policy,
            outline_intent=outline_intent,
            outline_data=json.dumps(outline_data, indent=2),
        )

        # Load user prompt template
        user_prompt_path = os.path.join(BASE, "prompts", "user_script.txt")
        with open(user_prompt_path, "r", encoding="utf-8") as f:
            user_prompt_template = f.read()

        user_prompt = user_prompt_template.format(
            topic=outline_data.get("topic", "the topic")
        )

        # Generate script using LLM
        with model_session(model_name) as session:
            response = session.chat(
                system=system_prompt, user=user_prompt, temperature=0.3
            )

            # Parse response
            try:
                data = json.loads(response.strip())
            except json.JSONDecodeError:
                log.error("Failed to parse LLM response as JSON")
                # Create fallback script
                data = create_fallback_script(
                    outline_data, target_len_sec, outline_intent
                )

        # Validate and enhance script
        data = validate_and_enhance_script(data, outline_data, target_len_sec)

        # Insert citation placeholders for sections that need citations
        data = insert_citation_placeholders(data, outline_data)

        # Enforce CTA policy
        script_text = data.get("script", "")
        script_text, cta_action = enforce_cta_policy(
            script_text, cta_policy, outline_intent
        )
        data["script"] = script_text

        # Add metadata
        data["generated_at"] = str(Path.cwd())
        data["model_used"] = model_name
        data["intent"] = outline_intent
        data["cta_policy"] = cta_policy
        data["evidence_load"] = evidence_load

        # Log final state with intent and CTA action
        word_count = len(script_text.split())
        log_state(
            "llm_script",
            "OK",
            f"{os.path.basename(outline_path)}.txt;intent={outline_intent};cta_action={cta_action}",
        )

        # Print summary
        print(f"Generated script for: {outline_data.get('topic', 'Unknown')}")
        print(f"Intent: {outline_intent}, CTA: {cta_action}, Evidence: {evidence_load}")
        print(f"Word count: {word_count}, Target duration: {target_len_sec}s")

        return data

    except Exception as e:
        log.error(f"Script generation failed: {e}")
        log_state("llm_script", "ERROR", f"generation failed: {e}")
        raise


def create_fallback_script(
    outline_data: Dict, target_len_sec: int, intent: str
) -> Dict:
    """Create a fallback script when LLM generation fails."""
    log.warning(
        f"[script] Creating fallback script for {outline_data.get('topic', 'Unknown')}"
    )

    sections = outline_data.get("sections", [])
    script_parts = []

    for section in sections:
        section_content = (
            f"[{section.get('title', 'Section')} content will be generated]"
        )
        if section.get("needs_citations", True):
            section_content += " [CITATION NEEDED]"
        script_parts.append(section_content)

    script_text = "\n\n".join(script_parts)

    return {
        "title": f"{outline_data.get('topic', 'Topic')}: {intent.replace('_', ' ').title()}",
        "script": script_text,
        "sections": sections,
        "metadata": {
            "word_count": len(script_text.split()),
            "estimated_duration_sec": target_len_sec,
            "citation_placeholders_count": sum(
                1 for s in sections if s.get("needs_citations", True)
            ),
        },
    }


def validate_and_enhance_script(
    data: Dict, outline_data: Dict, target_len_sec: int
) -> Dict:
    """Validate and enhance the generated script."""
    if not isinstance(data, dict):
        return create_fallback_script(outline_data, target_len_sec, "narrative_history")

    # Ensure required fields
    if "script" not in data:
        data["script"] = ""

    if "sections" not in data:
        data["sections"] = []

    # Validate sections
    valid_sections = []
    for section in data["sections"]:
        if isinstance(section, dict) and "title" in section:
            # Ensure section has required fields
            section.setdefault("id", f"section_{len(valid_sections) + 1}")
            section.setdefault("content", section.get("title", ""))
            section.setdefault("needs_citations", True)
            section.setdefault("citation_placeholders", [])

            valid_sections.append(section)

    data["sections"] = valid_sections

    # Validate metadata
    if "metadata" not in data:
        data["metadata"] = {}

    metadata = data["metadata"]
    metadata.setdefault("word_count", len(data["script"].split()))
    metadata.setdefault("estimated_duration_sec", target_len_sec)
    metadata.setdefault("citation_placeholders_count", 0)

    return data


def insert_citation_placeholders(data: Dict, outline_data: Dict) -> Dict:
    """Insert citation placeholders for sections that need citations."""
    sections = data.get("sections", [])
    outline_sections = outline_data.get("sections", [])

    # Map outline sections to script sections
    for script_section in sections:
        # Find corresponding outline section
        outline_section = None
        for outline_sec in outline_sections:
            if outline_sec.get("id") == script_section.get("id") or outline_sec.get(
                "title"
            ) == script_section.get("title"):
                outline_section = outline_sec
                break

        if outline_section and outline_section.get("needs_citations", True):
            # Add citation placeholder
            script_section["needs_citations"] = True
            script_section["citation_placeholders"] = [
                "[CITATION NEEDED] for factual claims"
            ]

            # Add placeholder to script content
            content = script_section.get("content", "")
            if content and "[CITATION NEEDED]" not in content:
                script_section["content"] = content + " [CITATION NEEDED]"

    # Update metadata
    total_placeholders = sum(len(s.get("citation_placeholders", [])) for s in sections)
    data["metadata"]["citation_placeholders_count"] = total_placeholders

    return data


def save_script(data: Dict, output_path: str):
    """Save script to file."""
    try:
        # Save JSON data
        json_path = output_path.replace(".txt", ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Save plain text script
        script_text = data.get("script", "")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script_text)

        log.info(f"[script] Saved script to {output_path} and {json_path}")
    except Exception as e:
        log.error(f"Failed to save script: {e}")
        raise


def main(brief=None, models_config=None, outline_path=None, slug=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate video script using LLM")
    parser.add_argument("--brief", help="Path to brief file")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("--outline", help="Path to outline file")
    parser.add_argument(
        "--duration", type=int, default=60, help="Target duration in seconds"
    )
    parser.add_argument("--output", help="Output file path")
    parser.add_argument(
        "--mode",
        choices=["reuse", "live"],
        default="reuse",
        help="Mode: reuse (cache only) or live (with API calls)",
    )
    parser.add_argument(
        "--slug", required=True, help="Topic slug for script generation"
    )
    args = parser.parse_args()

    # Load brief data
    if brief is None:
        if args.brief:
            with open(args.brief, "r") as f:
                brief = json.load(f)
        elif args.brief_data:
            brief = json.loads(args.brief_data)
        else:
            brief = {"keywords_include": [args.slug]}

    # Determine outline path
    if outline_path is None:
        if args.outline:
            outline_path = args.outline
        else:
            outline_path = os.path.join(BASE, "scripts", f"{args.slug}.outline.json")

    log.info(
        f"[script] Starting script generation for slug: {args.slug}, outline: {outline_path}, duration: {args.duration}s"
    )

    # Generate script
    script_data = generate_script(outline_path, args.duration, brief, models_config)

    # Save script
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(BASE, "scripts", f"{args.slug}.txt")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    save_script(script_data, output_path)

    log.info(f"[script] Script generation completed for {args.slug}")
    log.info(f"[script] Output saved to {output_path}")

    return script_data


if __name__ == "__main__":
    main()
