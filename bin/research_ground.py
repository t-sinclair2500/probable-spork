#!/usr/bin/env python3
"""
Research Grounding Component

Uses collected research to ground script content with citations and references.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib
from datetime import datetime

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, log_state, single_lock
from bin.model_runner import model_session

log = get_logger("research_ground")

class ResearchGrounder:
    """Grounds script content with research citations and references."""
    
    def __init__(self, models_config: Optional[Dict] = None):
        """Initialize research grounder."""
        self.config = load_config()
        self.models_config = models_config or self._load_models_config()
        
        # Load research config from models.yaml since it's not in global.yaml
        self.research_config = self._load_research_config()
        
        # Database setup
        self.db_path = Path(BASE) / self.research_config.get('database', 'data/research.db')
        if not self.db_path.exists():
            raise FileNotFoundError(f"Research database not found: {self.db_path}")
        
        # Grounding settings
        self.grounding_config = self.research_config.get('grounding', {})
        self.min_citations_per_beat = self.grounding_config.get('min_citations_per_beat', 1)
        self.target_citations_per_beat = self.grounding_config.get('target_citations_per_beat', 2)
        self.min_beats_coverage_pct = self.grounding_config.get('min_beats_coverage_pct', 60.0)
        self.citation_format = self.grounding_config.get('citation_format', '[S{num}]')
        
        # Quality thresholds
        self.min_domain_quality_score = self.grounding_config.get('min_domain_quality_score', 0.6)
        self.min_content_relevance_score = self.grounding_config.get('min_content_relevance_score', 0.7)
    
    def _load_models_config(self) -> Dict:
        """Load models configuration."""
        try:
            import yaml
            models_path = Path(BASE) / "conf" / "models.yaml"
            with open(models_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            log.warning(f"Failed to load models.yaml: {e}, using defaults")
            return {}
    
    def _load_research_config(self) -> Dict:
        """Load research configuration from models.yaml."""
        try:
            import yaml
            models_path = Path(BASE) / "conf" / "models.yaml"
            with open(models_path, 'r', encoding='utf-8') as f:
                models_data = yaml.safe_load(f)
                return models_data.get('research', {})
        except Exception as e:
            log.warning(f"Failed to load research config: {e}, using defaults")
            return {}
    
    def ground_script(self, script_path: Path, brief: Dict) -> Dict:
        """
        Ground a script with research citations.
        
        Args:
            script_path: Path to script file
            brief: Brief configuration
            
        Returns:
            Grounded script with citations and references
        """
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        
        log.info(f"[ground] Grounding script: {script_path}")
        
        # Load script content
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        # Extract script beats/sections
        beats = self._extract_beats(script_content)
        
        # Ground each beat with research
        grounded_beats = []
        all_references = set()
        
        for i, beat in enumerate(beats):
            log.info(f"[ground] Grounding beat {i+1}/{len(beats)}: {beat['title'][:50]}...")
            
            grounded_beat = self._ground_beat(beat, brief)
            grounded_beats.append(grounded_beat)
            
            # Collect references
            if grounded_beat.get('citations'):
                all_references.update(grounded_beat['citations'])
        
        # Generate grounded script
        grounded_script = self._generate_grounded_script(script_content, grounded_beats)
        
        # Save results to data directory with slug
        script_basename = script_path.stem
        # Extract slug from filename (e.g., "2025-08-12_topic.txt" -> "topic")
        if '_' in script_basename:
            slug = script_basename.split('_', 1)[1]
        else:
            slug = script_basename
        
        output_dir = Path(BASE) / "data" / slug
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Normalize references into standard format
        normalized_references = self._normalize_references(list(all_references))
        
        # Save grounded results
        self._save_grounded_results(output_dir, grounded_beats, normalized_references)
        
        # Validate grounding quality
        quality_report = self._validate_grounding_quality(grounded_beats, normalized_references)
        
        log.info(f"[ground] Grounding completed for {slug}")
        log.info(f"[ground] Quality report: {quality_report}")
        
        return {
            'grounded_beats': grounded_beats,
            'references': normalized_references,
            'quality_report': quality_report
        }
    
    def _extract_beats(self, script_content: str) -> List[Dict]:
        """Extract beats from script content."""
        # Simple beat extraction - split by double newlines
        sections = script_content.split('\n\n')
        beats = []
        
        for i, section in enumerate(sections):
            section = section.strip()
            if not section or len(section) < 20:
                continue
            
            # Extract title from first line
            lines = section.split('\n')
            title = lines[0].strip()
            content = '\n'.join(lines[1:]).strip()
            
            if content:
                beats.append({
                    'id': f'beat_{i+1}',
                    'title': title,
                    'content': content,
                    'original_content': content
                })
        
        return beats
    
    def _ground_beat(self, beat: Dict, brief: Dict) -> Dict:
        """Ground a single beat with research."""
        # Get relevant research chunks
        chunks = self._get_relevant_chunks(beat['content'], brief)
        
        if not chunks:
            log.warning(f"[ground] No relevant research found for beat: {beat['title']}")
            return {
                **beat,
                'grounded_content': beat['content'],
                'citations': [],
                'research_score': 0.0
            }
        
        # Score chunks by quality and relevance
        scored_chunks = self._score_chunks(chunks, beat['content'])
        
        # Select best chunks for grounding
        selected_chunks = self._select_best_chunks(scored_chunks, self.target_citations_per_beat)
        
        # Ground content with selected research
        grounded_content = self._ground_content_with_research(beat['content'], selected_chunks)
        
        # Extract citations
        citations = self._extract_citations(grounded_content, selected_chunks)
        
        return {
            **beat,
            'grounded_content': grounded_content,
            'citations': citations,
            'research_score': sum(chunk.get('score', 0) for chunk in selected_chunks) / len(selected_chunks) if selected_chunks else 0.0,
            'selected_chunks': selected_chunks
        }
    
    def _get_relevant_chunks(self, content: str, brief: Dict) -> List[Dict]:
        """Get relevant research chunks from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get chunks with their source information
                cursor = conn.execute("""
                    SELECT c.chunk_text, c.chunk_hash, c.token_count, s.url, s.title, s.domain
                    FROM chunks c
                    JOIN sources s ON c.source_id = s.id
                    WHERE c.chunk_text IS NOT NULL AND length(c.chunk_text) > 50
                """)
                
                chunks = []
                for row in cursor.fetchall():
                    chunk_text, chunk_hash, token_count, url, title, domain = row
                    
                    # Calculate relevance score
                    relevance_score = self._calculate_relevance_score(content, chunk_text)
                    
                    if relevance_score >= self.min_content_relevance_score:
                        chunks.append({
                            'chunk_text': chunk_text,
                            'chunk_hash': chunk_hash,
                            'token_count': token_count,
                            'url': url,
                            'title': title,
                            'domain': domain,
                            'relevance_score': relevance_score
                        })
                
                return chunks
                
        except Exception as e:
            log.error(f"Failed to get relevant chunks: {e}")
            return []
    
    def _calculate_relevance_score(self, content: str, chunk_text: str) -> float:
        """Calculate relevance score between content and chunk."""
        # Simple word overlap scoring
        content_words = set(re.findall(r'\w+', content.lower()))
        chunk_words = set(re.findall(r'\w+', chunk_text.lower()))
        
        if not content_words or not chunk_words:
            return 0.0
        
        intersection = content_words.intersection(chunk_words)
        union = content_words.union(chunk_words)
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _score_chunks(self, chunks: List[Dict], content: str) -> List[Dict]:
        """Score chunks by quality and relevance."""
        scoring_weights = self.research_config.get('collection', {}).get('scoring_weights', {})
        
        for chunk in chunks:
            # Domain quality score
            domain_score = self._calculate_domain_quality_score(chunk['domain'])
            
            # Content relevance score (already calculated)
            relevance_score = chunk['relevance_score']
            
            # Recency score (placeholder - could be enhanced with actual timestamps)
            recency_score = 0.7  # Default score
            
            # Calculate weighted score
            weighted_score = (
                domain_score * scoring_weights.get('domain_quality', 0.4) +
                relevance_score * scoring_weights.get('topical_overlap', 0.3) +
                recency_score * scoring_weights.get('recency', 0.3)
            )
            
            chunk['score'] = weighted_score
            chunk['domain_score'] = domain_score
            chunk['recency_score'] = recency_score
        
        # Sort by score (descending)
        chunks.sort(key=lambda x: x['score'], reverse=True)
        return chunks
    
    def _calculate_domain_quality_score(self, domain: str) -> float:
        """Calculate domain quality score based on reputation."""
        # Domain reputation scoring
        high_reputation_domains = {
            'wikipedia.org', 'en.wikipedia.org', 'britannica.com', 'encyclopedia.com',
            'academic.oup.com', 'jstor.org', 'arxiv.org', 'ieee.org', 'acm.org'
        }
        
        medium_reputation_domains = {
            'designmuseum.org', 'moma.org', 'tate.org.uk', 'vam.ac.uk',
            'cooperhewitt.org', 'metmuseum.org', 'nga.gov', 'si.edu'
        }
        
        if domain in high_reputation_domains:
            return 0.9
        elif domain in medium_reputation_domains:
            return 0.7
        else:
            # Check if domain is in allowlist
            allowlist = self.research_config.get('domains', {}).get('allowlist', [])
            if domain in allowlist:
                return 0.6
            else:
                return 0.4
    
    def _select_best_chunks(self, scored_chunks: List[Dict], target_count: int) -> List[Dict]:
        """Select the best chunks for grounding."""
        # Filter by minimum quality threshold
        qualified_chunks = [chunk for chunk in scored_chunks if chunk['score'] >= self.min_domain_quality_score]
        
        # Select top chunks up to target count
        selected = qualified_chunks[:target_count]
        
        log.info(f"[ground] Selected {len(selected)} chunks from {len(scored_chunks)} candidates")
        return selected
    
    def _ground_content_with_research(self, content: str, chunks: List[Dict]) -> str:
        """Ground content with research information."""
        if not chunks:
            return content
        
        # Create research context
        research_context = "\n\n".join([
            f"Source {i+1} ({chunk['domain']}): {chunk['chunk_text'][:500]}..."
            for i, chunk in enumerate(chunks)
        ])
        
        # Load prompt template
        prompt_path = os.path.join(BASE, "prompts", "research_grounding.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
        
        # Format prompt with variables
        system_prompt = template.format(
            brief_context="",  # Research grounding doesn't use brief context
            topic=topic,
            research_goals="Enhance content with factual information",
            evidence_level="high"
        )
        
        # Add research context and content
        system_prompt += f"""

Research Context:
{research_context}

Original Content:
{content}

Enhanced Content:"""

        try:
            # Use model runner for deterministic load/unload
            model_name = self.research_config.get('models', {}).get('research', 'llama3.2:3b')
            
            # Load user prompt template
            user_prompt_path = os.path.join(BASE, "prompts", "user_research_ground.txt")
            with open(user_prompt_path, "r", encoding="utf-8") as f:
                user_prompt_template = f.read()
            
            user_prompt = user_prompt_template.strip()
            
            with model_session(model_name) as session:
                grounded_content = session.chat(
                    system=system_prompt,
                    user=user_prompt,
                    temperature=0.3
                )
                
                return grounded_content.strip()
            
        except Exception as e:
            log.error(f"Failed to ground content with research: {e}")
            return content
    
    def _extract_citations(self, content: str, chunks: List[Dict]) -> List[Dict]:
        """Extract citations from grounded content."""
        citations = []
        
        # Find citation markers like [S1], [S2], etc.
        citation_pattern = r'\[S(\d+)\]'
        matches = re.findall(citation_pattern, content)
        
        for match in matches:
            source_num = int(match)
            if source_num <= len(chunks):
                chunk = chunks[source_num - 1]
                citations.append({
                    'source_num': source_num,
                    'url': chunk['url'],
                    'title': chunk['title'],
                    'domain': chunk['domain'],
                    'chunk_hash': chunk['chunk_hash'],
                    'score': chunk['score']
                })
        
        return citations
    
    def _normalize_references(self, references: List[Dict]) -> List[Dict]:
        """Normalize references into standard format."""
        normalized = []
        
        for ref in references:
            if isinstance(ref, dict):
                normalized_ref = {
                    'url': ref.get('url', ''),
                    'domain': ref.get('domain', ''),
                    'title': ref.get('title', ''),
                    'ts': ref.get('ts', datetime.utcnow().isoformat()),
                    'published_at': ref.get('published_at', ''),
                    'text_raw': ref.get('text_raw', ''),
                    'text_clean': ref.get('text_clean', ''),
                    'extract_method': ref.get('extract_method', 'unknown'),
                    'metadata': ref.get('metadata', {})
                }
                normalized.append(normalized_ref)
        
        return normalized
    
    def _validate_grounding_quality(self, grounded_beats: List[Dict], references: List[Dict]) -> Dict:
        """Validate grounding quality against requirements."""
        total_beats = len(grounded_beats)
        beats_with_citations = sum(1 for beat in grounded_beats if beat.get('citations'))
        
        coverage_pct = (beats_with_citations / total_beats * 100) if total_beats > 0 else 0
        
        # Check minimum coverage requirement
        meets_coverage = coverage_pct >= self.min_beats_coverage_pct
        
        # Check minimum citations per beat
        avg_citations = sum(len(beat.get('citations', [])) for beat in grounded_beats) / total_beats if total_beats > 0 else 0
        meets_citation_min = avg_citations >= self.min_citations_per_beat
        
        quality_report = {
            'total_beats': total_beats,
            'beats_with_citations': beats_with_citations,
            'coverage_percentage': coverage_pct,
            'average_citations_per_beat': avg_citations,
            'meets_coverage_requirement': meets_coverage,
            'meets_citation_minimum': meets_citation_min,
            'overall_quality': 'PASS' if (meets_coverage and meets_citation_min) else 'FAIL',
            'quality_issues': []
        }
        
        if not meets_coverage:
            quality_report['quality_issues'].append(
                f"Coverage {coverage_pct:.1f}% below minimum {self.min_beats_coverage_pct}%"
            )
        
        if not meets_citation_min:
            quality_report['quality_issues'].append(
                f"Average citations {avg_citations:.1f} below minimum {self.min_citations_per_beat}"
            )
        
        return quality_report
    
    def _generate_grounded_script(self, original_script: str, grounded_beats: List[Dict]) -> str:
        """Generate final grounded script with citations."""
        # Replace original content with grounded content
        grounded_script = original_script
        
        for beat in grounded_beats:
            # Simple replacement - could be enhanced with more sophisticated text matching
            if beat['original_content'] in grounded_script:
                grounded_script = grounded_script.replace(
                    beat['original_content'], 
                    beat['grounded_content']
                )
        
        return grounded_script
    
    def _save_grounded_results(self, output_dir: Path, grounded_beats: List[Dict], references: List[Dict]):
        """Save grounded results to files."""
        # Save grounded beats
        beats_path = output_dir / "grounded_beats.json"
        with open(beats_path, 'w', encoding='utf-8') as f:
            json.dump(grounded_beats, f, indent=2, ensure_ascii=False)
        
        # Save references
        refs_path = output_dir / "references.json"
        with open(refs_path, 'w', encoding='utf-8') as f:
            json.dump(references, f, indent=2, ensure_ascii=False)
        
        log.info(f"[ground] Saved grounded results to {output_dir}")

def main(brief=None, models_config=None, script_path=None, slug=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Ground script content with research")
    parser.add_argument("script", help="Path to script file")
    parser.add_argument("--brief", help="Path to brief file")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("--mode", choices=['reuse', 'live'], default='reuse',
                       help='Mode: reuse (cache only) or live (with API calls)')
    parser.add_argument("--slug", required=True, help="Topic slug for research grounding")
    args = parser.parse_args()
    
    # Use command line args if provided, otherwise use function parameters
    script_path = args.script if hasattr(args, 'script') else script_path
    slug = args.slug if hasattr(args, 'slug') else slug
    
    if not script_path or not slug:
        log.error("Script path and slug are required")
        return
    
    # Load brief data
    if brief is None:
        if args.brief:
            with open(args.brief, 'r') as f:
                brief = json.load(f)
        elif args.brief_data:
            brief = json.loads(args.brief_data)
        else:
            brief = {"keywords_include": [slug]}
    
    log.info(f"[ground] Starting research grounding for script: {script_path}, slug: {slug}")
    
    # Initialize grounder
    grounder = ResearchGrounder(models_config)
    
    # Ground script
    results = grounder.ground_script(Path(script_path), brief)
    
    log.info(f"[ground] Research grounding completed")
    log.info(f"[ground] Quality report: {results['quality_report']}")
    
    return results

if __name__ == "__main__":
    main()
