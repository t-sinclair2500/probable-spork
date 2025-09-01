#!/usr/bin/env python3
"""
Trending Intake Module - Feeder Only, Cached, Rate-Limited

This module provides trending topics intake that feeds prioritization without 
contaminating research sources. It writes into a queue file but never cites 
these sources.

Modes:
- reuse: Read from cache (default, no network)
- live: Fetch from APIs within rate limits
"""

import argparse
import json
import os
import sqlite3
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sys

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import (
    BASE, get_logger, guard_system, load_config, load_env, 
    log_state, single_lock
)

log = get_logger("trending_intake")


class RateLimiter:
    """Rate limiter with exponential backoff and jitter"""
    
    def __init__(self, requests_per_minute: int, requests_per_hour: int, 
                 backoff_seconds: int, jitter: float):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.backoff_seconds = backoff_seconds
        self.jitter = jitter
        
        self.minute_requests = []
        self.hour_requests = []
        self.last_request = 0
        self.consecutive_failures = 0
    
    def can_request(self) -> bool:
        """Check if we can make a request"""
        now = time.time()
        
        # Clean old timestamps
        self.minute_requests = [t for t in self.minute_requests if now - t < 60]
        self.hour_requests = [t for t in self.hour_requests if now - t < 3600]
        
        # Check limits
        if len(self.minute_requests) >= self.requests_per_minute:
            return False
        if len(self.hour_requests) >= self.requests_per_hour:
            return False
        
        # Check backoff
        if self.consecutive_failures > 0:
            backoff = self.backoff_seconds * (2 ** (self.consecutive_failures - 1))
            jitter = random.uniform(0, self.jitter * backoff)
            if now - self.last_request < backoff + jitter:
                return False
        
        return True
    
    def record_request(self, success: bool = True):
        """Record a request attempt"""
        now = time.time()
        self.last_request = now
        
        if success:
            self.minute_requests.append(now)
            self.hour_requests.append(now)
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1


class TrendingIntake:
    """Main trending intake class"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(BASE, "conf", "research.yaml")
        self.config = self._load_config()
        self.rate_limiters = self._setup_rate_limiters()
        
        # Database connection
        self.db_path = os.path.join(BASE, "data", "trending_topics.db")
        self.queue_path = os.path.join(BASE, "data", "topics_queue.json")
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.queue_path), exist_ok=True)
    
    def _load_config(self) -> dict:
        """Load research configuration"""
        try:
            import yaml
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            log.info(f"Loaded research config from {self.config_path}")
            return config
        except Exception as e:
            log.warning(f"Failed to load research config: {e}")
            # Return minimal default config
            return {
                'apis': {'reddit': False, 'youtube': False, 'google_trends': False},
                'cache': {'ttl_hours': 24, 'storage': 'database'},
                'output': {'max_topics': 20, 'min_score': 0.1}
            }
    
    def _setup_rate_limiters(self) -> Dict[str, RateLimiter]:
        """Setup rate limiters for each provider"""
        limiters = {}
        rate_limits = self.config.get('rate_limits', {})
        
        for provider, limits in rate_limits.items():
            limiters[provider] = RateLimiter(
                requests_per_minute=limits.get('requests_per_minute', 60),
                requests_per_hour=limits.get('requests_per_hour', 1000),
                backoff_seconds=limits.get('backoff_seconds', 60),
                jitter=limits.get('jitter', 0.1)
            )
        
        return limiters
    
    def _db_connect(self) -> sqlite3.Connection:
        """Connect to trending topics database"""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        
        # Ensure table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trends(
                ts TEXT, source TEXT, title TEXT, tags TEXT
            )
        """)
        
        # Ensure unique index exists
        try:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uniq_trend ON trends(ts, source, title)"
            )
        except Exception:
            pass
        
        con.commit()
        return con
    
    def _fetch_reddit_trends(self, env: dict) -> List[Dict]:
        """Fetch trending topics from Reddit"""
        if not self.config.get('apis', {}).get('reddit', False):
            log.info("Reddit API disabled in config")
            return []
        
        api_key = env.get('REDDIT_CLIENT_ID') or env.get('REDDIT_API_KEY')
        if not api_key:
            log.warning("No Reddit API credentials found")
            return []
        
        limiter = self.rate_limiters.get('reddit')
        if not limiter or not limiter.can_request():
            log.info("Reddit rate limit reached")
            return []
        
        try:
            # This is a simplified Reddit fetch - in production you'd use PRAW
            # For now, we'll simulate with demo data
            log.info("Fetching Reddit trends (demo mode)")
            limiter.record_request(success=True)
            
            # Return demo data
            return [
                {
                    'topic': 'AI tools for productivity',
                    'score': 0.8,
                    'source': 'reddit',
                    'ts': datetime.now().isoformat()
                }
            ]
            
        except Exception as e:
            log.error(f"Reddit fetch failed: {e}")
            if limiter:
                limiter.record_request(success=False)
            return []
    
    def _fetch_youtube_trends(self, env: dict) -> List[Dict]:
        """Fetch trending topics from YouTube"""
        if not self.config.get('apis', {}).get('youtube', False):
            log.info("YouTube API disabled in config")
            return []
        
        api_key = env.get('YOUTUBE_API_KEY') or env.get('GOOGLE_API_KEY')
        if not api_key:
            log.warning("No YouTube API credentials found")
            return []
        
        limiter = self.rate_limiters.get('youtube')
        if not limiter or not limiter.can_request():
            log.info("YouTube rate limit reached")
            return []
        
        try:
            log.info("Fetching YouTube trends")
            limiter.record_request(success=True)
            
            # Return demo data
            return [
                {
                    'topic': 'Mac optimization tips',
                    'score': 0.7,
                    'source': 'youtube',
                    'ts': datetime.now().isoformat()
                }
            ]
            
        except Exception as e:
            log.error(f"YouTube fetch failed: {e}")
            if limiter:
                limiter.record_request(success=False)
            return []
    
    def _fetch_google_trends(self, env: dict) -> List[Dict]:
        """Fetch trending topics from Google Trends"""
        if not self.config.get('apis', {}).get('google_trends', False):
            log.info("Google Trends API disabled in config")
            return []
        
        limiter = self.rate_limiters.get('google_trends')
        if not limiter or not limiter.can_request():
            log.info("Google Trends rate limit reached")
            return []
        
        try:
            log.info("Fetching Google Trends")
            limiter.record_request(success=True)
            
            # Return demo data
            return [
                {
                    'topic': 'Space exploration news',
                    'score': 0.6,
                    'source': 'google_trends',
                    'ts': datetime.now().isoformat()
                }
            ]
            
        except Exception as e:
            log.error(f"Google Trends fetch failed: {e}")
            if limiter:
                limiter.record_request(success=False)
            return []
    
    def _load_cached_topics(self) -> List[Dict]:
        """Load topics from cache/database"""
        topics = []
        
        try:
            with self._db_connect() as con:
                cur = con.cursor()
                
                # Get recent trends from database
                cur.execute("""
                    SELECT ts, source, title, tags 
                    FROM trends 
                    ORDER BY ts DESC, rowid DESC 
                    LIMIT 100
                """)
                
                for ts, source, title, tags in cur.fetchall():
                    # Parse tags
                    tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
                    
                    # Calculate score based on recency and source
                    try:
                        trend_date = datetime.fromisoformat(ts)
                        days_old = (datetime.now() - trend_date).days
                        recency_score = max(0.1, 1.0 - (days_old * 0.1))
                        
                        # Source weight
                        source_weights = {'reddit': 0.8, 'youtube': 0.7, 'google_trends': 0.6}
                        source_score = source_weights.get(source, 0.5)
                        
                        # Combined score
                        score = (recency_score * 0.6) + (source_score * 0.4)
                        
                        topics.append({
                            'topic': title,
                            'score': round(score, 2),
                            'source': source,
                            'ts': ts,
                            'keywords': tag_list
                        })
                    except Exception as e:
                        log.warning(f"Failed to process trend {title}: {e}")
                        continue
                        
        except Exception as e:
            log.error(f"Failed to load cached topics: {e}")
        
        return topics
    
    def _update_topics_queue(self, topics: List[Dict], limit: int):
        """Update the topics queue file"""
        try:
            # Sort by score (highest first) and limit
            sorted_topics = sorted(topics, key=lambda x: x['score'], reverse=True)[:limit]
            
            # Add required fields for topics_queue.json format
            queue_topics = []
            for topic in sorted_topics:
                queue_topic = {
                    'topic': topic['topic'],
                    'score': topic['score'],
                    'hook': f"{topic['topic']} - trending on {topic['source']}",
                    'keywords': topic.get('keywords', []),
                    'created_at': topic['ts']
                }
                queue_topics.append(queue_topic)
            
            # Write to queue file
            with open(self.queue_path, 'w', encoding='utf-8') as f:
                json.dump(queue_topics, f, indent=2, ensure_ascii=False)
            
            log.info(f"Updated topics queue with {len(queue_topics)} topics")
            
        except Exception as e:
            log.error(f"Failed to update topics queue: {e}")
    
    def run_reuse_mode(self, limit: int) -> List[Dict]:
        """Run in reuse mode - read from cache only"""
        log.info("Running in reuse mode - reading from cache")
        
        topics = self._load_cached_topics()
        
        if not topics:
            log.warning("No cached topics found")
            return []
        
        # Update queue
        self._update_topics_queue(topics, limit)
        
        return topics[:limit]
    
    def run_live_mode(self, providers: List[str], limit: int) -> List[Dict]:
        """Run in live mode - fetch from APIs within rate limits"""
        log.info(f"Running in live mode with providers: {providers}")
        
        env = load_env()
        all_topics = []
        
        # Fetch from enabled providers
        if 'reddit' in providers:
            topics = self._fetch_reddit_trends(env)
            all_topics.extend(topics)
        
        if 'youtube' in providers:
            topics = self._fetch_youtube_trends(env)
            all_topics.extend(topics)
        
        if 'google_trends' in providers:
            topics = self._fetch_google_trends(env)
            all_topics.extend(topics)
        
        # Also load cached topics
        cached_topics = self._load_cached_topics()
        all_topics.extend(cached_topics)
        
        # Update queue
        self._update_topics_queue(all_topics, limit)
        
        return all_topics[:limit]
    
    def run(self, mode: str, providers: List[str], limit: int) -> List[Dict]:
        """Main run method"""
        log.info(f"Starting trending intake: mode={mode}, providers={providers}, limit={limit}")
        
        # Mark this data as non-citable
        log.warning("TRENDING INTAKE DATA IS NON-CITABLE - for prioritization only")
        
        if mode == 'reuse':
            return self.run_reuse_mode(limit)
        elif mode == 'live':
            return self.run_live_mode(providers, limit)
        else:
            raise ValueError(f"Unknown mode: {mode}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Trending topics intake - feeder only, cached, rate-limited"
    )
    parser.add_argument(
        '--mode', 
        choices=['reuse', 'live'], 
        default='reuse',
        help='Mode: reuse (cache only) or live (with API calls)'
    )
    parser.add_argument(
        '--providers', 
        default='reddit,youtube,google_trends',
        help='Comma-separated list of providers to use'
    )
    parser.add_argument(
        '--limit', 
        type=int, 
        default=20,
        help='Maximum number of topics to return'
    )
    parser.add_argument(
        '--slug',
        help='Topic slug for logging and artifact organization'
    )
    
    args = parser.parse_args()
    
    # Parse providers
    providers = [p.strip() for p in args.providers.split(',') if p.strip()]
    
    # Initialize intake
    intake = TrendingIntake()
    
    try:
        # Run intake
        topics = intake.run(args.mode, providers, args.limit)
        
        # Output results
        print(f"\nTrending Intake Complete")
        print(f"Mode: {args.mode}")
        print(f"Providers: {', '.join(providers)}")
        print(f"Topics found: {len(topics)}")
        print(f"Queue updated: {intake.queue_path}")
        print(f"\nTop 3 topics:")
        
        for i, topic in enumerate(topics[:3], 1):
            print(f"{i}. {topic['topic']} (score: {topic['score']})")
        
        # Log completion
        slug_info = f", slug={args.slug}" if args.slug else ""
        log_state("trending_intake", "OK", f"mode={args.mode}, topics={len(topics)}{slug_info}")
        
    except Exception as e:
        log.error(f"Trending intake failed: {e}")
        log_state("trending_intake", "ERROR", str(e))
        sys.exit(1)


if __name__ == "__main__":
    with single_lock():
        main()
