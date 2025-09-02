#!/usr/bin/env python3
"""
Research Collection Component

Fetches content from reputable sources, chunks it into manageable pieces,
and stores it in a SQLite database for later grounding.
"""

import argparse
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests
from pathlib import Path

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, load_config
from bin.utils.config import get_research_policy, load_all_configs

log = get_logger("research_collect")


class RateLimiter:
    """Provider-aware rate limiter with jitter."""

    def __init__(self, limits: dict):
        self.limits = limits or {}
        self._last = {}

    def wait(self, provider: str):
        """Wait for the appropriate interval before making a request."""
        lim = self.limits.get(provider, {})
        base = int(lim.get("min_interval_ms", 0))
        jitter = int(lim.get("jitter_ms", 0))
        if base <= 0:
            return
        now = time.time()
        last = self._last.get(provider, 0)
        wait = (base + random.randint(0, jitter)) / 1000.0 - (now - last)
        if wait > 0:
            time.sleep(wait)
        self._last[provider] = time.time()


def _load_fixture(slug: str) -> List[Dict]:
    """Load fixture data for a given slug."""
    p = Path(BASE) / "data" / "fixtures" / f"{slug}.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                log.info(f"[collect] Loaded {len(data)} sources from fixture: {p}")
                return data
        except Exception as e:
            log.warning(f"Failed to load fixture {p}: {e}")
    return []


class ResearchCollector:
    """Collects and processes research content from web sources."""

    def __init__(self, models_config: Optional[Dict] = None, mode: str = "reuse"):
        """Initialize research collector."""
        # Global runtime config (pydantic model) if needed elsewhere
        self.config = load_config()
        self.models_config = models_config

        # Load research policy from unified config (conf/research.yaml only)
        bundle = load_all_configs()
        self.policy = get_research_policy(bundle)
        self.mode = mode or self.policy.mode

        # Store research config for later use
        self.research_config = (
            bundle.research
            if hasattr(bundle, "research")
            else bundle.get("research", {})
        )

        # Initialize rate limiter
        research_data = (
            bundle.get("research", {})
            if isinstance(bundle, dict)
            else bundle.research.dict()
        )
        provider_limits = research_data.get("providers", {}).get("rate_limits", {})
        self.rate_limiter = RateLimiter(provider_limits)

        # Database setup
        self.db_path = Path(BASE) / "data/research.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Load domain allowlist and blacklist from research config
        self.domain_allowlist = set(
            research_data.get("domains", {}).get("allowlist", [])
        )
        self.domain_blacklist = set(
            research_data.get("domains", {}).get("blacklist", [])
        )

        # Cache settings from research config
        cache_config = research_data.get("cache", {})
        self.cache_enabled = cache_config.get("disk_cache", {}).get("enabled", True)
        self.cache_base_path = Path(BASE) / cache_config.get("disk_cache", {}).get(
            "base_path", "data/research_cache"
        )
        self.cache_ttl_hours = cache_config.get("ttl_hours", 24)

        if self.cache_enabled:
            self.cache_base_path.mkdir(parents=True, exist_ok=True)

    def _init_database(self):
        """Initialize SQLite database for research data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    domain TEXT,
                    content_hash TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """
            )

            conn.execute(
                """
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
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_cache (
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
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(chunk_hash)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_domain ON research_cache(domain)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_expires ON research_cache(cache_expires)
            """
            )

            conn.commit()

    def _is_domain_allowed(self, domain: str) -> bool:
        """Check if a domain is allowed for research collection."""
        # Check blacklist first
        if domain in self.domain_blacklist:
            log.info(f"[collect] Domain {domain} is blacklisted")
            return False

        # If allowlist is empty, allow all non-blacklisted domains
        if not self.domain_allowlist:
            return True

        # Check allowlist
        is_allowed = domain in self.domain_allowlist
        if not is_allowed:
            log.info(f"[collect] Domain {domain} not in allowlist")
        return is_allowed

    def _get_cached_content(self, url: str) -> Optional[Dict]:
        """Get cached content if available and not expired."""
        if not self.cache_enabled:
            return None

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT url, domain, title, ts, published_at, text_raw, text_clean, extract_method, metadata
                    FROM research_cache 
                    WHERE url = ? AND cache_expires > ?
                """,
                    (url, datetime.utcnow()),
                )

                row = cursor.fetchone()
                if row:
                    return {
                        "url": row[0],
                        "domain": row[1],
                        "title": row[2],
                        "ts": row[3],
                        "published_at": row[4],
                        "text_raw": row[5],
                        "text_clean": row[6],
                        "extract_method": row[7],
                        "metadata": json.loads(row[8]) if row[8] else {},
                    }
        except Exception as e:
            log.warning(f"Failed to get cached content: {e}")

        return None

    def _cache_content(self, content_data: Dict):
        """Cache content with expiration."""
        if not self.cache_enabled:
            return

        try:
            expires = datetime.utcnow() + timedelta(hours=self.cache_ttl_hours)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO research_cache 
                    (url, domain, title, ts, published_at, text_raw, text_clean, extract_method, content_hash, cache_expires, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        content_data["url"],
                        content_data["domain"],
                        content_data.get("title", ""),
                        content_data.get("ts", datetime.utcnow().isoformat()),
                        content_data.get("published_at", ""),
                        content_data.get("text_raw", ""),
                        content_data.get("text_clean", ""),
                        content_data.get("extract_method", "unknown"),
                        content_data.get("content_hash", ""),
                        expires.isoformat(),
                        json.dumps(content_data.get("metadata", {})),
                    ),
                )
                conn.commit()

                log.info(f"[collect] Cached content for {content_data['domain']}")
        except Exception as e:
            log.warning(f"Failed to cache content: {e}")

    def collect_from_brief(self, brief: Dict) -> List[Dict]:
        """
        Collect research content based on brief configuration.

        Args:
            brief: Brief configuration with keywords and preferred sources

        Returns:
            List of collected source information
        """
        keywords = brief.get("keywords_include", [])
        preferred_sources = brief.get("sources_preferred", [])

        if not keywords:
            log.warning("No keywords found in brief, using default research")
            keywords = ["content creation", "video production"]

        log.info(f"[collect] Collecting research for keywords: {keywords}")

        # Try fixtures first in reuse mode
        if self.mode == "reuse":
            # Try to extract slug from brief
            slug = (
                brief.get("slug")
                or brief.get("topic")
                or keywords[0].lower().replace(" ", "-")
            )
            fixture_sources = _load_fixture(slug)
            if fixture_sources:
                log.info(
                    f"[collect] Using {len(fixture_sources)} sources from fixture for {slug}"
                )
                return fixture_sources

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
        collection_config = getattr(self.research_config, "collection", {})
        max_sources = collection_config.get("max_sources_per_topic", 15)
        if len(sources) < max_sources:
            additional_sources = self._collect_from_search(
                keywords, max_sources - len(sources)
            )
            sources.extend(additional_sources)

        return sources

    def _collect_from_source(self, source: str, keywords: List[str]) -> Optional[Dict]:
        """Collect content from a specific source."""
        try:
            if source.startswith("http"):
                return self._fetch_web_content(source, keywords)
            else:
                # Handle source types (e.g., "Google Search Central")
                return self._fetch_from_source_type(source, keywords)
        except Exception as e:
            log.error(f"Failed to collect from source {source}: {e}")
            return None

    def _fetch_web_content(self, url: str, keywords: List[str]) -> Optional[Dict]:
        """Fetch and process web content."""
        # Check cache first
        cached = self._get_cached_content(url)
        if cached:
            log.info(f"[collect] Using cached content for {url}")
            return cached

        # Check if we should fetch live content
        if self.mode == "reuse":
            log.info(f"[collect] Reuse mode: skipping live fetch for {url}")
            return None

        try:
            # Apply rate limiting for web scraping
            self.rate_limiter.wait("web_scraping")

            headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Extract text content
            content = self._extract_text_content(response.text)

            if not content or len(content) < 100:
                return None

            # Check if content is relevant to keywords
            if not self._is_relevant_content(content, keywords):
                return None

            # Process and store content
            content_data = {
                "url": url,
                "title": self._extract_title(response.text),
                "domain": urlparse(url).netloc,
                "ts": datetime.utcnow().isoformat(),
                "published_at": self._extract_published_date(response.text),
                "text_raw": response.text,
                "text_clean": content,
                "extract_method": "trafilatura",  # Primary method
                "content_hash": hashlib.md5(content.encode()).hexdigest(),
                "metadata": {
                    "content_length": len(content),
                    "response_status": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "keywords_matched": keywords,
                },
            }

            # Cache the content
            self._cache_content(content_data)

            # Store in database
            source_id = self._store_source(url, content)
            if source_id:
                self._chunk_and_store_content(source_id, content)

                return content_data

        except Exception as e:
            log.error(f"Failed to fetch {url}: {e}")

        return None

    def _apply_rate_limiting(self):
        """Apply rate limiting for web requests."""
        # Simple rate limiting - could be enhanced with more sophisticated logic
        time.sleep(2)  # 2 second delay between requests

    def _extract_published_date(self, html: str) -> Optional[str]:
        """Extract published date from HTML."""
        # Look for common date patterns
        date_patterns = [
            r'<meta property="article:published_time" content="([^"]+)"',
            r'<meta name="publish_date" content="([^"]+)"',
            r'<time datetime="([^"]+)"',
            r'<span class="date">([^<]+)</span>',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_text_content(self, html: str) -> str:
        """Extract text content from HTML."""
        # Try trafilatura first if available
        try:
            import trafilatura

            extracted = trafilatura.extract(html)
            if extracted and len(extracted) > 100:
                return extracted
        except ImportError:
            pass

        # Fallback to BeautifulSoup
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Remove script and style tags
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)

            return text
        except ImportError:
            pass

        # Last resort: regex-based extraction
        # Remove script and style tags
        html = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(
            r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE
        )

        # Extract text from remaining HTML
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def _extract_title(self, html: str) -> str:
        """Extract title from HTML."""
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        return "Untitled"

    def _is_relevant_content(self, content: str, keywords: List[str]) -> bool:
        """Check if content is relevant to the given keywords."""
        content_lower = content.lower()
        keyword_matches = sum(
            1 for keyword in keywords if keyword.lower() in content_lower
        )
        return keyword_matches > 0

    def _store_source(self, url: str, content: str) -> Optional[int]:
        """Store source in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT OR REPLACE INTO sources (url, title, domain, content_hash, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        url,
                        "Extracted Title",  # Will be updated later
                        urlparse(url).netloc,
                        hashlib.md5(content.encode()).hexdigest(),
                        json.dumps({"extracted_at": datetime.utcnow().isoformat()}),
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            log.error(f"Failed to store source: {e}")
            return None

    def _chunk_and_store_content(self, source_id: int, content: str):
        """Chunk content and store in database."""
        # Simple chunking by paragraphs
        chunks = content.split("\n\n")

        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 50:  # Skip very short chunks
                continue

            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()

            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO chunks (source_id, chunk_text, chunk_hash, token_count)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            source_id,
                            chunk,
                            chunk_hash,
                            len(chunk.split()),  # Rough token count
                        ),
                    )
                    conn.commit()
            except Exception as e:
                log.error(f"Failed to store chunk: {e}")

    def _fetch_from_source_type(
        self, source_type: str, keywords: List[str]
    ) -> Optional[Dict]:
        """Fetch content from a specific source type."""
        # This would implement specific logic for different source types
        # For now, return None
        log.info(f"Source type {source_type} not yet implemented")
        return None

    def _collect_from_search(self, keywords: List[str], max_sources: int) -> List[Dict]:
        """Collect content from general search."""
        # This would implement search-based collection
        # For now, return empty list
        log.info("Search-based collection not yet implemented")
        return []


def main(brief=None, models_config=None, mode="reuse", slug=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Collect research content")
    parser.add_argument("--brief", help="Path to brief file")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    parser.add_argument(
        "--mode",
        choices=["reuse", "live"],
        default="reuse",
        help="Mode: reuse (cache only) or live (with API calls)",
    )
    parser.add_argument(
        "--slug", required=True, help="Topic slug for research collection"
    )
    args = parser.parse_args()

    # Use command line args if provided, otherwise use function parameters
    mode = args.mode if hasattr(args, "mode") else mode
    slug = args.slug if hasattr(args, "slug") else slug

    if not slug:
        log.error("Slug is required")
        return

    # Load brief data
    if brief is None:
        if args.brief:
            with open(args.brief, "r") as f:
                brief = json.load(f)
        elif args.brief_data:
            brief = json.loads(args.brief_data)
        else:
            brief = {"keywords_include": [slug]}

    log.info(f"[collect] Starting research collection for slug: {slug}, mode: {mode}")

    # Initialize collector
    collector = ResearchCollector(models_config, mode)

    # Collect research
    sources = collector.collect_from_brief(brief)

    # Save results
    output_dir = Path(BASE) / "data" / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save collected sources
    sources_path = output_dir / "collected_sources.json"
    with open(sources_path, "w", encoding="utf-8") as f:
        json.dump(sources, f, indent=2, ensure_ascii=False)

    log.info(
        f"[collect] Research collection completed: {len(sources)} sources collected"
    )
    log.info(f"[collect] Results saved to {sources_path}")

    return sources


if __name__ == "__main__":
    main()
