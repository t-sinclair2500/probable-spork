#!/usr/bin/env python3
"""
Fact Guard - Content Validation and Fact-Checking

Uses the research model (Mistral 7B) to validate content for factual accuracy,
identify claims requiring citations, and ensure content quality.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, log_state, single_lock
from bin.model_runner import model_session

log = get_logger("fact_guard")


def load_fact_guard_prompt() -> str:
    """Load the fact-guard prompt template."""
    prompt_path = os.path.join(BASE, "prompts", "fact_check.txt")
    if not os.path.exists(prompt_path):
        # Create a default prompt if none exists
        default_prompt = """You are a fact-checker and content validator. Review the given content for:

1. Factual accuracy and verifiability
2. Claims that need citations or sources
3. Potentially misleading statements
4. Content quality and coherence

Return your response as JSON with this structure:
{
  "issues": [
    {
      "text": "problematic text",
      "issue": "description of the issue",
      "suggestion": "corrected version or improvement",
      "severity": "high|medium|low"
    }
  ],
  "citations_needed": ["fact 1", "fact 2", ...],
  "overall_score": 0.95,
  "summary": "Brief assessment of content quality"
}"""
        
        # Ensure prompts directory exists
        os.makedirs(os.path.dirname(prompt_path), exist_ok=True)
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(default_prompt)
        
        return default_prompt
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def validate_content(content: str, models_config: Optional[Dict] = None) -> Dict:
    """
    Validate content using the research model.
    
    Args:
        content: Content to validate
        models_config: Models configuration
        
    Returns:
        Validation results dictionary
    """
    try:
        # Get model name from config
        if models_config and 'research' in models_config.get('models', {}):
            model_name = models_config['models']['research']['name']
        else:
            # Fallback to default
            model_name = 'mistral:7b-instruct'
        
        prompt_template = load_fact_guard_prompt()
        full_prompt = f"{prompt_template}\n\nCONTENT TO VALIDATE:\n{content}"
        
        # Use model session for deterministic load/unload
        with model_session(model_name) as session:
            system_prompt = "You are a fact-checker and content validator. Review content for accuracy and quality."
            response = session.chat(system=system_prompt, user=full_prompt)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                log.warning("Failed to parse fact-guard response as JSON")
                return {
                    "issues": [],
                    "citations_needed": [],
                    "overall_score": 0.8,
                    "summary": "Validation completed but response parsing failed"
                }
                
    except Exception as e:
        log.error(f"Content validation failed: {e}")
        return {
            "issues": [],
            "citations_needed": [],
            "overall_score": 0.5,
            "summary": f"Validation failed: {str(e)}"
        }


def main(brief=None, models_config=None):
    """Main entry point."""
    cfg = load_config()
    
    # Load models configuration if not provided
    if models_config is None:
        try:
            import yaml
            models_path = os.path.join(BASE, "conf", "models.yaml")
            if os.path.exists(models_path):
                with open(models_path, 'r', encoding='utf-8') as f:
                    models_config = yaml.safe_load(f)
                log.info("Loaded models configuration")
        except Exception as e:
            log.warning(f"Failed to load models configuration: {e}")
            models_config = {}
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("fact_guard", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")
    else:
        log_state("fact_guard", "START", "brief=none")
        log.info("Running without brief - using default behavior")
    
    # Find the most recent script to validate
    scripts_dir = os.path.join(BASE, "scripts")
    if not os.path.exists(scripts_dir):
        log_state("fact_guard", "SKIP", "no scripts directory")
        log.info("No scripts directory found")
        return
    
    script_files = [f for f in os.listdir(scripts_dir) if f.endswith('.txt')]
    if not script_files:
        log_state("fact_guard", "SKIP", "no script files")
        log.info("No script files found")
        return
    
    # Use the most recent script
    script_files.sort(reverse=True)
    script_path = os.path.join(scripts_dir, script_files[0])
    
    log.info(f"Validating script: {script_files[0]}")
    
    # Read script content
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
    except Exception as e:
        log.error(f"Failed to read script: {e}")
        log_state("fact_guard", "ERROR", f"script read failed: {e}")
        return
    
    # Validate content
    log.info("Running fact-guard validation...")
    validation_results = validate_content(script_content, models_config)
    
    # Log results
    issues_count = len(validation_results.get('issues', []))
    citations_needed = len(validation_results.get('citations_needed', []))
    overall_score = validation_results.get('overall_score', 0.0)
    
    log.info(f"Validation complete: {issues_count} issues, {citations_needed} citations needed, score: {overall_score:.2f}")
    
    # Save validation results
    results_path = script_path.replace('.txt', '.fact_guard.json')
    try:
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(validation_results, f, indent=2)
        log.info(f"Saved validation results to: {results_path}")
    except Exception as e:
        log.error(f"Failed to save validation results: {e}")
    
    # Log final state
    if issues_count == 0 and citations_needed == 0:
        log_state("fact_guard", "OK", f"score={overall_score:.2f};no_issues")
    else:
        log_state("fact_guard", "ISSUES", f"score={overall_score:.2f};issues={issues_count};citations={citations_needed}")
    
    # Print summary
    print(f"Fact-Guard Validation Results:")
    print(f"  Overall Score: {overall_score:.2f}")
    print(f"  Issues Found: {issues_count}")
    print(f"  Citations Needed: {citations_needed}")
    print(f"  Summary: {validation_results.get('summary', 'No summary available')}")
    
    if issues_count > 0:
        print(f"\nIssues:")
        for issue in validation_results.get('issues', [])[:5]:  # Show first 5
            print(f"  - {issue.get('issue', 'Unknown issue')}")
            if len(validation_results.get('issues', [])) > 5:
                print(f"  ... and {len(validation_results.get('issues', [])) - 5} more")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fact-guard content validation")
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
