#!/usr/bin/env python3
"""
Example usage of the Workstream Brief Loader.

This script demonstrates how to integrate the brief loader
into your pipeline scripts.
"""

import sys
import os

# Add the bin directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from brief_loader import load_brief
from core import load_config, load_brief as core_load_brief


def main():
    """Demonstrate brief loader usage."""
    print("=== Workstream Brief Loader Example ===\n")
    
    # Method 1: Direct import from brief_loader
    print("1. Loading brief directly:")
    try:
        brief = load_brief()
        print(f"   Title: {brief['title']}")
        print(f"   Audience: {', '.join(brief['audience'])}")
        print(f"   Tone: {brief['tone']}")
        print(f"   Video target: {brief['video']['target_length_min']}-{brief['video']['target_length_max']} minutes")
        print(f"   Blog target: {brief['blog']['words_min']}-{brief['blog']['words_max']} words")
        print(f"   Keywords to include: {', '.join(brief['keywords_include'][:3])}...")
        print(f"   CTA: {brief['monetization']['cta_text']}")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()
    
    # Method 2: Through core module
    print("2. Loading brief through core module:")
    try:
        brief = core_load_brief()
        print(f"   Title: {brief['title']}")
        print(f"   Source: {brief.get('_source', 'core fallback')}")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()
    
    # Method 3: Show how to use brief in content generation
    print("3. Using brief for content generation:")
    try:
        brief = load_brief()
        
        # Example: Generate a content outline based on brief
        print(f"   Content Strategy for: {brief['title']}")
        print(f"   Target Audience: {', '.join(brief['audience'])}")
        print(f"   Content Tone: {brief['tone']}")
        print(f"   Primary Keywords: {', '.join(brief['keywords_include'][:5])}")
        print(f"   Avoid Keywords: {', '.join(brief['keywords_exclude'][:3])}")
        print(f"   Preferred Sources: {', '.join(brief['sources_preferred'][:3])}")
        print(f"   Monetization: {', '.join(brief['monetization']['primary'])}")
        print(f"   Call to Action: {brief['monetization']['cta_text']}")
        print()
        
        # Example: Content length planning
        video_min = brief['video']['target_length_min']
        video_max = brief['video']['target_length_max']
        blog_min = brief['blog']['words_min']
        blog_max = brief['blog']['words_max']
        
        print(f"   Content Targets:")
        print(f"     Video: {video_min}-{video_max} minutes")
        print(f"     Blog: {blog_min}-{blog_max} words")
        print()
        
        # Example: Notes and context
        if brief['notes']:
            print(f"   Additional Context:")
            print(f"     {brief['notes'][:100]}...")
            print()
            
    except Exception as e:
        print(f"   Error: {e}")
        print()
    
    print("=== End Example ===")


if __name__ == "__main__":
    main()
