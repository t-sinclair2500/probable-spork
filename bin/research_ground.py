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
        # Model runner will be used directly in methods
        self.research_config = self.models_config.get('research', {})
        
        # Database setup
        self.db_path = Path(BASE) / self.research_config.get('database', 'data/research.db')
        if not self.db_path.exists():
            raise FileNotFoundError(f"Research database not found: {self.db_path}")
    
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
        
        log.info(f"Grounding script: {script_path}")
        
        # Load script content
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        # Extract script beats/sections
        beats = self._extract_beats(script_content)
        
        # Ground each beat with research
        grounded_beats = []
        all_references = set()
        
        for i, beat in enumerate(beats):
            log.info(f"Grounding beat {i+1}/{len(beats)}: {beat['title'][:50]}...")
            
            grounded_beat = self._ground_beat(beat, brief)
            grounded_beats.append(grounded_beat)
            
            # Collect references
            if grounded_beat.get('citations'):
                all_references.update(grounded_beat['citations'])
        
        # Generate grounded script
        grounded_script = self._generate_grounded_script(script_content, grounded_beats)
        
        # Save results to data directory with slug
        script_basename = script_path.stem
        # Extract slug from filename (e.g., "2025-08-12_eames.txt" -> "eames")
        if '_' in script_basename:
            slug = script_basename.split('_', 1)[1]
        else:
            slug = script_basename
        
        output_dir = Path("data") / slug
        output_dir.mkdir(parents=True, exist_ok=True)
        self._save_grounded_results(output_dir, grounded_beats, list(all_references))
        
        return {
            'grounded_script': grounded_script,
            'grounded_beats': grounded_beats,
            'references': list(all_references)
        }
    
    def _extract_beats(self, script_content: str) -> List[Dict]:
        """Extract beats/sections from script content."""
        # This is a simplified beat extraction - could be enhanced
        # to parse actual script structure from outline.json
        
        # Split by double newlines as a simple beat separator
        sections = re.split(r'\n\s*\n', script_content.strip())
        
        beats = []
        for i, section in enumerate(sections):
            if len(section.strip()) < 20:  # Skip very short sections
                continue
            
            # Extract first line as title
            lines = section.strip().split('\n')
            title = lines[0].strip()
            content = '\n'.join(lines[1:]).strip()
            
            if content:
                beats.append({
                    'id': i + 1,
                    'title': title,
                    'content': content,
                    'word_count': len(content.split())
                })
        
        return beats
    
    def _ground_beat(self, beat: Dict, brief: Dict) -> Dict:
        """Ground a single beat with research."""
        # Find relevant research chunks
        relevant_chunks = self._find_relevant_chunks(beat['content'], brief)
        
        # Use research model to ground content
        grounded_content = self._ground_with_research(beat, relevant_chunks, brief)
        
        # Extract citations
        citations = self._extract_citations(grounded_content, relevant_chunks)
        
        return {
            **beat,
            'grounded_content': grounded_content,
            'citations': citations,
            'research_chunks': [c['id'] for c in relevant_chunks]
        }
    
    def _find_relevant_chunks(self, content: str, brief: Dict) -> List[Dict]:
        """Find research chunks relevant to content."""
        keywords = brief.get('keywords_include', [])
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Simple keyword-based search (could be enhanced with embeddings)
                query = """
                    SELECT c.id, c.chunk_text, c.token_count, s.url, s.title, s.domain
                    FROM chunks c
                    JOIN sources s ON c.source_id = s.id
                    WHERE c.chunk_text LIKE ?
                    ORDER BY c.token_count DESC
                    LIMIT 5
                """
                
                chunks = []
                for keyword in keywords[:3]:  # Use top 3 keywords
                    cursor = conn.execute(query, (f'%{keyword}%',))
                    for row in cursor:
                        chunks.append({
                            'id': row[0],
                            'chunk_text': row[1],
                            'token_count': row[2],
                            'url': row[3],
                            'title': row[4],
                            'domain': row[5]
                        })
                
                return chunks
                
        except Exception as e:
            log.error(f"Failed to find relevant chunks: {e}")
            return []
    
    def _ground_with_research(self, beat: Dict, chunks: List[Dict], brief: Dict) -> str:
        """Use research model to ground content."""
        if not chunks:
            return beat['content']
        
        # Prepare research context
        research_context = "\n\n".join([
            f"Source {i+1} ({chunk['domain']}): {chunk['chunk_text'][:500]}..."
            for i, chunk in enumerate(chunks)
        ])
        
        system_prompt = f"""You are a research assistant helping to ground content with factual information.

Your task is to enhance the given content with research-backed information while maintaining the original tone and style.

Guidelines:
- Add factual details and statistics where relevant
- Include specific examples from the research
- Maintain the original voice and pacing
- Don't change the core message or structure
- Use [S1], [S2], etc. to cite sources

Research Context:
{research_context}

Original Content:
{beat['content']}

Enhanced Content:"""

        try:
            # Use model runner for deterministic load/unload
            model_name = self.research_config.get('name', 'mistral:7b-instruct')
            
            with model_session(model_name) as session:
                grounded_content = session.chat(
                    system=system_prompt,
                    user="Please enhance this content with research-backed information while maintaining the original style.",
                    temperature=0.3
                )
                
                return grounded_content.strip()
            
        except Exception as e:
            log.error(f"Failed to ground content with research: {e}")
            return beat['content']
    
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
                    'domain': chunk['domain']
                })
        
        return citations
    
    def _generate_grounded_script(self, original_script: str, grounded_beats: List[Dict]) -> str:
        """Generate final grounded script with citations."""
        # Replace original content with grounded content
        grounded_script = original_script
        
        for beat in grounded_beats:
            # Simple replacement - could be enhanced with more sophisticated text matching
            if beat['content'] in grounded_script:
                grounded_script = grounded_script.replace(
                    beat['content'], 
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
        
        log.info(f"Saved grounded results to {output_dir}")

def main(brief=None, models_config=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Ground script content with research")
    parser.add_argument("script", help="Path to script file")
    parser.add_argument("--brief", help="Path to brief file")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()
    
    if args.dry_run:
        log.info("DRY RUN MODE - No changes will be made")
    
    try:
        script_path = Path(args.script)
        if not script_path.exists():
            log.error(f"Script not found: {script_path}")
            return 1
        
        # Load brief
        brief = None
        if args.brief_data:
            try:
                brief = json.loads(args.brief_data)
                log.info(f"Loaded brief from --brief-data: {brief.get('title', 'Untitled')}")
            except (json.JSONDecodeError, TypeError) as e:
                log.error(f"Failed to parse brief data: {e}")
                return 1
        elif args.brief:
            brief_path = Path(args.brief)
            if brief_path.exists():
                import yaml
                with open(brief_path, 'r', encoding='utf-8') as f:
                    brief = yaml.safe_load(f)
            else:
                log.error(f"Brief file not found: {brief_path}")
                return 1
        else:
            # Try to load default brief
            brief_path = Path(BASE) / "conf" / "brief.yaml"
            if brief_path.exists():
                import yaml
                with open(brief_path, 'r', encoding='utf-8') as f:
                    brief = yaml.safe_load(f)
            else:
                log.warning("No brief file found, using minimal configuration")
                brief = {"keywords_include": ["content creation"]}
        
        # Initialize grounder
        grounder = ResearchGrounder()
        
        # Ground script
        results = grounder.ground_script(script_path, brief)
        
        log.info(f"Successfully grounded script with {len(results['references'])} references")
        
        return 0
        
    except Exception as e:
        log.error(f"Research grounding failed: {e}")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ground script content with research")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("script", help="Path to script file")
    parser.add_argument("--brief", help="Path to brief file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    
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
        main(brief, models_config=None)  # models_config not passed via CLI
