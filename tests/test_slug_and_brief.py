# tests/test_slug_and_brief.py
import os
import sys
import types

# Ensure repo root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.utils.slug import safe_slug_from_script

def test_safe_slug_from_script_basic():
    """Test basic slug extraction from various filename patterns."""
    assert safe_slug_from_script("scripts/myVideo.txt") == "myvideo"
    assert safe_slug_from_script("scripts/2024  BIG_launch!!.txt") == "2024-big-launch"
    assert safe_slug_from_script("scripts/no_underscore_but_good.txt") == "no-underscore-but-good"
    assert safe_slug_from_script("weird/..//----.txt") == "unnamed"

def test_safe_slug_from_script_edge_cases():
    """Test edge cases for slug extraction."""
    # No underscores
    assert safe_slug_from_script("simple.txt") == "simple"
    assert safe_slug_from_script("simple") == "simple"
    
    # Multiple underscores
    assert safe_slug_from_script("2024_08_15_topic.txt") == "2024-08-15-topic"
    
    # Special characters
    assert safe_slug_from_script("file@#$%^&*().txt") == "file"
    assert safe_slug_from_script("file with spaces.txt") == "file-with-spaces"
    
    # Empty or problematic names
    assert safe_slug_from_script("") == "unnamed"
    assert safe_slug_from_script("----.txt") == "unnamed"

def test_brief_normalization():
    """Test brief list field normalization."""
    # Import the helper function
    from bin.brief_loader import _normalize_list_field

    # Test None input
    assert _normalize_list_field(None) == []
    
    # Test string input
    assert _normalize_list_field("alpha") == ["alpha"]
    assert _normalize_list_field("  alpha  ") == ["alpha"]
    
    # Test list input with mixed types
    assert _normalize_list_field(["a", " b ", None, 3, "", "   "]) == ["a", "b", "3"]
    
    # Test non-string scalar
    assert _normalize_list_field(42) == ["42"]
    assert _normalize_list_field(True) == ["True"]
    
    # Test empty inputs
    assert _normalize_list_field([]) == []
    assert _normalize_list_field("") == []
    assert _normalize_list_field("   ") == []

def test_should_run_shared_ingestion_logic():
    """Test the ingestion gating logic."""
    # Import the helper function
    from bin.run_pipeline import _should_run_shared_ingestion

    # Create mock args objects
    def mk(yto, fs):
        o = types.SimpleNamespace()
        o.yt_only = yto
        o.from_step = fs
        return o

    # Test cases
    assert _should_run_shared_ingestion(mk(False, None)) is True
    assert _should_run_shared_ingestion(mk(True, None)) is False
    assert _should_run_shared_ingestion(mk(True, "assemble")) is False
    assert _should_run_shared_ingestion(mk(True, "ingest")) is True
    assert _should_run_shared_ingestion(mk(True, "ingestion")) is True
    assert _should_run_shared_ingestion(mk(True, "shared_ingestion")) is True
    
    # Test case sensitivity
    assert _should_run_shared_ingestion(mk(True, "INGEST")) is True
    assert _should_run_shared_ingestion(mk(True, "  ingest  ")) is True

if __name__ == "__main__":
    # Simple test runner if pytest is not available
    print("Running slug and brief tests...")
    
    test_safe_slug_from_script_basic()
    test_safe_slug_from_script_edge_cases()
    test_brief_normalization()
    test_should_run_shared_ingestion_logic()
    
    print("All tests passed!")
