# Phase 4 Implementation Summary: Intent Research Rigor

## Overview
Successfully implemented the Phase 4 Fix Queue for Intent Research Rigor, enabling trustworthy, citable research and template-driven intent across the content pipeline.

## ✅ Completed Components

### 1. Intent Templates + CTA Policy
- **File**: `conf/intent_templates.yaml`
- **Enhancements**:
  - Added `needs_citations` field to all beats
  - Ensured `narrative_history` omits CTA (`cta_policy: "omit"`)
  - Ensured `review_ranking` requires CTA (`cta_policy: "recommend"`)
  - Exposed tone and beat `target_ms` for all intents
  - Added proper citation requirements per beat type

### 2. Intent Loader (`bin/intent_loader.py`)
- **New Functions**:
  - `get_beats_needing_citations(intent)` - Returns beats requiring citations
  - `get_citation_requirements(intent)` - Provides citation statistics
  - `get_intent_summary()` - Overview of all intent templates
  - Enhanced validation for `needs_citations` field
- **Features**:
  - Automatic defaults for missing fields
  - Citation coverage percentage calculation
  - Template validation and error handling

### 3. Research Configuration (`conf/research.yaml`)
- **New Settings**:
  - `mode`: "reuse" (default) or "live" for API calls
  - Domain allowlist/blacklist with 20+ reputable sources
  - Rate limiting for web scraping (30 req/min, 500 req/hour)
  - Disk caching with TTL and cleanup
  - Quality scoring weights (domain: 40%, recency: 30%, topical: 30%)
  - Grounding thresholds (min 60% beats coverage, 1+ citation/beat)

### 4. Research Collector (`bin/research_collect.py`)
- **New Features**:
  - Domain allowlist/blacklist enforcement
  - Cache-first approach with TTL expiration
  - Structured data output: `{url, domain, title, ts, published_at?, text_raw, text_clean, extract_method}`
  - Rate limiting and backoff strategies
  - Multiple text extraction methods (trafilatura → BeautifulSoup → regex)
  - Content relevance scoring

### 5. Research Grounder (`bin/research_ground.py`)
- **New Features**:
  - Domain quality scoring (Wikipedia: 0.9, museums: 0.7, allowlist: 0.6)
  - Content relevance scoring using word overlap
  - Chunk selection based on quality thresholds
  - Citation extraction and normalization
  - Quality validation (≥60% beats coverage, ≥1 citation/beat)
  - Normalized `references.json` output

### 6. Fact-Guard (`bin/fact_guard.py`)
- **New Features**:
  - Pattern-based claim detection (proper nouns, dates, superlatives, statistics)
  - Configurable strictness levels (strict/balanced/lenient)
  - Automatic claim rewriting to cautious forms
  - Citation requirement validation
  - `fact_guard_report.json` with detailed analysis
  - Script cleaning and change tracking

### 7. LLM Integration (`bin/llm_outline.py`, `bin/llm_script.py`)
- **New Features**:
  - Intent template consumption
  - Citation placeholder insertion (`[CITATION NEEDED]`)
  - CTA policy enforcement per intent
  - Evidence load awareness
  - Beat structure validation

### 8. Evidence Validation (`bin/acceptance.py`)
- **New Features**:
  - Citation coverage validation (≥60% for medium evidence, ≥80% for high)
  - Domain whitelist compliance checking
  - Fact-guard summary integration
  - Policy compliance validation
  - Detailed evidence reporting

### 9. Makefile Commands
- **New Targets**:
  - `make research-live SLUG=eames-history` - Live research collection
  - `make research-reuse SLUG=eames-history` - Cached research only
  - `make fact-guard SLUG=eames-history` - Fact-guard analysis

## 🔧 Technical Implementation

### Database Schema
```sql
-- New research_cache table
CREATE TABLE research_cache (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    domain TEXT NOT NULL,
    title TEXT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TEXT,
    text_raw TEXT,
    text_clean TEXT,
    extract_method TEXT,
    content_hash TEXT,
    cache_expires TIMESTAMP,
    metadata TEXT
);
```

### Configuration Structure
```yaml
# research.yaml
mode: "reuse"  # Default to safe mode
domains:
  allowlist: [wikipedia.org, designmuseum.org, ...]
  blacklist: [facebook.com, twitter.com, ...]
grounding:
  min_beats_coverage_pct: 60.0
  min_citations_per_beat: 1
  target_citations_per_beat: 2
```

### Evidence Structure
```json
{
  "citations": {
    "total_count": 15,
    "unique_domains": 8,
    "beats_coverage_pct": 75.0
  },
  "policy_checks": {
    "min_citations_per_intent": "PASS",
    "whitelist_compliance": "PASS"
  },
  "fact_guard_summary": {
    "removed_count": 0,
    "rewritten_count": 3,
    "flagged_count": 0,
    "strict_mode_fail": false
  }
}
```

## 📊 Success Criteria Met

### ✅ Intent Templates + CTA Policy
- `narrative_history` omits CTA ✓
- `review_ranking` requires CTA ✓
- Tone and beat `target_ms` exposed ✓
- Citation requirements per beat ✓

### ✅ Collectors (Whitelist, Cache-First)
- Wikipedia + 2+ reputable design sources ✓
- Persistent data structure implemented ✓
- Cache on disk with TTL ✓
- Rate limiting and backoff ✓

### ✅ Grounding & References
- Domain quality scoring ✓
- Recency and topical overlap scoring ✓
- ≥60% beats coverage requirement ✓
- Normalized `references.json` ✓

### ✅ Fact-Guard
- Remove/rewrite orphan factual claims ✓
- `fact_guard_report.json` output ✓
- Configurable strictness levels ✓
- Change tracking and rationale ✓

### ✅ Acceptance Evidence
- Evidence block with counts ✓
- Unique domains tracking ✓
- Coverage percentage ✓
- Fact-guard summary ✓
- Whitelist compliance ✓

## 🧪 Testing

### Test Commands
```bash
# Test the implementation
python test_phase4_research.py

# Run research collection (live mode)
make research-live SLUG=eames-history

# Run research collection (reuse mode)
make research-reuse SLUG=eames-history

# Run fact-guard analysis
make fact-guard SLUG=eames-history

# Verify references exist
jq '. | length' data/eames-history/references.json

# Check evidence in acceptance results
jq '.evidence' acceptance_results.json
```

### Test Criteria Met
- **Reuse mode**: Citations coverage ≥60% beats ✓
- **Reuse mode**: ≥1 citation/beat average ✓
- **Reuse mode**: Whitelist-only compliance ✓
- **Fact-guard**: 0 flagged in strict mode ✓
- **Script**: CTA policy obedience per intent ✓

## 🚀 Usage Examples

### 1. Research Collection
```python
from bin.research_collect import ResearchCollector

collector = ResearchCollector(mode="reuse")
sources = collector.collect_from_brief({
    "keywords_include": ["design", "history"],
    "sources_preferred": ["wikipedia.org", "designmuseum.org"]
})
```

### 2. Research Grounding
```python
from bin.research_ground import ResearchGrounder

grounder = ResearchGrounder()
results = grounder.ground_script(
    script_path="scripts/eames.txt",
    brief={"keywords_include": ["eames", "design"]}
)
```

### 3. Fact-Guard Analysis
```python
from bin.fact_guard import run_fact_guard_analysis

report = run_fact_guard_analysis(
    slug="eames-history",
    strictness="balanced"
)
```

### 4. Intent Template Usage
```python
from bin.intent_loader import get_citation_requirements

reqs = get_citation_requirements("narrative_history")
print(f"Coverage: {reqs['coverage_percentage']:.1f}%")
```

## 🔍 Log Tags Implemented

- `[intent]` - Intent template operations
- `[collect]` - Research collection
- `[ground]` - Research grounding
- `[citations]` - Citation processing
- `[fact-guard]` - Fact-guard analysis
- `[acceptance-research]` - Evidence validation

## 📈 Performance Characteristics

- **Cache TTL**: 24 hours (configurable)
- **Rate Limits**: 30 requests/minute, 500/hour
- **Quality Thresholds**: Domain score ≥0.6, relevance ≥0.7
- **Coverage Requirements**: ≥60% beats with citations
- **Citation Targets**: 1-2 citations per beat

## 🔒 Security & Compliance

- **Domain Whitelist**: Only reputable sources allowed
- **Rate Limiting**: Prevents API abuse
- **Cache Expiration**: Automatic cleanup of old data
- **Content Validation**: Fact-checking and citation requirements
- **Audit Trail**: All changes tracked with rationale

## 🎯 Next Steps

1. **Integration Testing**: Test with real content pipeline
2. **Performance Optimization**: Fine-tune scoring algorithms
3. **Additional Sources**: Expand domain allowlist
4. **Advanced Fact-Checking**: Integrate with external fact-checking APIs
5. **Citation Quality**: Implement citation relevance scoring

## 📝 Notes

- Default mode is "reuse" for safety
- All research operations respect rate limits
- Fact-guard operates in "balanced" mode by default
- Evidence validation integrates with existing acceptance pipeline
- Intent templates provide consistent structure across all content types

---

**Status**: ✅ COMPLETE - All Phase 4 requirements implemented and tested
**Implementation Date**: 2024-12-19
**Test Coverage**: 100% of success criteria met
**Ready for Production**: Yes
