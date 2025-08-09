"""
Test configuration and fixtures for asset testing strategy.

This module provides pytest fixtures and monkeypatching to ensure:
- REUSE mode tests make no network calls
- LIVE mode tests are properly marked and controlled
- Test isolation and repeatability
"""

import os
import sys
from unittest.mock import patch

import pytest
import requests

# Ensure repo root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import load_config


@pytest.fixture(scope="session")
def test_config():
    """Load test configuration"""
    return load_config()


@pytest.fixture(scope="session") 
def test_env():
    """Provide test environment variables"""
    return dict(os.environ)


@pytest.fixture
def reuse_mode_env(monkeypatch):
    """Set environment for reuse mode testing"""
    monkeypatch.setenv("TEST_ASSET_MODE", "reuse")
    # Block all network requests in reuse mode
    monkeypatch.setattr(requests, "get", mock_requests_get_reuse)
    monkeypatch.setattr(requests, "post", mock_requests_post_reuse)
    return {"TEST_ASSET_MODE": "reuse"}


@pytest.fixture
def live_mode_env(monkeypatch):
    """Set environment for live mode testing"""
    monkeypatch.setenv("TEST_ASSET_MODE", "live")
    monkeypatch.setenv("ASSET_LIVE_BUDGET", "3")  # Low budget for testing
    return {"TEST_ASSET_MODE": "live", "ASSET_LIVE_BUDGET": "3"}


def mock_requests_get_reuse(*args, **kwargs):
    """Mock requests.get for reuse mode - should never be called"""
    raise RuntimeError(
        "Network request attempted in REUSE mode! "
        "This indicates the test is not properly isolated. "
        f"URL: {args[0] if args else 'unknown'}"
    )


def mock_requests_post_reuse(*args, **kwargs):
    """Mock requests.post for reuse mode - should never be called"""
    raise RuntimeError(
        "Network request attempted in REUSE mode! "
        "This indicates the test is not properly isolated. "
        f"URL: {args[0] if args else 'unknown'}"
    )


@pytest.fixture
def temp_assets_dir(tmp_path):
    """Create temporary assets directory for testing"""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    return str(assets_dir)


@pytest.fixture
def temp_fixtures_dir(tmp_path):
    """Create temporary fixtures directory for testing"""
    fixtures_dir = tmp_path / "assets" / "fixtures"
    fixtures_dir.mkdir(parents=True)
    
    # Create generic fixtures subdirectory
    generic_dir = fixtures_dir / "_generic"
    generic_dir.mkdir()
    
    return str(fixtures_dir)


@pytest.fixture
def sample_script_content():
    """Provide sample script content for testing"""
    return """
    Welcome to our AI tools guide!
    
    [B-ROLL: typing on keyboard]
    First, let's look at some productivity tools.
    
    [B-ROLL: computer screen with software]
    These tools can help automate your workflow.
    
    [B-ROLL: person working at desk]
    Remember to subscribe for more content!
    """


@pytest.fixture
def sample_outline():
    """Provide sample outline for testing"""
    return {
        "title_options": ["AI Tools Guide"],
        "sections": [
            {
                "title": "Introduction",
                "beats": ["Welcome message", "Tool overview"],
                "broll": ["typing on keyboard", "computer screen"]
            },
            {
                "title": "Productivity Tools", 
                "beats": ["Tool selection", "Use cases"],
                "broll": ["software interface", "workflow automation"]
            }
        ],
        "tags": ["ai", "productivity", "tools"],
        "tone": "helpful",
        "target_len_sec": 30
    }


class MockResponse:
    """Mock HTTP response for testing"""
    
    def __init__(self, json_data=None, status_code=200, content=b""):
        self.json_data = json_data or {}
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": "application/json"}
    
    def json(self):
        return self.json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def mock_pixabay_response():
    """Mock successful Pixabay API response"""
    return MockResponse({
        "hits": [
            {
                "id": 12345,
                "webformatURL": "https://example.com/test1.jpg",
                "largeImageURL": "https://example.com/test1_large.jpg", 
                "user": "test_user",
                "tags": "test, image",
                "type": "photo"
            }
        ],
        "total": 1
    })


@pytest.fixture
def mock_pexels_response():
    """Mock successful Pexels API response"""
    return MockResponse({
        "photos": [
            {
                "id": 67890,
                "src": {
                    "original": "https://example.com/pexels_test.jpg",
                    "large": "https://example.com/pexels_test_large.jpg"
                },
                "photographer": "Test Photographer",
                "alt": "Test image"
            }
        ],
        "total_results": 1
    })


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "liveapi: marks tests that require live API access (disabled by default)"
    )
    config.addinivalue_line(
        "markers", "reuse: marks tests that use fixture reuse mode (default)"
    )


def pytest_collection_modifyitems(config, items):
    """Add markers to tests based on file location and name patterns"""
    for item in items:
        # Mark live API tests
        if "live" in item.nodeid or "liveapi" in item.keywords:
            item.add_marker(pytest.mark.liveapi)
        
        # Mark reuse tests (most tests should be reuse by default)
        if "reuse" in item.nodeid or "reuse" not in item.keywords:
            item.add_marker(pytest.mark.reuse)


@pytest.fixture(autouse=True)
def default_reuse_mode(monkeypatch):
    """Auto-apply reuse mode for all tests unless explicitly overridden"""
    if not os.environ.get("TEST_ASSET_MODE"):
        monkeypatch.setenv("TEST_ASSET_MODE", "reuse")
