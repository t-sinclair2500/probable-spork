"""
Tests for research fixtures and rate limiting:
- Fixture loading and fallback behavior
- Rate limiter with jitter
- Domain scoring from config
"""

import json
import tempfile
import time
from unittest.mock import Mock, patch

import pytest
from pathlib import Path

from bin.research_collect import RateLimiter, ResearchCollector, _load_fixture
from bin.research_ground import ResearchGrounder


def test_fixture_load_returns_non_empty_for_reuse():
    """Test that fixture loading returns non-empty data when fixture exists."""
    # Create a temporary fixture file
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the fixtures directory structure
        fixtures_dir = Path(tmpdir) / "data" / "fixtures"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        fixture_path = fixtures_dir / "test-topic.json"
        fixture_data = [
            {
                "url": "https://example.com/article",
                "title": "Test Article",
                "text": "This is test content for the article.",
                "ts": "2024-01-15T10:30:00Z",
                "domain": "example.com",
            }
        ]
        fixture_path.write_text(json.dumps(fixture_data), encoding="utf-8")

        # Test fixture loading
        with patch("bin.research_collect.BASE", tmpdir):
            result = _load_fixture("test-topic")
            assert len(result) == 1
            assert result[0]["url"] == "https://example.com/article"
            assert result[0]["title"] == "Test Article"


def test_fixture_load_returns_empty_when_not_found():
    """Test that fixture loading returns empty list when fixture doesn't exist."""
    with patch("bin.research_collect.BASE", "/nonexistent"):
        result = _load_fixture("nonexistent-topic")
        assert result == []


def test_fixture_load_handles_invalid_json():
    """Test that fixture loading handles invalid JSON gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the fixtures directory structure
        fixtures_dir = Path(tmpdir) / "data" / "fixtures"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        fixture_path = fixtures_dir / "invalid.json"
        fixture_path.write_text("invalid json content", encoding="utf-8")

        with patch("bin.research_collect.BASE", tmpdir):
            result = _load_fixture("invalid")
            assert result == []


def test_rate_limiter_enforces_minimum_interval():
    """Test that RateLimiter enforces minimum interval with jitter."""
    limits = {
        "test_provider": {
            "min_interval_ms": 100,  # 100ms minimum
            "jitter_ms": 50,  # 0-50ms jitter
        }
    }

    limiter = RateLimiter(limits)

    # First call should not wait
    start_time = time.time()
    limiter.wait("test_provider")
    first_call_time = time.time() - start_time

    # Second call should wait
    start_time = time.time()
    limiter.wait("test_provider")
    second_call_time = time.time() - start_time

    # First call should be fast
    assert first_call_time < 0.01

    # Second call should have waited at least the minimum interval
    assert second_call_time >= 0.1


def test_rate_limiter_handles_zero_interval():
    """Test that RateLimiter handles zero interval correctly."""
    limits = {"no_limit_provider": {"min_interval_ms": 0, "jitter_ms": 0}}

    limiter = RateLimiter(limits)

    # Multiple calls should be fast
    start_time = time.time()
    for _ in range(5):
        limiter.wait("no_limit_provider")
    total_time = time.time() - start_time

    # Should be very fast (no waiting)
    assert total_time < 0.01


def test_rate_limiter_handles_unknown_provider():
    """Test that RateLimiter handles unknown providers gracefully."""
    limits = {"known_provider": {"min_interval_ms": 100, "jitter_ms": 50}}

    limiter = RateLimiter(limits)

    # Unknown provider should not cause errors
    start_time = time.time()
    limiter.wait("unknown_provider")
    call_time = time.time() - start_time

    # Should be fast (no waiting for unknown provider)
    assert call_time < 0.01


def test_research_collector_uses_fixtures_in_reuse_mode():
    """Test that ResearchCollector uses fixtures in reuse mode."""
    with patch("bin.research_collect.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.research.policy.mode = "reuse"
        mock_bundle.research.policy.allow_providers = ["local_fixtures"]
        mock_bundle.research.dict.return_value = {
            "providers": {"rate_limits": {}},
            "domains": {"allowlist": [], "blacklist": []},
            "cache": {
                "disk_cache": {"enabled": True, "base_path": "data/research_cache"},
                "ttl_hours": 24,
            },
        }
        mock_load.return_value = mock_bundle

        with patch("bin.research_collect._load_fixture") as mock_fixture:
            mock_fixture.return_value = [
                {
                    "url": "https://example.com/article",
                    "title": "Test Article",
                    "text": "Test content",
                    "domain": "example.com",
                }
            ]

            collector = ResearchCollector(mode="reuse")
            brief = {"keywords_include": ["test"], "slug": "test-topic"}

            result = collector.collect_from_brief(brief)

            # Should have called fixture loading
            mock_fixture.assert_called_once_with("test-topic")
            assert len(result) == 1
            assert result[0]["url"] == "https://example.com/article"


def test_research_collector_falls_back_to_live_in_reuse_mode():
    """Test that ResearchCollector falls back to live providers when fixture is empty."""
    with patch("bin.research_collect.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.research.policy.mode = "reuse"
        mock_bundle.research.policy.allow_providers = ["local_fixtures"]
        mock_bundle.research.dict.return_value = {
            "providers": {"rate_limits": {}},
            "domains": {"allowlist": [], "blacklist": []},
            "cache": {
                "disk_cache": {"enabled": True, "base_path": "data/research_cache"},
                "ttl_hours": 24,
            },
        }
        mock_load.return_value = mock_bundle

        with patch("bin.research_collect._load_fixture") as mock_fixture:
            mock_fixture.return_value = []  # Empty fixture

            with patch.object(ResearchCollector, "_collect_from_source") as mock_source:
                mock_source.return_value = None

                collector = ResearchCollector(mode="reuse")
                # Set the collection config directly
                collector.research_config = Mock()
                collector.research_config.collection = {"max_sources_per_topic": 15}

                brief = {
                    "keywords_include": ["test"],
                    "sources_preferred": ["https://example.com"],
                }

                result = collector.collect_from_brief(brief)

                # Should have tried fixture first, then fallen back to live
                mock_fixture.assert_called_once_with("test")
                assert result == []


def test_domain_scoring_uses_config_values():
    """Test that domain scoring uses configured values from research.yaml."""
    with patch("bin.research_ground.load_all_configs") as mock_load:
        # Mock config bundle with domain scores
        mock_bundle = Mock()
        mock_bundle.research.dict.return_value = {
            "domain_scores": {
                "wikipedia.org": 1.0,
                "nytimes.com": 0.9,
                "medium.com": 0.5,
            }
        }
        mock_load.return_value = mock_bundle

        with patch("bin.research_ground.get_research_policy") as mock_policy:
            mock_policy.return_value = Mock(
                min_citations=2, coverage_threshold=0.65, min_domain_score=0.6
            )

            with patch("pathlib.Path.exists", return_value=True):
                grounder = ResearchGrounder()

                # Test domain scoring
                assert grounder._score_domain("https://en.wikipedia.org/article") == 1.0
                assert grounder._score_domain("https://www.nytimes.com/article") == 0.9
                assert grounder._score_domain("https://medium.com/article") == 0.5
                assert (
                    grounder._score_domain("https://unknown.com/article") == 0.5
                )  # Default


def test_domain_scoring_handles_case_insensitive():
    """Test that domain scoring handles case insensitive matching."""
    with patch("bin.research_ground.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.research.dict.return_value = {
            "domain_scores": {"wikipedia.org": 1.0}
        }
        mock_load.return_value = mock_bundle

        with patch("bin.research_ground.get_research_policy") as mock_policy:
            mock_policy.return_value = Mock(
                min_citations=2, coverage_threshold=0.65, min_domain_score=0.6
            )

            with patch("pathlib.Path.exists", return_value=True):
                grounder = ResearchGrounder()

                # Test case insensitive matching
                assert grounder._score_domain("https://WIKIPEDIA.ORG/article") == 1.0
                assert (
                    grounder._score_domain("https://www.Wikipedia.org/article") == 1.0
                )


def test_research_collector_applies_rate_limiting():
    """Test that ResearchCollector applies rate limiting to provider calls."""
    with patch("bin.research_collect.load_all_configs") as mock_load:
        # Mock config bundle with rate limits
        mock_bundle = Mock()
        mock_bundle.research.dict.return_value = {
            "providers": {
                "rate_limits": {
                    "web_scraping": {"min_interval_ms": 100, "jitter_ms": 50}
                }
            },
            "domains": {"allowlist": [], "blacklist": []},
            "cache": {
                "disk_cache": {"enabled": True, "base_path": "data/research_cache"},
                "ttl_hours": 24,
            },
        }
        mock_load.return_value = mock_bundle

        with patch("bin.research_collect.get_research_policy") as mock_policy:
            mock_policy.return_value = Mock(mode="live")

            collector = ResearchCollector(mode="live")

            # Test that rate limiter is initialized
            assert hasattr(collector, "rate_limiter")
            assert (
                collector.rate_limiter.limits["web_scraping"]["min_interval_ms"] == 100
            )


def test_fixture_slug_extraction():
    """Test that fixture slug is extracted correctly from brief."""
    with patch("bin.research_collect.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.research.policy.mode = "reuse"
        mock_bundle.research.dict.return_value = {
            "providers": {"rate_limits": {}},
            "domains": {"allowlist": [], "blacklist": []},
            "cache": {
                "disk_cache": {"enabled": True, "base_path": "data/research_cache"},
                "ttl_hours": 24,
            },
        }
        mock_load.return_value = mock_bundle

        with patch("bin.research_collect._load_fixture") as mock_fixture:
            mock_fixture.return_value = []

            collector = ResearchCollector(mode="reuse")
            # Set the collection config directly
            collector.research_config = Mock()
            collector.research_config.collection = {"max_sources_per_topic": 15}

            # Test different slug extraction scenarios
            brief_with_slug = {
                "slug": "design-thinking",
                "keywords_include": ["design"],
            }
            collector.collect_from_brief(brief_with_slug)
            mock_fixture.assert_called_with("design-thinking")

            brief_with_topic = {"topic": "ai-ethics", "keywords_include": ["ai"]}
            collector.collect_from_brief(brief_with_topic)
            mock_fixture.assert_called_with("ai-ethics")

            brief_with_keywords = {"keywords_include": ["machine learning"]}
            collector.collect_from_brief(brief_with_keywords)
            mock_fixture.assert_called_with("machine-learning")


if __name__ == "__main__":
    pytest.main([__file__])
