"""
Workstream Brief Loader

Centralized brief configuration that the entire pipeline reads first.
Supports both YAML and Markdown front-matter formats.
"""

import os
import re
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


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
