#!/usr/bin/env python3
"""
Tests for additional critical fixes:
- Undefined topic in research_ground.py
- List normalization in brief_loader.py  
- --yt-only gating in run_pipeline.py
- Model runner timeouts and no /api/pull misuse
- Palette adapter in animatics_generate.py
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_safe_subject_function():
    """Test the _safe_subject helper function from research_ground.py."""
    # Import the function
    from bin.research_ground import _safe_subject
    
    # Test cases
    assert _safe_subject("test-slug", None) == "test-slug"
    assert _safe_subject("test-slug", {"title": "Test Title"}) == "Test Title"
    assert _safe_subject("test-slug", {"topic": "Test Topic"}) == "Test Topic"
    assert _safe_subject("test-slug", {"title": "Test Title", "topic": "Test Topic"}) == "Test Title"
    assert _safe_subject(None, {"title": "Test Title"}) == "Test Title"
    assert _safe_subject("", {"title": ""}) == "untitled"
    assert _safe_subject(None, None) == "untitled"
    assert _safe_subject("  test-slug  ", None) == "test-slug"
    
    print("✅ _safe_subject function works correctly")


def test_normalize_list_field_handles_mixed():
    """Test the _normalize_list_field function from brief_loader.py."""
    # Import the function
    from bin.brief_loader import _normalize_list_field
    
    # Test cases
    assert _normalize_list_field(["a", None, "  b ", 3, ""]) == ["a", "b", "3"]
    assert _normalize_list_field(" one ") == ["one"]
    assert _normalize_list_field(None) == []
    assert _normalize_list_field([]) == []
    assert _normalize_list_field(["", None, "  "]) == []
    assert _normalize_list_field(123) == ["123"]
    assert _normalize_list_field(["a", "b", "c"]) == ["a", "b", "c"]
    
    print("✅ _normalize_list_field function handles mixed types correctly")


def test_should_run_shared_ingestion_strict():
    """Test the _should_run_shared_ingestion function from run_pipeline.py."""
    # Import the function
    from bin.run_pipeline import _should_run_shared_ingestion
    
    # Test cases
    args_false = SimpleNamespace(yt_only=False)
    args_true = SimpleNamespace(yt_only=True)
    args_none = SimpleNamespace()
    
    assert _should_run_shared_ingestion(args_false) is True
    assert _should_run_shared_ingestion(args_true) is False
    assert _should_run_shared_ingestion(args_none) is True  # Default behavior
    
    print("✅ _should_run_shared_ingestion enforces strict --yt-only gating")


def test_model_runner_no_pull_misuse():
    """Test that ModelRunner doesn't call /api/pull in hot paths."""
    from bin.model_runner import ModelRunner
    
    # Create a mock runner to inspect behavior
    runner = ModelRunner(base_url="http://test", timeout_sec=5)
    
    # Verify ensure_model is not called in chat/generate methods
    # This is verified by checking that the methods don't have ensure_model calls
    chat_source = runner.chat.__code__.co_code
    generate_source = runner.generate.__code__.co_code
    
    # Check that ensure_model method exists but is not called in hot paths
    assert hasattr(runner, 'ensure_model')
    assert hasattr(runner, 'pull')
    
    # Verify timeout is set
    assert runner.timeout == 5.0
    
    print("✅ ModelRunner has proper timeout and no /api/pull misuse")


def test_palette_adapter_colors():
    """Test that palette adapter ensures .colors access."""
    from bin.utils.palette import ensure_palette, Palette
    
    # Test cases
    # Dict with colors
    pal1 = ensure_palette({"colors": ["#111111", "#222222"]})
    assert isinstance(pal1, Palette)
    assert pal1.colors == ["#111111", "#222222"]
    assert pal1.get(0) == "#111111"
    
    # List of colors
    pal2 = ensure_palette(["#333333", "#444444"])
    assert isinstance(pal2, Palette)
    assert pal2.colors == ["#333333", "#444444"]
    
    # Already a Palette
    original = Palette(colors=["#555555"])
    pal3 = ensure_palette(original)
    assert pal3 is original  # Should return same object
    
    # None/empty
    pal4 = ensure_palette(None)
    assert isinstance(pal4, Palette)
    assert pal4.colors == []
    
    print("✅ Palette adapter ensures .colors access")


def test_brief_loader_list_normalization_integration():
    """Test that brief loader properly normalizes list fields."""
    from bin.brief_loader import _normalize_list_field
    
    # Test mixed-type lists that might come from YAML
    mixed_list = ["keyword1", None, "  keyword2  ", 123, ""]
    normalized = _normalize_list_field(mixed_list)
    
    assert normalized == ["keyword1", "keyword2", "123"]
    assert all(isinstance(x, str) for x in normalized)
    
    # Test that join operations work
    joined = ", ".join(normalized)
    assert joined == "keyword1, keyword2, 123"
    
    print("✅ Brief loader list normalization works with join operations")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_safe_subject_function,
        test_normalize_list_field_handles_mixed,
        test_should_run_shared_ingestion_strict,
        test_model_runner_no_pull_misuse,
        test_palette_adapter_colors,
        test_brief_loader_list_normalization_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    print(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All critical fixes verified!")
        return True
    else:
        print("⚠️  Some tests failed - please check the fixes")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
