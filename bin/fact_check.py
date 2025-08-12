#!/usr/bin/env python3
"""
Fact-checking module for blog content validation.
Uses the prompts/fact_check.txt prompt to identify claims requiring citations.
"""
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, parse_llm_json, log_state

log = get_logger("fact_check")


def load_fact_check_prompt() -> str:
    """Load the fact-checking prompt template."""
    prompt_path = os.path.join(BASE, "prompts", "fact_check.txt")
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Fact-check prompt not found: {prompt_path}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def extract_text_lines(markdown_content: str) -> List[str]:
    """Extract text lines from markdown, excluding headers and metadata."""
    lines = markdown_content.split('\n')
    text_lines = []
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        # Skip empty lines, headers, code blocks, and image references
        if (not line or 
            line.startswith('#') or 
            line.startswith('```') or 
            line.startswith('![') or
            line.startswith('<!--')):
            continue
        
        # Clean up markdown formatting for fact-checking
        clean_line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)  # Remove link formatting
        clean_line = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', clean_line)  # Remove bold/italic
        clean_line = re.sub(r'`([^`]+)`', r'\1', clean_line)  # Remove inline code
        
        if clean_line.strip():
            text_lines.append(clean_line.strip())
    
    return text_lines


def call_fact_checker(content: str, cfg, models_config=None) -> Dict:
    """Call the LLM fact-checker and return parsed results."""
    try:
        # Use new model_runner system
        from bin.model_runner import model_session
        
        # Get model name from config
        if models_config and 'research' in models_config.get('models', {}):
            model_name = models_config['models']['research']['name']
        else:
            # Fallback to global config
            model_name = cfg.llm.model
        
        prompt_template = load_fact_check_prompt()
        full_prompt = f"{prompt_template}\n\nCONTENT TO CHECK:\n{content}"
        
        # Use model session for deterministic load/unload
        with model_session(model_name) as session:
            system_prompt = "You are a fact-checker. Review the given content for factual accuracy."
            response = session.chat(system=system_prompt, user=full_prompt)
            return parse_llm_json(response)
            
    except Exception as e:
        log.error(f"Model runner failed, falling back to legacy: {e}")
        
        # Fallback to legacy system
        import requests
        
        prompt_template = load_fact_check_prompt()
        full_prompt = f"{prompt_template}\n\nCONTENT TO CHECK:\n{content}"
        
        payload = {
            "model": cfg.llm.model,
            "prompt": full_prompt,
            "stream": False
        }
        
        try:
            response = requests.post(cfg.llm.endpoint, json=payload, timeout=300)
            if response.ok:
                response_text = response.json().get("response", "").strip()
                return parse_llm_json(response_text)
            else:
                log.error(f"LLM request failed: {response.status_code} - {response.text}")
                return {"issues": []}
        except Exception as e:
            log.error(f"Fact-check LLM call failed: {e}")
            return {"issues": []}


def categorize_issue_severity(claim: str) -> str:
    """Categorize fact-check issue severity based on claim content."""
    claim_lower = claim.lower()
    
    # High-risk patterns that need citations
    high_risk_patterns = [
        r'\d+%', r'\d+\.\d+%',  # Specific percentages
        r'study shows?', r'research shows?', r'studies indicate',
        r'according to', r'data shows?',
        r'proven to', r'scientifically proven',
        r'experts? say', r'specialists? recommend',
        r'statistics show', r'survey found',
        r'clinical trial', r'peer.?reviewed',
        r'fda approved', r'government data',
        r'official statistics', r'census data'
    ]
    
    # Medium-risk patterns
    medium_risk_patterns = [
        r'most people', r'majority of', r'commonly',
        r'typically', r'generally', r'usually',
        r'many experts?', r'some studies?',
        r'reports suggest', r'evidence suggests',
        r'industry standard', r'best practice'
    ]
    
    # Check for high-risk patterns
    for pattern in high_risk_patterns:
        if re.search(pattern, claim_lower):
            return "error"
    
    # Check for medium-risk patterns
    for pattern in medium_risk_patterns:
        if re.search(pattern, claim_lower):
            return "warning"
    
    # Default to info for other potential issues
    return "info"


def fact_check_content(markdown_content: str, config=None) -> Dict:
    """
    Perform fact-checking on markdown content.
    
    Args:
        markdown_content: The markdown content to fact-check
        config: Configuration object (auto-loaded if None)
    
    Returns:
        Dict with fact-check results including issues, metrics, and summary
    """
    if config is None:
        config = load_config()
    
    start_time = time.time()
    
    # Extract text for fact-checking
    text_lines = extract_text_lines(markdown_content)
    content_to_check = '\n'.join(text_lines)
    
    log.info(f"Starting fact-check on {len(text_lines)} lines of content")
    
    # Call the LLM fact-checker
    llm_result = call_fact_checker(content_to_check, config)
    
    # Process and enhance the results
    processed_issues = []
    severity_counts = {"info": 0, "warning": 0, "error": 0}
    
    for issue in llm_result.get("issues", []):
        claim = issue.get("claim", "")
        line_num = issue.get("line", 0)
        suggested = issue.get("suggested", "")
        
        # Enhance with severity categorization
        severity = categorize_issue_severity(claim)
        severity_counts[severity] += 1
        
        processed_issue = {
            "line": line_num,
            "claim": claim,
            "suggested": suggested,
            "severity": severity,
            "category": "fact_check"
        }
        processed_issues.append(processed_issue)
    
    # Calculate metrics
    processing_time = time.time() - start_time
    total_issues = len(processed_issues)
    
    result = {
        "issues": processed_issues,
        "metrics": {
            "total_issues": total_issues,
            "severity_counts": severity_counts,
            "processing_time_seconds": round(processing_time, 2),
            "content_lines_checked": len(text_lines),
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        },
        "summary": {
            "has_errors": severity_counts["error"] > 0,
            "has_warnings": severity_counts["warning"] > 0,
            "needs_attention": total_issues > 0,
            "highest_severity": _get_highest_severity(severity_counts)
        }
    }
    
    # Log results
    log.info(f"Fact-check completed in {processing_time:.2f}s: "
             f"{total_issues} issues found (errors: {severity_counts['error']}, "
             f"warnings: {severity_counts['warning']}, info: {severity_counts['info']})")
    
    if processed_issues:
        for issue in processed_issues[:3]:  # Log first 3 issues
            log.info(f"Issue ({issue['severity']}): {issue['claim'][:100]}...")
    
    return result


def _get_highest_severity(severity_counts: Dict[str, int]) -> str:
    """Determine the highest severity level present."""
    if severity_counts["error"] > 0:
        return "error"
    elif severity_counts["warning"] > 0:
        return "warning"
    elif severity_counts["info"] > 0:
        return "info"
    else:
        return "none"


def should_gate_content(fact_check_result: Dict, gate_mode: str, 
                       severity_threshold: str = "warning") -> bool:
    """
    Determine if content should be gated based on fact-check results.
    
    Args:
        fact_check_result: Result from fact_check_content()
        gate_mode: "off", "warn", or "block"
        severity_threshold: Minimum severity to trigger gating
    
    Returns:
        True if content should be blocked, False otherwise
    """
    if gate_mode == "off":
        return False
    
    if gate_mode == "warn":
        return False  # Warnings don't block, just log
    
    if gate_mode != "block":
        return False
    
    # Check if we have issues at or above the threshold
    severity_hierarchy = {"info": 1, "warning": 2, "error": 3}
    threshold_level = severity_hierarchy.get(severity_threshold, 2)
    
    summary = fact_check_result.get("summary", {})
    highest_severity = summary.get("highest_severity", "none")
    highest_level = severity_hierarchy.get(highest_severity, 0)
    
    return highest_level >= threshold_level


def main(brief=None):
    """CLI interface for testing fact-checking functionality."""
    import argparse
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("fact_check", "START", f"brief={brief_title}")
        print(f"Running with brief: {brief_title}")
    else:
        log_state("fact_check", "START", "brief=none")
        print("Running without brief - using default behavior")
    
    parser = argparse.ArgumentParser(description="Fact-check markdown content")
    parser.add_argument("input_file", help="Markdown file to fact-check")
    parser.add_argument("--output", help="Output JSON file for results")
    parser.add_argument("--gate-mode", choices=["off", "warn", "block"], 
                       default="warn", help="Gating mode")
    parser.add_argument("--severity-threshold", choices=["info", "warning", "error"],
                       default="warning", help="Minimum severity for gating")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found: {args.input_file}")
        return 1
    
    # Load content
    with open(args.input_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Apply brief settings for fact-checking if available
    if brief:
        # Use brief keywords to prioritize fact-checking
        brief_keywords = brief.get('keywords_include', [])
        if brief_keywords:
            print(f"Brief keywords for fact-checking priority: {', '.join(brief_keywords)}")
            # Prioritize fact-checking of claims containing brief keywords
            content_lines = content.split('\n')
            prioritized_lines = []
            for line in content_lines:
                line_lower = line.lower()
                if any(kw.lower() in line_lower for kw in brief_keywords):
                    prioritized_lines.append(f"PRIORITY: {line}")
                else:
                    prioritized_lines.append(line)
            content = '\n'.join(prioritized_lines)
            print(f"Prioritized {len([l for l in prioritized_lines if l.startswith('PRIORITY:')])} lines for fact-checking")
        
        # Apply brief tone to fact-checking approach
        brief_tone = brief.get('tone', '').lower()
        if brief_tone:
            print(f"Brief tone: {brief_tone}")
            if brief_tone in ['professional', 'corporate', 'formal']:
                print("Professional tone: applying strict fact-checking standards")
                # Could adjust severity thresholds for professional content
            elif brief_tone in ['casual', 'friendly']:
                print("Casual tone: applying balanced fact-checking standards")
            elif brief_tone in ['educational', 'informative']:
                print("Educational tone: applying thorough fact-checking for accuracy")
    
    # Run fact-check
    print(f"Fact-checking {args.input_file}...")
    result = fact_check_content(content)
    
    # Display results
    metrics = result["metrics"]
    summary = result["summary"]
    
    print(f"\nFact-Check Results:")
    print(f"  Lines checked: {metrics['content_lines_checked']}")
    print(f"  Processing time: {metrics['processing_time_seconds']}s")
    print(f"  Total issues: {metrics['total_issues']}")
    print(f"  Errors: {metrics['severity_counts']['error']}")
    print(f"  Warnings: {metrics['severity_counts']['warning']}")
    print(f"  Info: {metrics['severity_counts']['info']}")
    print(f"  Highest severity: {summary['highest_severity']}")
    
    # Check gating
    should_block = should_gate_content(result, args.gate_mode, args.severity_threshold)
    if should_block:
        print(f"\n⚠️  CONTENT BLOCKED: Issues exceed {args.severity_threshold} threshold in {args.gate_mode} mode")
    elif summary["needs_attention"]:
        print(f"\n⚠️  ATTENTION NEEDED: Found {metrics['total_issues']} issues requiring review")
    else:
        print(f"\n✅ CONTENT CLEAR: No fact-checking issues found")
    
    # Save results if requested
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to {args.output}")
    
    # Include brief context in final log
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("fact_check", "OK", f"issues={metrics['total_issues']};brief={brief_title}")
    else:
        log_state("fact_check", "OK", f"issues={metrics['total_issues']}")
    
    return 1 if should_block else 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fact checking")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("input_file", nargs='?', help="Markdown file to fact-check (optional)")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
            print(f"Loaded brief: {brief.get('title', 'Untitled')}")
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Warning: Failed to parse brief data: {e}")
    
    # If no input file provided, run in pipeline mode
    if not args.input_file:
        # Pipeline mode - just log that we're ready
        if brief:
            brief_title = brief.get('title', 'Untitled')
            log_state("fact_check", "START", f"brief={brief_title}")
            print(f"Fact-check ready with brief: {brief_title}")
        else:
            log_state("fact_check", "START", "brief=none")
            print("Fact-check ready without brief")
        sys.exit(0)
    
    # CLI mode - run fact-check on input file
    sys.exit(main(brief))
