"""
Tests for the brief loader module.
"""

import os
import tempfile
import pytest
import yaml
from unittest.mock import patch

# Ensure repo root is on sys.path
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.brief_loader import (
    load_brief,
    from_markdown_front_matter,
    validate_brief,
    create_brief_template,
    get_brief_path
)


class TestBriefLoader:
    """Test the brief loader functionality."""
    
    def test_validate_brief_with_complete_data(self):
        """Test validation with complete brief data."""
        brief = {
            "title": "Test Title",
            "audience": ["test audience"],
            "tone": "test tone",
            "video": {"target_length_min": 3, "target_length_max": 5},
    
            "keywords_include": ["keyword1", "keyword2"],
            "keywords_exclude": ["avoid1", "avoid2"],
            "sources_preferred": ["source1", "source2"],
            "monetization": {"primary": ["test"], "cta_text": "Test CTA"},
            "notes": "Test notes"
        }
        
        result = validate_brief(brief)
        
        assert result["title"] == "Test Title"
        assert result["audience"] == ["test audience"]
        assert result["tone"] == "test tone"
        assert result["video"]["target_length_min"] == 3
        assert result["video"]["target_length_max"] == 5
        
        assert result["keywords_include"] == ["keyword1", "keyword2"]
        assert result["keywords_exclude"] == ["avoid1", "avoid2"]
        assert result["sources_preferred"] == ["source1", "source2"]
        assert result["monetization"]["primary"] == ["test"]
        assert result["monetization"]["cta_text"] == "Test CTA"
        assert result["notes"] == "Test notes"
    
    def test_validate_brief_with_defaults(self):
        """Test validation applies defaults for missing fields."""
        brief = {"title": "Test Title"}
        
        result = validate_brief(brief)
        
        assert result["title"] == "Test Title"
        assert result["audience"] == []
        assert result["tone"] == "informative"
        assert result["video"]["target_length_min"] == 5
        assert result["video"]["target_length_max"] == 7
        
        assert result["keywords_include"] == []
        assert result["keywords_exclude"] == []
        assert result["sources_preferred"] == []
        assert result["monetization"]["primary"] == ["lead_magnet", "email_capture"]
        assert result["monetization"]["cta_text"] == "Download our free guide"
        assert result["notes"] == ""
    
    def test_validate_brief_normalizes_keywords(self):
        """Test that keywords are normalized (lowercase, stripped)."""
        brief = {
            "keywords_include": ["  KEYWORD1  ", "Keyword2", "  KEYWORD3  "],
            "keywords_exclude": ["  AVOID1  ", "Avoid2"]
        }
        
        result = validate_brief(brief)
        
        assert result["keywords_include"] == ["keyword1", "keyword2", "keyword3"]
        assert result["keywords_exclude"] == ["avoid1", "avoid2"]
    
    def test_validate_brief_handles_string_audience(self):
        """Test that string audience is converted to list."""
        brief = {"audience": "single audience"}
        
        result = validate_brief(brief)
        
        assert result["audience"] == ["single audience"]
    
    def test_validate_brief_handles_invalid_types(self):
        """Test that invalid types are handled gracefully."""
        brief = {
            "audience": None,
            "keywords_include": "not a list",
            "video": "not a dict",
            "notes": None
        }
        
        result = validate_brief(brief)
        
        assert result["audience"] == []
        assert result["keywords_include"] == ["not a list"]  # String gets converted to list
        assert isinstance(result["video"], dict)
        assert result["notes"] == ""


class TestMarkdownFrontMatter:
    """Test Markdown front-matter parsing."""
    
    def test_from_markdown_front_matter_with_front_matter(self):
        """Test parsing Markdown with YAML front-matter."""
        content = """---
title: Test Title
audience: ["test"]
---
# Content here
This is the body content."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            
            try:
                result = from_markdown_front_matter(f.name)
                
                assert result["title"] == "Test Title"
                assert result["audience"] == ["test"]
                assert "Content here" in result["notes"]
                assert "This is the body content" in result["notes"]
            finally:
                os.unlink(f.name)
    
    def test_from_markdown_front_matter_without_front_matter(self):
        """Test parsing Markdown without front-matter."""
        content = """# No front-matter
This is just content."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            
            try:
                result = from_markdown_front_matter(f.name)
                
                assert result["notes"] == content
            finally:
                os.unlink(f.name)
    
    def test_from_markdown_front_matter_invalid_yaml(self):
        """Test handling of invalid YAML in front-matter."""
        content = """---
title: "Unclosed quote
---
Content here"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            
            try:
                with pytest.raises(yaml.YAMLError):
                    from_markdown_front_matter(f.name)
            finally:
                os.unlink(f.name)


class TestBriefTemplate:
    """Test brief template creation."""
    
    def test_create_brief_template(self):
        """Test creating a brief template."""
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = os.path.join(temp_dir, "brief.yaml")
            
            result_path = create_brief_template(template_path)
            
            assert result_path == template_path
            assert os.path.exists(template_path)
            
            # Verify template content
            with open(template_path, 'r') as f:
                template = yaml.safe_load(f)
            
            assert template["title"] == "Local SEO for Dentists"
            assert "practice owners" in template["audience"]
            assert template["tone"] == "confident, practical"
            assert template["video"]["target_length_min"] == 5
            assert template["video"]["target_length_max"] == 7


class TestBriefPath:
    """Test brief path detection."""
    
    @patch('os.path.exists')
    def test_get_brief_path_yaml_exists(self, mock_exists):
        """Test path detection when YAML exists."""
        mock_exists.side_effect = lambda path: "brief.yaml" in path
        
        path = get_brief_path()
        
        assert "brief.yaml" in path
    
    @patch('os.path.exists')
    def test_get_brief_path_md_exists(self, mock_exists):
        """Test path detection when only Markdown exists."""
        mock_exists.side_effect = lambda path: "brief.md" in path
        
        path = get_brief_path()
        
        assert "brief.md" in path
    
    @patch('os.path.exists')
    def test_get_brief_path_none_exist(self, mock_exists):
        """Test path detection when no brief files exist."""
        mock_exists.return_value = False
        
        path = get_brief_path()
        
        assert path is None


if __name__ == "__main__":
    pytest.main([__file__])
