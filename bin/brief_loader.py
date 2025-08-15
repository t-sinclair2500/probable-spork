"""
Workstream Brief Loader

Centralized brief configuration that the entire pipeline reads first.
Supports both YAML and Markdown front-matter formats.
"""

import os
import re
import yaml
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Set up logging
log = logging.getLogger(__name__)


def load_brief() -> Dict[str, Any]:
    """
    Load the workstream brief from conf/brief.yaml or conf/brief.md.
    
    Returns:
        Dict containing the brief configuration with normalized fields and defaults.
        
    Raises:
        FileNotFoundError: If neither brief file exists
        yaml.YAMLError: If YAML parsing fails
    """
    # Check for YAML first (takes precedence)
    yaml_path = os.path.join(BASE, "conf", "brief.yaml")
    md_path = os.path.join(BASE, "conf", "brief.md")
    
    if os.path.exists(yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            brief = yaml.safe_load(f)
        brief["_source"] = "yaml"
    elif os.path.exists(md_path):
        brief = from_markdown_front_matter(md_path)
        brief["_source"] = "markdown"
    else:
        raise FileNotFoundError(
            "No brief file found. Create either conf/brief.yaml or conf/brief.md"
        )
    
    return validate_brief(brief)


def from_markdown_front_matter(md_path: str) -> Dict[str, Any]:
    """
    Parse Markdown file with YAML front-matter.
    
    Args:
        md_path: Path to the Markdown file
        
    Returns:
        Dict with front-matter as config and body as "notes"
    """
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extract front-matter (between --- markers)
    front_matter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    
    if front_matter_match:
        front_matter_text = front_matter_match.group(1)
        try:
            brief = yaml.safe_load(front_matter_text)
            if brief is None:
                brief = {}
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in front-matter: {e}")
        
        # Extract body content (everything after front-matter)
        body_start = content.find("---", 3) + 3
        if body_start > 3:
            body = content[body_start:].strip()
            if body:
                brief["notes"] = body
    else:
        # No front-matter, treat entire file as notes
        brief = {"notes": content.strip()}
    
    return brief


def validate_brief(brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize brief configuration.
    
    Args:
        brief: Raw brief configuration
        
    Returns:
        Normalized brief with defaults applied
    """
    # Define allowed keys and their default values
    allowed_keys = {
        "title": "",
        "intent": "",
        "audience": [],
        "tone": "informative",
        "video": {"target_length_min": 5, "target_length_max": 7},
        "blog": {"words_min": 900, "words_max": 1300},
        "keywords_include": [],
        "keywords_exclude": [],
        "sources_preferred": [],
        "monetization": {
            "primary": ["lead_magnet", "email_capture"],
            "cta_text": "Download our free guide"
        },
        "notes": ""
    }
    
    # Apply defaults for missing keys
    normalized = {}
    for key, default_value in allowed_keys.items():
        if key in brief:
            normalized[key] = brief[key]
        else:
            normalized[key] = default_value
    
    # Normalize specific fields
    normalized = _normalize_brief_fields(normalized)
    
    # Validate intent if present
    if normalized.get('intent'):
        try:
            from bin.core import validate_brief_intent
            is_valid, error = validate_brief_intent(normalized)
            if not is_valid:
                raise ValueError(f"Intent validation failed: {error}")
        except ImportError:
            # Intent validation not available, skip
            pass
    
    return normalized


def _normalize_brief_fields(brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize specific fields in the brief.
    
    Args:
        brief: Brief configuration
        
    Returns:
        Normalized brief
    """
    # Ensure audience is a list
    if isinstance(brief["audience"], str):
        brief["audience"] = [brief["audience"]]
    elif not isinstance(brief["audience"], list):
        brief["audience"] = []
    
    # Ensure keywords are lists and normalized
    for key in ["keywords_include", "keywords_exclude", "sources_preferred"]:
        if isinstance(brief[key], str):
            brief[key] = [brief[key]]
        elif not isinstance(brief[key], list):
            brief[key] = []
        
        # Normalize keywords: lowercase, strip whitespace
        brief[key] = [kw.lower().strip() for kw in brief[key] if kw.strip()]
    
    # Ensure video/blog configs are dicts
    for key in ["video", "blog"]:
        if not isinstance(brief[key], dict):
            brief[key] = {}
    
    # Ensure monetization is a dict
    if not isinstance(brief["monetization"], dict):
        brief["monetization"] = {}
    
    # Ensure notes is a string
    if not isinstance(brief["notes"], str):
        brief["notes"] = str(brief["notes"]) if brief["notes"] is not None else ""
    
    return brief


def get_brief_path() -> Optional[str]:
    """
    Get the path to the current brief file.
    
    Returns:
        Path to brief file if it exists, None otherwise
    """
    yaml_path = os.path.join(BASE, "conf", "brief.yaml")
    md_path = os.path.join(BASE, "conf", "brief.md")
    
    if os.path.exists(yaml_path):
        return yaml_path
    elif os.path.exists(md_path):
        return md_path
    else:
        return None


def create_brief_template(output_path: str = None) -> str:
    """
    Create a template brief file.
    
    Args:
        output_path: Where to save the template (default: conf/brief.yaml)
        
    Returns:
        Path to the created template file
    """
    if output_path is None:
        output_path = os.path.join(BASE, "conf", "brief.yaml")
    
    template = {
        "title": "Local SEO for Dentists",
        "audience": ["practice owners", "office managers"],
        "tone": "confident, practical",
        "video": {
            "target_length_min": 5,
            "target_length_max": 7
        },
        "blog": {
            "words_min": 900,
            "words_max": 1300
        },
        "keywords_include": [
            "Google Business Profile",
            "reviews",
            "NAP consistency",
            "service pages"
        ],
        "keywords_exclude": [
            "AI tools",
            "crypto",
            "NFT"
        ],
        "sources_preferred": [
            "Google Search Central",
            "Sterling Sky blog"
        ],
        "monetization": {
            "primary": ["lead_magnet", "email_capture"],
            "cta_text": "Download the Local SEO checklist"
        },
        "notes": "Focus on appointment intent keywords and GBP optimization."
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)
    
    return output_path


def parse_free_text_brief(text: str) -> Dict[str, Any]:
    """
    Parse a free-text brief into a structured Brief object.
    
    Uses simple rules + optional local LLM to infer brief fields.
    
    Args:
        text: Free-text brief description
        
    Returns:
        Dict containing the parsed brief configuration
        
    Example:
        "3-4 min explainer on baby sleep regression, comforting tone, linen texture, CTA off"
        → {"video": {"target_length_min": 3, "target_length_max": 4}, "tone": "comforting", ...}
    """
    log.info(f"[brief] Parsing free-text brief: {text[:100]}...")
    
    # Initialize with defaults
    brief = {
        "title": "",
        "intent": "narrative_history",  # Default intent
        "audience": [],
        "tone": "informative",
        "video": {"target_length_min": 5, "target_length_max": 7},
        "blog": {"words_min": 900, "words_max": 1300},
        "keywords_include": [],
        "keywords_exclude": [],
        "sources_preferred": [],
        "monetization": {
            "primary": ["lead_magnet", "email_capture"],
            "cta_text": "Download our free guide"
        },
        "notes": text,  # Store original text
        "_source": "free_text_parse"
    }
    
    # Extract duration patterns
    duration_patterns = [
        r"(\d+)[-\s](\d+)\s*(?:min|minute|minutes?)\s*(?:explainer|video|content)",
        r"(\d+)\s*(?:min|minute|minutes?)\s*(?:explainer|video|content)",
        r"(\d+)[-\s](\d+)\s*(?:second|seconds?)",
        r"(\d+)\s*(?:second|seconds?)"
    ]
    
    for pattern in duration_patterns:
        match = re.search(pattern, text.lower())
        if match:
            if len(match.groups()) == 2:
                min_val, max_val = int(match.group(1)), int(match.group(2))
                brief["video"]["target_length_min"] = min_val
                brief["video"]["target_length_max"] = max_val
                log.info(f"[brief] Extracted duration: {min_val}-{max_val} minutes")
            else:
                duration = int(match.group(1))
                brief["video"]["target_length_min"] = duration
                brief["video"]["target_length_max"] = duration
                log.info(f"[brief] Extracted duration: {duration} minutes")
            break
    
    # Extract tone patterns
    tone_patterns = [
        r"(comforting|warm|gentle|soothing|calm)",
        r"(authoritative|confident|professional|expert)",
        r"(conversational|casual|friendly|approachable)",
        r"(dramatic|intense|serious|urgent)",
        r"(humorous|fun|lighthearted|entertaining)",
        r"(educational|informative|instructional|tutorial)"
    ]
    
    for pattern in tone_patterns:
        match = re.search(pattern, text.lower())
        if match:
            brief["tone"] = match.group(1)
            log.info(f"[brief] Extracted tone: {brief['tone']}")
            break
    
    # Extract texture patterns
    texture_keywords = {
        "linen": "linen",
        "woodgrain": "woodgrain", 
        "halftone": "halftone",
        "paper": "print_soft",
        "vintage": "vintage_paper",
        "minimal": "minimal",
        "modern": "modern_flat",
        "off": "off"
    }
    
    for keyword, preset in texture_keywords.items():
        if keyword in text.lower():
            brief["texture_preset"] = preset
            log.info(f"[brief] Extracted texture preset: {preset}")
            break
    
    # Extract CTA patterns
    if "cta off" in text.lower() or "no cta" in text.lower():
        brief["monetization"]["cta_enabled"] = False
        log.info("[brief] CTA disabled")
    elif "cta on" in text.lower():
        brief["monetization"]["cta_enabled"] = True
        log.info("[brief] CTA enabled")
    
    # Extract topic from text
    # Look for "on" or "about" followed by topic
    topic_patterns = [
        r"(?:on|about|regarding)\s+([^,\.]+)",
        r"explainer\s+(?:on|about)\s+([^,\.]+)",
        r"video\s+(?:on|about)\s+([^,\.]+)"
    ]
    
    for pattern in topic_patterns:
        match = re.search(pattern, text.lower())
        if match:
            topic = match.group(1).strip()
            brief["title"] = f"Guide on {topic.title()}"
            log.info(f"[brief] Extracted topic: {topic}")
            break
    
    # Try to use local LLM if available for enhanced parsing
    try:
        enhanced_brief = _enhance_brief_with_llm(text, brief)
        if enhanced_brief:
            brief.update(enhanced_brief)
            log.info("[brief] Enhanced brief using local LLM")
    except Exception as e:
        log.debug(f"[brief] LLM enhancement failed (expected): {e}")
    
    # Validate and normalize the brief
    brief = validate_brief(brief)
    
    log.info(f"[brief] Parsed brief fields: {list(brief.keys())}")
    return brief


def _enhance_brief_with_llm(text: str, base_brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Enhance brief parsing using local LLM if available.
    
    Args:
        text: Original free-text brief
        base_brief: Base brief with initial parsing
        
    Returns:
        Enhanced brief fields or None if LLM not available
    """
    try:
        # Check if Ollama is available
        import subprocess
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            return None
        
        # Check if we have a suitable model
        models_result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "llama3.2" not in models_result.stdout.lower() and "mistral" not in models_result.stdout.lower():
            return None
        
        # Create LLM prompt for brief enhancement
        prompt = f"""
        Parse this video brief and return ONLY a JSON object with these fields:
        - intent: one of [narrative_history, how_to, product_demo, explainer, story]
        - audience: list of target audience segments
        - keywords_include: list of relevant keywords
        - motion: one of [subtle, moderate, dynamic] (animation style)
        - seed: random number 1-9999 for consistent generation
        
        Brief: "{text}"
        
        Return only valid JSON:
        """
        
        # Call Ollama
        llm_result = subprocess.run(
            ["ollama", "run", "llama3.2:3b", prompt],
            capture_output=True, text=True, timeout=30
        )
        
        if llm_result.returncode == 0:
            # Extract JSON from response
            response = llm_result.stdout.strip()
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                enhanced = yaml.safe_load(json_match.group()) # Use yaml.safe_load for JSON-like YAML
                log.info(f"[brief] LLM enhanced fields: {list(enhanced.keys())}")
                return enhanced
                
    except Exception as e:
        log.debug(f"[brief] LLM enhancement failed: {e}")
    
    return None


def resolve_brief(preferred: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Resolve brief configuration by merging preferred settings with base config.
    
    Args:
        preferred: Preferred brief configuration (from free-text parse or UI)
        
    Returns:
        Resolved brief configuration
    """
    log.info("[brief] Resolving brief configuration")
    
    # Load base brief from conf/brief.yaml
    try:
        base_brief = load_brief()
        log.info("[brief] Loaded base brief from conf/brief.yaml")
    except Exception as e:
        log.warning(f"[brief] Failed to load base brief: {e}, using defaults")
        base_brief = {
            "title": "Default Content",
            "intent": "narrative_history",
            "audience": ["general"],
            "tone": "informative",
            "video": {"target_length_min": 5, "target_length_max": 7},
            "blog": {"words_min": 900, "words_max": 1300},
            "keywords_include": [],
            "keywords_exclude": [],
            "sources_preferred": [],
            "monetization": {
                "primary": ["lead_magnet", "email_capture"],
                "cta_text": "Download our free guide"
            },
            "notes": ""
        }
    
    # If no preferred settings, return base
    if not preferred:
        log.info("[brief] No preferred settings, using base brief")
        return base_brief
    
    # Merge preferred over base
    resolved = base_brief.copy()
    resolved.update(preferred)
    
    # Ensure video config is properly merged
    if "video" in preferred and "video" in base_brief:
        resolved["video"] = {**base_brief["video"], **preferred["video"]}
    
    # Ensure monetization config is properly merged
    if "monetization" in preferred and "monetization" in base_brief:
        resolved["monetization"] = {**base_brief["monetization"], **preferred["monetization"]}
    
    log.info(f"[brief] Resolved fields: {list(resolved.keys())}")
    return resolved


if __name__ == "__main__":
    # CLI interface for testing and template creation
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create-template":
        path = create_brief_template()
        print(f"Created brief template at: {path}")
    else:
        try:
            brief = load_brief()
            print("Current brief:")
            print(yaml.dump(brief, default_flow_style=False, sort_keys=False))
        except Exception as e:
            print(f"Error loading brief: {e}")
            print("\nTo create a template, run: python brief_loader.py create-template")
