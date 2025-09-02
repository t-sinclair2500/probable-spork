"""
Tests for orchestrator hardening improvements:
- Safe slug derivation
- YT-only gating with from-step respect
- Brief list field normalization
"""

from types import SimpleNamespace

import pytest
from pathlib import Path


def test_safe_slug_from_script():
    """Test safe slug derivation handles various filename patterns."""
    from bin.utils.slug import safe_slug_from_script

    # Test underscore handling (should convert to hyphens for consistency)
    assert safe_slug_from_script("2025_08_21-My Slug.txt") == "2025-08-21-my-slug"
    assert safe_slug_from_script("nospace.mov") == "nospace"

    # Test space handling
    assert safe_slug_from_script("My Video Title.mp4") == "my-video-title"

    # Test mixed separators
    assert (
        safe_slug_from_script("video_with spaces-and_dashes.mp4")
        == "video-with-spaces-and-dashes"
    )

    # Test edge cases
    assert safe_slug_from_script("") == "unnamed"
    assert safe_slug_from_script("   ") == "unnamed"
    assert safe_slug_from_script("A--B---C") == "a-b-c"

    # Test Path objects
    assert safe_slug_from_script(Path("test_file.txt")) == "test-file"


def test_normalize_list_field_handles_mixed():
    """Test brief list field normalization handles various input types."""
    from bin.brief_loader import _normalize_list_field

    # Test mixed content
    assert _normalize_list_field(["A", None, 3, "  "]) == ["A", "3"]

    # Test string input
    assert _normalize_list_field("single item") == ["single item"]
    assert _normalize_list_field("  ") == []
    assert _normalize_list_field("") == []

    # Test list input
    assert _normalize_list_field(["a", "b", "c"]) == ["a", "b", "c"]
    assert _normalize_list_field([1, 2, 3]) == ["1", "2", "3"]
    assert _normalize_list_field([None, "", "valid"]) == ["valid"]

    # Test None input
    assert _normalize_list_field(None) == []

    # Test scalar input
    assert _normalize_list_field(42) == ["42"]
    assert _normalize_list_field(True) == ["True"]


def test_should_run_shared_ingestion_behaviour():
    """Test the _should_run_shared_ingestion function respects --yt-only and --from-step."""
    from bin.run_pipeline import _should_run_shared_ingestion

    # Test yt_only=True without from_step
    args = SimpleNamespace(yt_only=True, from_step=None)
    assert _should_run_shared_ingestion(args) is False

    # Test yt_only=True with non-ingestion from_step
    args = SimpleNamespace(yt_only=True, from_step="assemble")
    assert _should_run_shared_ingestion(args) is False

    # Test yt_only=True with ingestion from_step
    args = SimpleNamespace(yt_only=True, from_step="research_collect")
    assert _should_run_shared_ingestion(args) is True

    args = SimpleNamespace(yt_only=True, from_step="ingest")
    assert _should_run_shared_ingestion(args) is True

    args = SimpleNamespace(yt_only=True, from_step="ingestion")
    assert _should_run_shared_ingestion(args) is True

    # Test case insensitivity
    args = SimpleNamespace(yt_only=True, from_step="INGEST")
    assert _should_run_shared_ingestion(args) is True

    args = SimpleNamespace(yt_only=True, from_step="  ingest  ")
    assert _should_run_shared_ingestion(args) is True

    # Test yt_only=False (default behavior)
    args = SimpleNamespace(yt_only=False, from_step=None)
    assert _should_run_shared_ingestion(args) is True

    args = SimpleNamespace(yt_only=False, from_step="assemble")
    assert _should_run_shared_ingestion(args) is True

    # Test missing attributes (graceful fallback)
    args = SimpleNamespace()
    assert _should_run_shared_ingestion(args) is True


def test_brief_normalization_integration():
    """Test that brief loading properly normalizes list fields."""
    from bin.brief_loader import _normalize_list_field

    # Test that the normalization is applied to known list fields
    # This test would require a mock brief file, but we can test the function directly
    # Test that tags, questions, sources are normalized if present
    test_brief = {
        "title": "Test Brief",
        "audience": ["owner", None, "manager"],
        "keywords_include": ["kw1", "", "kw2"],
        "tags": ["tag1", None, 42, "tag2"],
        "questions": ["q1", "", "q2"],
        "sources": ["src1", None, "src2"],
    }

    # Simulate the normalization that would happen in _normalize_brief_fields
    normalized = test_brief.copy()
    normalized["audience"] = _normalize_list_field(normalized.get("audience"))
    normalized["keywords_include"] = _normalize_list_field(
        normalized.get("keywords_include")
    )
    normalized["tags"] = _normalize_list_field(normalized.get("tags"))
    normalized["questions"] = _normalize_list_field(normalized.get("questions"))
    normalized["sources"] = _normalize_list_field(normalized.get("sources"))

    assert normalized["audience"] == ["owner", "manager"]
    assert normalized["keywords_include"] == ["kw1", "kw2"]
    assert normalized["tags"] == ["tag1", "42", "tag2"]
    assert normalized["questions"] == ["q1", "q2"]
    assert normalized["sources"] == ["src1", "src2"]


if __name__ == "__main__":
    pytest.main([__file__])
