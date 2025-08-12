#!/usr/bin/env python3
"""
Research Collection Component

Fetches content from reputable sources, chunks it into manageable pieces,
and stores it in a SQLite database for later grounding.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import requests
import hashlib

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config, log_state, single_lock
from bin.model_runner import model_session

log = get_logger("research_collect")

class ResearchCollector:
    """Collects and processes research content from web sources."""
    
    def __init__(self, models_config: Optional[Dict] = None):
        """Initialize research collector."""
        self.config = load_config()
        self.models_config = models_config or self._load_models_config()
        self.research_config = self.models_config.get('research', {})
        
        # Database setup
        self.db_path = Path(BASE) / self.research_config.get('database', 'data/research.db')
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
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
    
    def _init_database(self):
        """Initialize SQLite database for research data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    domain TEXT,
                    content_hash TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY,
                    source_id INTEGER,
                    chunk_text TEXT NOT NULL,
                    chunk_hash TEXT UNIQUE NOT NULL,
                    token_count INTEGER,
                    embedding BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_id) REFERENCES sources (id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(chunk_hash)
            """)
            
            conn.commit()
    
    def collect_from_brief(self, brief: Dict) -> List[Dict]:
        """
        Collect research content based on brief configuration.
        
        Args:
            brief: Brief configuration with keywords and preferred sources
            
        Returns:
            List of collected source information
        """
        keywords = brief.get('keywords_include', [])
        preferred_sources = brief.get('sources_preferred', [])
        
        if not keywords:
            log.warning("No keywords found in brief, using default research")
            keywords = ["content creation", "video production"]
        
        log.info(f"Collecting research for keywords: {keywords}")
        
        # Collect from preferred sources first
        sources = []
        for source in preferred_sources:
            try:
                source_data = self._collect_from_source(source, keywords)
                if source_data:
                    sources.append(source_data)
            except Exception as e:
                log.error(f"Failed to collect from {source}: {e}")
        
        # Collect from general search if we need more sources
        max_sources = self.research_config.get('max_sources', 8)
        if len(sources) < max_sources:
            additional_sources = self._collect_from_search(keywords, max_sources - len(sources))
            sources.extend(additional_sources)
        
        return sources
    
    def _collect_from_source(self, source: str, keywords: List[str]) -> Optional[Dict]:
        """Collect content from a specific source."""
        try:
            if source.startswith('http'):
                return self._fetch_web_content(source, keywords)
            else:
                # Handle source types (e.g., "Google Search Central")
                return self._fetch_from_source_type(source, keywords)
        except Exception as e:
            log.error(f"Failed to collect from source {source}: {e}")
            return None
    
    def _fetch_web_content(self, url: str, keywords: List[str]) -> Optional[Dict]:
        """Fetch and process web content."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ResearchBot/1.0)'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Extract text content (simplified - could use trafilatura for better extraction)
            content = self._extract_text_content(response.text)
            
            if not content or len(content) < 100:
                return None
            
            # Check if content is relevant to keywords
            if not self._is_relevant_content(content, keywords):
                return None
            
            # Store in database
            source_id = self._store_source(url, content)
            if source_id:
                self._chunk_and_store_content(source_id, content)
                
                return {
                    'url': url,
                    'title': self._extract_title(response.text),
                    'domain': urlparse(url).netloc,
                    'source_id': source_id,
                    'content_length': len(content)
                }
            
        except Exception as e:
            log.error(f"Failed to fetch {url}: {e}")
        
        return None
    
    def _extract_text_content(self, html: str) -> str:
        """Extract text content from HTML."""
        # Simple text extraction - could be enhanced with trafilatura
        # Remove script and style tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract text from remaining HTML
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _extract_title(self, html: str) -> str:
        """Extract title from HTML."""
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        return "Untitled"
    
    def _is_relevant_content(self, content: str, keywords: List[str]) -> bool:
        """Check if content is relevant to keywords."""
        content_lower = content.lower()
        keyword_matches = sum(1 for keyword in keywords if keyword.lower() in content_lower)
        return keyword_matches >= len(keywords) * 0.3  # At least 30% of keywords present
    
    def _store_source(self, url: str, content: str) -> Optional[int]:
        """Store source information in database."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT OR REPLACE INTO sources (url, content_hash, metadata)
                    VALUES (?, ?, ?)
                """, (url, content_hash, json.dumps({'collected_at': time.time()})))
                
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            log.error(f"Failed to store source: {e}")
            return None
    
    def _chunk_and_store_content(self, source_id: int, content: str):
        """Chunk content and store in database."""
        chunk_size = self.research_config.get('chunk_size_tokens', 1200)
        
        # Simple chunking by sentences (could be enhanced with proper tokenization)
        sentences = re.split(r'[.!?]+', content)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_chunk) + len(sentence) > chunk_size * 4:  # Rough character estimate
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Store chunks
        for chunk in chunks:
            chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()
            
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR IGNORE INTO chunks (source_id, chunk_text, chunk_hash, token_count)
                        VALUES (?, ?, ?, ?)
                    """, (source_id, chunk, chunk_hash, len(chunk.split())))
                    
                    conn.commit()
                    
            except Exception as e:
                log.error(f"Failed to store chunk: {e}")
    
    def _collect_from_search(self, keywords: List[str], max_sources: int) -> List[Dict]:
        """Collect from general search (placeholder for now)."""
        # This could integrate with search APIs or use predefined reputable sources
        log.info(f"Collecting {max_sources} additional sources from search")
        return []
    
    def _fetch_from_source_type(self, source_type: str, keywords: List[str]) -> Optional[Dict]:
        """Fetch from source type (e.g., documentation sites)."""
        # Placeholder for source type handling
        log.info(f"Fetching from source type: {source_type}")
        return None
    
    def plan_research(self, topic: str) -> Dict:
        """Generate research plan using the research model."""
        try:
            model_name = self.research_config.get('name', 'mistral:7b-instruct')
            
            with model_session(model_name) as session:
                system_prompt = """You are a research planner. Generate a structured research plan for the given topic.
                
Return your response as JSON with the following structure:
{
  "queries": ["search query 1", "search query 2", ...],
  "sources": ["source type 1", "source type 2", ...],
  "focus_areas": ["area 1", "area 2", ...]
}"""
                
                response = session.chat(
                    system=system_prompt,
                    user=f"Create a research plan for: {topic}"
                )
                
                try:
                    import json
                    return json.loads(response)
                except:
                    log.warning("Failed to parse research plan as JSON")
                    return {"queries": [topic], "sources": ["web"], "focus_areas": [topic]}
                    
        except Exception as e:
            log.error(f"Research planning failed: {e}")
            return {"queries": [topic], "sources": ["web"], "focus_areas": [topic]}

def main(brief=None, models_config=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Collect research content for content creation")
    parser.add_argument("--brief", help="Path to brief file")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()
    
    if args.dry_run:
        log.info("DRY RUN MODE - No changes will be made")
    
    try:
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
        
        # Initialize collector
        collector = ResearchCollector()
        
        # Collect research
        sources = collector.collect_from_brief(brief)
        
        log.info(f"Collected {len(sources)} research sources")
        for source in sources:
            log.info(f"  - {source['domain']}: {source['title']}")
        
        return 0
        
    except Exception as e:
        log.error(f"Research collection failed: {e}")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect research content for content creation")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
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
