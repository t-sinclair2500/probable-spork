#!/usr/bin/env python3
"""
Research Report Generator

Generates compact summaries of research coverage and citations statistics for a topic.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, log_state, single_lock

log = get_logger("research_report")


def load_grounded_beats(slug: str) -> List[Dict]:
    """Load grounded beats for a topic."""
    beats_path = os.path.join(BASE, "data", slug, "grounded_beats.json")
    if not os.path.exists(beats_path):
        log.warning(f"Grounded beats not found: {beats_path}")
        return []
    
    try:
        with open(beats_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load grounded beats: {e}")
        return []


def load_references(slug: str) -> List[Dict]:
    """Load references for a topic."""
    refs_path = os.path.join(BASE, "data", slug, "references.json")
    if not os.path.exists(refs_path):
        log.warning(f"References not found: {refs_path}")
        return []
    
    try:
        with open(refs_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load references: {e}")
        return []


def load_fact_guard_report(slug: str) -> Optional[Dict]:
    """Load fact-guard report for a topic."""
    report_path = os.path.join(BASE, "data", slug, "fact_guard_report.json")
    if not os.path.exists(report_path):
        return None
    
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load fact-guard report: {e}")
        return None


def generate_research_report(slug: str) -> Dict:
    """Generate comprehensive research report for a topic."""
    log.info(f"Generating research report for: {slug}")
    
    # Load all research artifacts
    grounded_beats = load_grounded_beats(slug)
    references = load_references(slug)
    fact_guard_report = load_fact_guard_report(slug)
    
    # Calculate citation statistics
    total_beats = len(grounded_beats)
    beats_with_citations = 0
    total_citations = 0
    citation_domains = set()
    citation_recency = []
    
    for beat in grounded_beats:
        citations = beat.get('citations', [])
        if citations:
            beats_with_citations += 1
            total_citations += len(citations)
            
            # Extract domain and recency info from citations
            for citation in citations:
                if isinstance(citation, dict):
                    domain = citation.get('domain', 'unknown')
                    if domain:
                        citation_domains.add(domain)
                    
                    timestamp = citation.get('timestamp', citation.get('collected_at'))
                    if timestamp:
                        try:
                            if isinstance(timestamp, str):
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            else:
                                dt = datetime.fromtimestamp(timestamp)
                            citation_recency.append(dt)
                        except:
                            pass
    
    # Calculate coverage percentage
    coverage_pct = (beats_with_citations / total_beats * 100) if total_beats > 0 else 0
    
    # Calculate average citations per beat
    avg_citations = (total_citations / total_beats) if total_beats > 0 else 0
    
    # Calculate recency statistics
    recency_stats = {}
    if citation_recency:
        now = datetime.now()
        ages = [(now - dt).days for dt in citation_recency]
        recency_stats = {
            "oldest_days": max(ages),
            "newest_days": min(ages),
            "avg_age_days": sum(ages) / len(ages)
        }
    
    # Fact-guard statistics
    fact_guard_stats = {}
    if fact_guard_report:
        summary = fact_guard_report.get('summary', {})
        fact_guard_stats = {
            "total_claims": summary.get('total_claims', 0),
            "kept": summary.get('kept', 0),
            "removed": summary.get('removed', 0),
            "rewritten": summary.get('rewritten', 0),
            "flagged": summary.get('flagged', 0)
        }
    
    # Generate report
    report = {
        "slug": slug,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_beats": total_beats,
            "beats_with_citations": beats_with_citations,
            "coverage_percentage": round(coverage_pct, 1),
            "total_citations": total_citations,
            "avg_citations_per_beat": round(avg_citations, 2)
        },
        "citations": {
            "unique_domains": len(citation_domains),
            "domain_list": sorted(list(citation_domains)),
            "recency": recency_stats
        },
        "fact_guard": fact_guard_stats,
        "acceptance_gates": {
            "citation_minimum_met": coverage_pct >= 60,
            "avg_citations_met": avg_citations >= 1.0,
            "fact_guard_clean": fact_guard_stats.get('removed', 0) == 0
        }
    }
    
    return report


def print_compact_summary(report: Dict):
    """Print a compact summary of the research report."""
    summary = report['summary']
    citations = report['citations']
    fact_guard = report['fact_guard']
    gates = report['acceptance_gates']
    
    print(f"\n📊 Research Report: {report['slug']}")
    print(f"   Generated: {report['generated_at']}")
    print()
    
    print(f"📝 Coverage:")
    print(f"   Beats: {summary['total_beats']} total, {summary['beats_with_citations']} with citations")
    print(f"   Coverage: {summary['coverage_percentage']}% ({'✅' if gates['citation_minimum_met'] else '❌'} ≥60%)")
    print(f"   Citations: {summary['total_citations']} total, {summary['avg_citations_per_beat']:.2f} avg/beat")
    print(f"   Avg Citations: {'✅' if gates['avg_citations_met'] else '❌'} ≥1.0")
    print()
    
    print(f"🔗 Citations:")
    print(f"   Domains: {citations['unique_domains']} unique")
    if citations['domain_list']:
        print(f"   Top domains: {', '.join(citations['domain_list'][:5])}")
    if citations['recency']:
        rec = citations['recency']
        print(f"   Recency: {rec['newest_days']} days (newest) to {rec['oldest_days']} days (oldest)")
    print()
    
    if fact_guard:
        print(f"✅ Fact-Guard:")
        print(f"   Claims: {fact_guard['total_claims']} total")
        print(f"   Kept: {fact_guard['kept']}, Removed: {fact_guard['removed']}")
        print(f"   Rewritten: {fact_guard['rewritten']}, Flagged: {fact_guard['flagged']}")
        print(f"   Clean: {'✅' if gates['fact_guard_clean'] else '❌'} (no removals)")
        print()
    
    print(f"🎯 Acceptance Gates:")
    print(f"   Citation Coverage: {'✅' if gates['citation_minimum_met'] else '❌'}")
    print(f"   Avg Citations: {'✅' if gates['avg_citations_met'] else '❌'}")
    print(f"   Fact-Guard Clean: {'✅' if gates['fact_guard_clean'] else '❌'}")
    
    # Overall status
    all_gates_passed = all(gates.values())
    status = "✅ PASSED" if all_gates_passed else "❌ FAILED"
    print(f"\n🏁 Overall Status: {status}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate research coverage and citation report")
    parser.add_argument("--slug", required=True, help="Topic slug for research report")
    parser.add_argument("--output", help="Output file path for JSON report")
    parser.add_argument("--compact", action="store_true", help="Print compact summary only")
    
    args = parser.parse_args()
    
    try:
        # Generate report
        report = generate_research_report(args.slug)
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            log.info(f"Report saved to: {output_path}")
        
        # Print output
        if args.compact:
            print_compact_summary(report)
        else:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        
        # Log completion
        summary = report['summary']
        log_state("research_report", "OK", 
                 f"slug={args.slug}, coverage={summary['coverage_percentage']}%, "
                 f"citations={summary['total_citations']}")
        
    except Exception as e:
        log.error(f"Research report generation failed: {e}")
        log_state("research_report", "ERROR", f"slug={args.slug}, error={str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    with single_lock():
        main()
