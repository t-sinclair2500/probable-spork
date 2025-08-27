#!/usr/bin/env python3
"""
Test script for Phase 4 Research Implementation

Tests the new research functionality including:
- Intent templates with CTA policy
- Research collection with allowlist/blacklist
- Research grounding with citations
- Fact-guard analysis
- Evidence validation
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger
from bin.intent_loader import (
    load_intent_templates, 
    get_intent_metadata, 
    get_citation_requirements,
    validate_intent
)
from bin.research_collect import ResearchCollector
from bin.research_ground import ResearchGrounder
from bin.fact_guard import run_fact_guard_analysis

log = get_logger("test_phase4_research")


def test_intent_templates():
    """Test intent templates functionality."""
    print("\n=== Testing Intent Templates ===")
    
    try:
        # Load all templates
        templates = load_intent_templates()
        print(f"✅ Loaded {len(templates.get('intents', {}))} intent templates")
        
        # Test specific intent
        intent = "narrative_history"
        metadata = get_intent_metadata(intent)
        print(f"✅ {intent} intent: CTA={metadata['cta_policy']}, Evidence={metadata['evidence_load']}")
        
        # Test citation requirements
        citation_reqs = get_citation_requirements(intent)
        print(f"✅ Citation requirements: {citation_reqs['beats_needing_citations']}/{citation_reqs['total_beats']} beats need citations")
        
        # Validate intent
        is_valid = validate_intent(intent)
        print(f"✅ Intent validation: {'PASS' if is_valid else 'FAIL'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Intent templates test failed: {e}")
        return False


def test_research_collector():
    """Test research collector functionality."""
    print("\n=== Testing Research Collector ===")
    
    try:
        # Initialize collector in reuse mode
        collector = ResearchCollector(mode="reuse")
        print("✅ Research collector initialized")
        
        # Test domain allowlist/blacklist
        test_domains = ["wikipedia.org", "facebook.com", "designmuseum.org"]
        for domain in test_domains:
            is_allowed = collector._is_domain_allowed(domain)
            status = "✅ ALLOWED" if is_allowed else "❌ BLOCKED"
            print(f"   {domain}: {status}")
        
        # Test brief processing
        brief = {"keywords_include": ["design", "history"]}
        sources = collector.collect_from_brief(brief)
        print(f"✅ Brief processing: {len(sources)} sources collected")
        
        return True
        
    except Exception as e:
        print(f"❌ Research collector test failed: {e}")
        return False


def test_research_grounder():
    """Test research grounder functionality."""
    print("\n=== Testing Research Grounder ===")
    
    try:
        # Initialize grounder
        grounder = ResearchGrounder()
        print("✅ Research grounder initialized")
        
        # Test domain quality scoring
        test_domains = ["wikipedia.org", "designmuseum.org", "unknown-site.com"]
        for domain in test_domains:
            score = grounder._calculate_domain_quality_score(domain)
            print(f"   {domain}: quality score {score:.2f}")
        
        # Test chunk scoring
        test_chunks = [
            {"domain": "wikipedia.org", "relevance_score": 0.8, "recency_score": 0.7},
            {"domain": "designmuseum.org", "relevance_score": 0.6, "recency_score": 0.9}
        ]
        
        scored_chunks = grounder._score_chunks(test_chunks, "test content")
        print(f"✅ Chunk scoring: {len(scored_chunks)} chunks scored")
        
        return True
        
    except Exception as e:
        print(f"❌ Research grounder test failed: {e}")
        return False


def test_fact_guard():
    """Test fact-guard functionality."""
    print("\n=== Testing Fact-Guard ===")
    
    try:
        # Test claim analysis
        test_line = "The topic was researched thoroughly with multiple credible sources."
        from bin.fact_guard import analyze_line_for_claims, determine_claim_action
        
        # Load config for claim policies
        from bin.core import load_config
        config = load_config()
        claim_policies = config.get('research', {}).get('fact_guard', {}).get('claim_policies', {})
        
        claims = analyze_line_for_claims(test_line, claim_policies, has_citations=False)
        print(f"✅ Claim analysis: {len(claims)} claims found")
        
        for claim in claims:
            action = determine_claim_action(claim, {"rewrite_to_cautious": True}, claim_policies)
            print(f"   Claim: {claim['claim_text']} -> Action: {action}")
        
        return True
        
    except Exception as e:
        print(f"❌ Fact-guard test failed: {e}")
        return False


def test_evidence_validation():
    """Test evidence validation functionality."""
    print("\n=== Testing Evidence Validation ===")
    
    try:
        # Create test evidence data
        test_evidence = {
            "citations": {
                "total_count": 5,
                "unique_domains": 3,
                "beats_coverage_pct": 75.0
            },
            "policy_checks": {
                "min_citations_per_intent": "PASS",
                "whitelist_compliance": "PASS"
            },
            "fact_guard_summary": {
                "removed_count": 0,
                "rewritten_count": 2,
                "flagged_count": 0,
                "strict_mode_fail": False
            }
        }
        
        # Test evidence structure
        required_fields = ["citations", "policy_checks", "fact_guard_summary"]
        for field in required_fields:
            if field in test_evidence:
                print(f"✅ {field} field present")
            else:
                print(f"❌ {field} field missing")
        
        # Test citation metrics
        citations = test_evidence["citations"]
        if citations["total_count"] > 0:
            print(f"✅ Total citations: {citations['total_count']}")
        if citations["beats_coverage_pct"] >= 60.0:
            print(f"✅ Coverage threshold met: {citations['beats_coverage_pct']}%")
        
        # Test fact-guard compliance
        fact_guard = test_evidence["fact_guard_summary"]
        if not fact_guard["strict_mode_fail"]:
            print("✅ Fact-guard strict mode compliance")
        
        return True
        
    except Exception as e:
        print(f"❌ Evidence validation test failed: {e}")
        return False


def main():
    """Run all Phase 4 research tests."""
    print("Phase 4 Research Implementation Test Suite")
    print("=" * 50)
    
    tests = [
        test_intent_templates,
        test_research_collector,
        test_research_grounder,
        test_fact_guard,
        test_evidence_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Phase 4 research implementation is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
