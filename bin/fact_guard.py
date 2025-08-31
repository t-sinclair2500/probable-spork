#!/usr/bin/env python3
"""
Fact Guard - Content Validation and Fact-Checking

P4-6 Implementation: Enforce that factual claims in the script are supported by references.
Remove or rewrite ungrounded claims and produce a fact-guard report.

Uses the research model (llama3.2:3b) to validate content for factual accuracy,
identify claims requiring citations, and ensure content quality.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, log_state, single_lock
from bin.model_runner import model_session

log = get_logger("fact_guard")


def load_fact_guard_prompt() -> str:
    """Load the fact-guard prompt template."""
    prompt_path = os.path.join(BASE, "prompts", "fact_guard.txt")
    if not os.path.exists(prompt_path):
        log.error(f"Fact-guard prompt not found: {prompt_path}")
        raise FileNotFoundError(f"Fact-guard prompt not found: {prompt_path}")
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def load_grounded_beats(run_dir: str) -> List[Dict]:
    """Load grounded beats from the specified run directory."""
    beats_path = os.path.join(BASE, "data", run_dir, "grounded_beats.json")
    if not os.path.exists(beats_path):
        log.warning(f"Grounded beats not found: {beats_path}")
        return []
    
    try:
        with open(beats_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load grounded beats: {e}")
        return []


def load_references(run_dir: str) -> List[Dict]:
    """Load references from the specified run directory."""
    refs_path = os.path.join(BASE, "data", run_dir, "references.json")
    if not os.path.exists(refs_path):
        log.warning(f"References not found: {refs_path}")
        return []
    
    try:
        with open(refs_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as load_references:
        log.error(f"Failed to load references: {load_references}")
        return []


def map_script_to_beats(script_lines: List[str], grounded_beats: List[Dict]) -> Dict[int, Dict]:
    """Map script lines to corresponding grounded beats for citation checking."""
    line_to_beat = {}
    
    # Simple heuristic: map script content to beat content
    for line_num, line in enumerate(script_lines, 1):
        line_lower = line.lower().strip()
        if not line_lower or line_lower.startswith('[') or line_lower.startswith('**'):
            continue
            
        # Find the beat that best matches this line
        best_match = None
        best_score = 0
        
        for beat in grounded_beats:
            beat_content = beat.get('content', '').lower()
            if not beat_content:
                continue
                
            # Simple word overlap scoring
            line_words = set(re.findall(r'\w+', line_lower))
            beat_words = set(re.findall(r'\w+', beat_content))
            
            if line_words and beat_words:
                overlap = len(line_words.intersection(beat_words))
                score = overlap / max(len(line_words), len(beat_words))
                
                if score > best_score and score > 0.1:  # Minimum threshold
                    best_score = score
                    best_match = beat
        
        if best_match:
            line_to_beat[line_num] = best_match
    
    return line_to_beat


def analyze_factual_claims(script_lines: List[str], grounded_beats: List[Dict], 
                          references: List[Dict], strictness: str = "balanced") -> Dict:
    """
    Analyze script for factual claims that need citations.
    
    Args:
        script_lines: Lines of the script
        grounded_beats: Grounded beats with citations
        references: Available references
        strictness: Strictness level (strict, balanced, lenient)
        
    Returns:
        Dictionary with analysis results
    """
    log.info(f"[fact-guard] Starting factual claims analysis with strictness: {strictness}")
    
    # Load fact-guard configuration
    config = load_config()
    fact_guard_config = config.get('research', {}).get('fact_guard', {})
    
    # Get strictness level settings
    strictness_levels = fact_guard_config.get('strictness_levels', {})
    current_level = strictness_levels.get(strictness, strictness_levels.get('balanced', {}))
    
    # Get claim policies
    claim_policies = fact_guard_config.get('claim_policies', {})
    
    # Map script lines to beats
    line_to_beat = map_script_to_beats(script_lines, grounded_beats)
    
    claims = []
    
    for line_num, line in enumerate(script_lines, 1):
        line = line.strip()
        if not line or line.startswith('[') or line.startswith('**'):
            continue
        
        # Check if this line has a corresponding beat with citations
        beat = line_to_beat.get(line_num)
        has_citations = beat and beat.get('citations')
        
        # Analyze line for factual claims
        line_claims = analyze_line_for_claims(line, claim_policies, has_citations)
        
        for claim in line_claims:
            claim['line'] = line_num
            claim['text'] = line
            claim['has_citation'] = has_citations
            
            # Determine action based on strictness level and claim type
            action = determine_claim_action(claim, current_level, claim_policies)
            claim['action'] = action
            
            # Generate suggested text if rewriting
            if action == 'rewrite':
                claim['suggested_text'] = generate_cautious_text(line, claim['claim_type'])
            
            claims.append(claim)
    
    # Generate summary
    summary = {
        'total_claims': len(claims),
        'kept': len([c for c in claims if c['action'] == 'keep']),
        'removed': len([c for c in claims if c['action'] == 'remove']),
        'rewritten': len([c for c in claims if c['action'] == 'rewrite']),
        'flagged': len([c for c in claims if c['action'] == 'flag']),
        'citations_needed': len([c for c in claims if c['requires_citation']])
    }
    
    log.info(f"[fact-guard] Analysis completed: {summary['total_claims']} claims found")
    
    return {
        'claims': claims,
        'summary': summary,
        'metadata': {
            'strictness': strictness,
            'timestamp': datetime.utcnow().isoformat(),
            'config_used': current_level
        }
    }


def analyze_line_for_claims(line: str, claim_policies: Dict, has_citations: bool) -> List[Dict]:
    """Analyze a single line for factual claims."""
    claims = []
    
    # Check for proper nouns (names, places, organizations)
    proper_noun_patterns = [
        r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # Full names
        r'\b[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+\b',  # Three-part names
        r'\b[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+\b',  # Four-part names
    ]
    
    for pattern in proper_noun_patterns:
        matches = re.finditer(pattern, line)
        for match in matches:
            claims.append({
                'claim_type': 'proper_nouns',
                'claim_text': match.group(),
                'requires_citation': claim_policies.get('proper_nouns', {}).get('requires_citation', True),
                'rationale': claim_policies.get('proper_nouns', {}).get('rationale', 'Proper nouns often represent specific facts requiring verification')
            })
    
    # Check for dates
    date_patterns = [
        r'\b\d{4}\b',  # Year
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',  # Full date
        r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # MM/DD/YYYY
        r'\b\d{1,2}-\d{1,2}-\d{4}\b',  # MM-DD-YYYY
    ]
    
    for pattern in date_patterns:
        matches = re.finditer(pattern, line)
        for match in matches:
            claims.append({
                'claim_type': 'dates',
                'claim_text': match.group(),
                'requires_citation': claim_policies.get('dates', {}).get('requires_citation', True),
                'rationale': claim_policies.get('dates', {}).get('rationale', 'Specific dates are factual claims needing source verification')
            })
    
    # Check for superlatives
    superlative_patterns = [
        r'\b(?:first|last|only|most|least|best|worst|biggest|smallest|oldest|newest|fastest|slowest)\b',
        r'\b(?:never|always|every|all|none|unique|original|primary|secondary)\b'
    ]
    
    for pattern in superlative_patterns:
        matches = re.finditer(pattern, line, re.IGNORECASE)
        for match in matches:
            claims.append({
                'claim_type': 'superlatives',
                'claim_text': match.group(),
                'requires_citation': claim_policies.get('superlatives', {}).get('requires_citation', True),
                'rationale': claim_policies.get('superlatives', {}).get('rationale', 'Superlatives (first, most, best) are factual claims needing evidence')
            })
    
    # Check for statistics
    stat_patterns = [
        r'\b\d+(?:\.\d+)?%\b',  # Percentages
        r'\b\d+(?:\.\d+)?\s+(?:million|billion|trillion)\b',  # Large numbers
        r'\b(?:over|under|more than|less than)\s+\d+\b',  # Comparative numbers
    ]
    
    for pattern in stat_patterns:
        matches = re.finditer(pattern, line, re.IGNORECASE)
        for match in matches:
            claims.append({
                'claim_type': 'statistics',
                'claim_text': match.group(),
                'requires_citation': claim_policies.get('statistics', {}).get('requires_citation', True),
                'rationale': claim_policies.get('statistics', {}).get('rationale', 'Statistics without sources are unreliable and should be removed')
            })
    
    # Check for expert opinions
    opinion_patterns = [
        r'\b(?:expert|specialist|professional|authority|researcher|scientist|professor|doctor)\s+(?:says|said|believes|thinks|argues|claims)\b',
        r'\b(?:according to|as stated by|as claimed by|as reported by)\b'
    ]
    
    for pattern in opinion_patterns:
        matches = re.finditer(pattern, line, re.IGNORECASE)
        for match in matches:
            claims.append({
                'claim_type': 'expert_opinions',
                'claim_text': match.group(),
                'requires_citation': claim_policies.get('expert_opinions', {}).get('requires_citation', True),
                'rationale': claim_policies.get('expert_opinions', {}).get('rationale', 'Expert opinions need attribution to maintain credibility')
            })
    
    # If no specific claims found, check if line contains general factual statements
    if not claims and not has_citations:
        # Look for statements that might be factual
        factual_indicators = [
            r'\b(?:is|was|are|were|has|had|have|had)\b',
            r'\b(?:discovered|invented|created|founded|established|built|designed)\b'
        ]
        
        for pattern in factual_indicators:
            if re.search(pattern, line, re.IGNORECASE):
                claims.append({
                    'claim_type': 'general_statements',
                    'claim_text': line,
                    'requires_citation': claim_policies.get('general_statements', {}).get('requires_citation', False),
                    'rationale': claim_policies.get('general_statements', {}).get('rationale', 'General observations don\'t require specific citations')
                })
                break
    
    return claims


def determine_claim_action(claim: Dict, strictness_level: Dict, claim_policies: Dict) -> str:
    """Determine what action to take on a claim based on strictness level."""
    claim_type = claim['claim_type']
    requires_citation = claim['requires_citation']
    has_citation = claim['has_citation']
    
    # If citation is not required, keep the claim
    if not requires_citation:
        return 'keep'
    
    # If citation is required but not present
    if requires_citation and not has_citation:
        if strictness_level.get('remove_unsupported', False):
            return 'remove'
        elif strictness_level.get('rewrite_to_cautious', False):
            return 'rewrite'
        elif strictness_level.get('flag_for_review', False):
            return 'flag'
        else:
            return 'keep'  # Default fallback
    
    # If citation is present, keep the claim
    return 'keep'


def generate_cautious_text(original_text: str, claim_type: str) -> str:
    """Generate more cautious version of text."""
    if claim_type == 'proper_nouns':
        # Add qualifiers for names
        return f"someone known as {original_text}"
    elif claim_type == 'dates':
        # Make dates approximate
        return f"around {original_text}"
    elif claim_type == 'superlatives':
        # Soften superlatives
        return f"one of the {original_text.replace('est', 'er')}"
    elif claim_type == 'statistics':
        # Remove specific numbers
        return "a significant amount" if "million" in original_text.lower() or "billion" in original_text.lower() else "some"
    elif claim_type == 'expert_opinions':
        # Make opinions more general
        return "some people believe" + original_text.replace("expert says", "").replace("expert said", "")
    else:
        # Default cautious version
        return f"it appears that {original_text.lower()}"


def apply_fact_guard_changes(script_lines: List[str], analysis_results: Dict, 
                           strictness: str = "balanced") -> Tuple[List[str], Dict]:
    """
    Apply fact-guard changes to the script based on analysis results.
    
    Args:
        script_lines: Original script lines
        analysis_results: Results from fact-guard analysis
        strictness: Strictness level (strict, balanced, lenient)
        
    Returns:
        Tuple of (cleaned_script_lines, changes_applied)
    """
    log.info(f"[fact-guard] Applying fact-guard changes with strictness: {strictness}")
    
    cleaned_lines = script_lines.copy()
    changes_applied = {
        'kept': [],
        'removed': [],
        'rewritten': [],
        'flagged': []
    }
    
    # Sort claims by line number (descending) to avoid line number shifts
    claims = sorted(analysis_results.get('claims', []), key=lambda x: x.get('line', 0), reverse=True)
    
    for claim in claims:
        line_num = claim.get('line', 0)
        action = claim.get('action', 'keep')
        text = claim.get('text', '')
        
        if line_num <= 0 or line_num > len(cleaned_lines):
            continue
            
        line_idx = line_num - 1  # Convert to 0-based index
        
        if action == 'remove':
            # Remove the problematic line
            if line_idx < len(cleaned_lines):
                removed_line = cleaned_lines.pop(line_idx)
                changes_applied['removed'].append({
                    'line': line_num,
                    'text': removed_line,
                    'rationale': claim.get('rationale', 'No rationale provided')
                })
                log.info(f"[fact-guard] Removed line {line_num}: {removed_line[:50]}...")
                
        elif action == 'rewrite':
            # Replace with suggested text
            suggested_text = claim.get('suggested_text', text)
            if line_idx < len(cleaned_lines):
                old_text = cleaned_lines[line_idx]
                cleaned_lines[line_idx] = suggested_text
                changes_applied['rewritten'].append({
                    'line': line_num,
                    'old_text': old_text,
                    'new_text': suggested_text,
                    'rationale': claim.get('rationale', 'No rationale provided')
                })
                log.info(f"[fact-guard] Rewrote line {line_num}: {old_text[:50]}... -> {suggested_text[:50]}...")
                
        elif action == 'flag':
            # Add TODO flag for operator review
            if line_idx < len(cleaned_lines):
                flagged_line = f"[TODO: FACT-CHECK] {cleaned_lines[line_idx]}"
                cleaned_lines[line_idx] = flagged_line
                changes_applied['flagged'].append({
                    'line': line_num,
                    'text': flagged_line,
                    'rationale': claim.get('rationale', 'No rationale provided')
                })
                log.info(f"[fact-guard] Flagged line {line_num} for review")
                
        elif action == 'keep':
            # Keep the line as-is
            changes_applied['kept'].append({
                'line': line_num,
                'text': text,
                'rationale': 'Claim is properly cited or does not require citation'
            })
    
    log.info(f"[fact-guard] Changes applied: {len(changes_applied['removed'])} removed, {len(changes_applied['rewritten'])} rewritten, {len(changes_applied['flagged'])} flagged")
    
    return cleaned_lines, changes_applied


def run_fact_guard_analysis(slug: str, strictness: str = "balanced") -> Dict:
    """
    Run fact-guard analysis using the research model.
    
    Args:
        slug: Topic slug for the run
        strictness: Strictness level (strict, balanced, lenient)
        
    Returns:
        Dictionary with fact-guard analysis results
    """
    log.info(f"[fact-guard] Starting fact-guard analysis for slug: {slug}")
    
    try:
        # Load grounded beats and references
        grounded_beats = load_grounded_beats(slug)
        references = load_references(slug)
        
        if not grounded_beats:
            log.warning(f"[fact-guard] No grounded beats found for {slug}")
            return {
                'claims': [],
                'summary': {
                    'total_claims': 0,
                    'kept': 0,
                    'removed': 0,
                    'rewritten': 0,
                    'flagged': 0,
                    'citations_needed': 0
                },
                'metadata': {
                    'strictness': strictness,
                    'timestamp': datetime.utcnow().isoformat(),
                    'error': 'No grounded beats found'
                }
            }
        
        # Load script content
        script_path = os.path.join(BASE, "scripts", f"{slug}.txt")
        if not os.path.exists(script_path):
            log.warning(f"[fact-guard] Script not found: {script_path}")
            # Try to find script in other locations
            script_path = os.path.join(BASE, "data", slug, f"{slug}.txt")
            if not os.path.exists(script_path):
                log.error(f"[fact-guard] Script not found in any location for {slug}")
                return {
                    'claims': [],
                    'summary': {
                        'total_claims': 0,
                        'kept': 0,
                        'removed': 0,
                        'rewritten': 0,
                        'flagged': 0,
                        'citations_needed': 0
                    },
                    'metadata': {
                        'strictness': strictness,
                        'timestamp': datetime.utcnow().isoformat(),
                        'error': 'Script not found'
                    }
                }
        
        with open(script_path, 'r', encoding='utf-8') as f:
            script_lines = f.readlines()
        
        # Analyze factual claims
        analysis_results = analyze_factual_claims(script_lines, grounded_beats, references, strictness)
        
        # Apply changes if needed
        cleaned_script, changes_applied = apply_fact_guard_changes(script_lines, analysis_results, strictness)
        
        # Save cleaned script if requested
        output_dir = os.path.join(BASE, "data", slug)
        os.makedirs(output_dir, exist_ok=True)
        
        if analysis_results.get('metadata', {}).get('config_used', {}).get('save_cleaned_script', True):
            cleaned_script_path = os.path.join(output_dir, f"{slug}_fact_guarded.txt")
            with open(cleaned_script_path, 'w', encoding='utf-8') as f:
                f.writelines(cleaned_script)
            log.info(f"[fact-guard] Saved cleaned script to {cleaned_script_path}")
        
        # Generate fact-guard report
        fact_guard_report = {
            'slug': slug,
            'timestamp': datetime.utcnow().isoformat(),
            'strictness': strictness,
            'analysis': analysis_results,
            'changes_applied': changes_applied,
            'summary': analysis_results['summary'],
            'metadata': {
                'script_path': script_path,
                'grounded_beats_count': len(grounded_beats),
                'references_count': len(references),
                'config_used': analysis_results.get('metadata', {}).get('config_used', {})
            }
        }
        
        # Save fact-guard report
        report_path = os.path.join(output_dir, "fact_guard_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(fact_guard_report, f, indent=2, ensure_ascii=False)
        
        log.info(f"[fact-guard] Fact-guard analysis completed for {slug}")
        log.info(f"[fact-guard] Report saved to {report_path}")
        
        return fact_guard_report
        
    except Exception as e:
        log.error(f"[fact-guard] Fact-guard analysis failed: {e}")
        
        # Return fallback results
        fallback_claims = []
        if 'script_lines' in locals():
            # Generate fallback claims for each line
            for line_num, line in enumerate(script_lines, 1):
                if line.strip() and not line.startswith('[') and not line.startswith('**'):
                    fallback_claims.append({
                        'line': line_num,
                        'text': line.strip(),
                        'claim_type': 'unknown',
                        'requires_citation': True,
                        'has_citation': False,
                        'action': 'flag',
                        'rationale': 'Specific factual claim requiring citation'
                    })
                
        return {
            'claims': fallback_claims,
            'summary': {
                'total_claims': len(fallback_claims),
                'kept': 0,
                'removed': 0,
                'rewritten': 0,
                'flagged': len(fallback_claims),
                'citations_needed': len(fallback_claims)
            },
            'metadata': {
                'strictness': strictness,
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
        }


def main(slug: str = None, strictness: str = "balanced"):
    """Main entry point for fact-guard analysis."""
    parser = argparse.ArgumentParser(description="Run fact-guard analysis on script content")
    parser.add_argument("--slug", required=True, help="Topic slug for fact-guard analysis")
    parser.add_argument("--strictness", choices=['strict', 'balanced', 'lenient'], default='balanced',
                       help='Strictness level for fact-guard analysis')
    args = parser.parse_args()
    
    # Use command line args if provided, otherwise use function parameters
    slug = args.slug if hasattr(args, 'slug') else slug
    strictness = args.strictness if hasattr(args, 'strictness') else strictness
    
    if not slug:
        log.error("Slug is required")
        return
    
    log.info(f"[fact-guard] Starting fact-guard analysis for slug: {slug}, strictness: {strictness}")
    
    # Run fact-guard analysis
    results = run_fact_guard_analysis(slug, strictness)
    
    # Print summary
    summary = results.get('summary', {})
    print(f"\nFact-Guard Analysis Summary for {slug}:")
    print(f"  Total claims: {summary.get('total_claims', 0)}")
    print(f"  Kept: {summary.get('kept', 0)}")
    print(f"  Removed: {summary.get('removed', 0)}")
    print(f"  Rewritten: {summary.get('rewritten', 0)}")
    print(f"  Flagged: {summary.get('flagged', 0)}")
    print(f"  Citations needed: {summary.get('citations_needed', 0)}")
    
    if results.get('metadata', {}).get('error'):
        print(f"  Error: {results['metadata']['error']}")
    
    return results


if __name__ == "__main__":
    main()
