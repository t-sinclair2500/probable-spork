#!/usr/bin/env python3
"""
Enhanced SEO module for comprehensive metadata generation and optimization.
Provides advanced meta tags, schema.org markup, and content analysis.
"""
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import quote

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, slugify

log = get_logger("seo_enhancer")


@dataclass
class SEOMetadata:
    """Comprehensive SEO metadata for content."""
    # Basic metadata
    title: str
    description: str
    slug: str
    url: str
    canonical_url: str
    
    # Content metadata
    reading_time_minutes: int
    word_count: int
    language: str = "en"
    
    # Author and publication
    author_name: str = "Editor"
    author_url: str = ""
    published_date: str = ""
    modified_date: str = ""
    
    # Image metadata
    featured_image_url: str = ""
    featured_image_alt: str = ""
    featured_image_width: int = 0
    featured_image_height: int = 0
    
    # Social metadata
    twitter_card: str = "summary_large_image"
    twitter_site: str = ""
    twitter_creator: str = ""
    
    # Content analysis
    keywords: List[str] = None
    tags: List[str] = None
    category: str = ""
    
    # Quality indicators
    fact_check_score: Optional[float] = None
    content_quality_score: Optional[float] = None
    
    # Technical SEO
    breadcrumbs: List[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.tags is None:
            self.tags = []
        if self.breadcrumbs is None:
            self.breadcrumbs = []


class SEOEnhancer:
    """Enhanced SEO metadata generation and optimization."""
    
    def __init__(self, site_config: Dict[str, Any] = None):
        self.site_config = site_config or {}
        
        # Default configuration
        self.default_config = {
            "site_name": "AI Content Pipeline",
            "site_url": "https://example.com",
            "twitter_site": "@example",
            "twitter_creator": "@example",
            "author_name": "AI Editor",
            "author_url": "https://example.com/about",
            "default_image": "https://example.com/images/default-og.jpg",
            "image_width": 1200,
            "image_height": 630,
            "organization_name": "AI Content Pipeline",
            "organization_logo": "https://example.com/images/logo.png"
        }
        
        # Merge configurations
        self.config = {**self.default_config, **self.site_config}
    
    def extract_keywords(self, content: str, max_keywords: int = 10) -> List[str]:
        """Extract relevant keywords from content."""
        # Remove markdown formatting
        clean_content = re.sub(r'[#*_`\[\]()]+', ' ', content)
        clean_content = re.sub(r'https?://\S+', '', clean_content)  # Remove URLs
        
        # Extract words (3+ characters, alphabetic)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', clean_content.lower())
        
        # Common stop words to filter out
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 
            'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 
            'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 
            'did', 'has', 'let', 'put', 'say', 'she', 'too', 'use', 'this', 'that',
            'with', 'have', 'from', 'they', 'know', 'want', 'been', 'good', 'much',
            'some', 'time', 'very', 'when', 'come', 'here', 'just', 'like', 'long',
            'make', 'many', 'over', 'such', 'take', 'than', 'them', 'well', 'were'
        }
        
        # Filter and count
        filtered_words = [w for w in words if w not in stop_words and len(w) > 3]
        word_freq = {}
        for word in filtered_words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort by frequency and return top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:max_keywords] if freq > 1]
    
    def calculate_reading_time(self, content: str) -> int:
        """Calculate estimated reading time in minutes."""
        # Remove markdown and count words
        clean_content = re.sub(r'[#*_`\[\]()]+', ' ', content)
        words = re.findall(r'\b\w+\b', clean_content)
        word_count = len(words)
        
        # Average reading speed: 200 words per minute
        reading_time = max(1, round(word_count / 200))
        return reading_time
    
    def generate_meta_description(self, content: str, max_length: int = 160) -> str:
        """Generate optimized meta description from content."""
        # Extract first paragraph or meaningful content
        paragraphs = content.split('\n\n')
        
        # Skip title and empty paragraphs
        meaningful_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para and not para.startswith('#') and len(para) > 50:
                # Clean markdown formatting
                clean_para = re.sub(r'[#*_`\[\]()]+', '', para)
                clean_para = re.sub(r'\s+', ' ', clean_para).strip()
                meaningful_paragraphs.append(clean_para)
        
        if not meaningful_paragraphs:
            return "Discover insights and practical tips in this comprehensive guide."
        
        # Use first meaningful paragraph
        description = meaningful_paragraphs[0]
        
        # Truncate to max length with proper word boundaries
        if len(description) > max_length:
            truncated = description[:max_length]
            last_space = truncated.rfind(' ')
            if last_space > max_length * 0.8:  # If we can find a good break point
                description = truncated[:last_space] + "..."
            else:
                description = truncated[:-3] + "..."
        
        return description
    
    def find_featured_image(self, post_metadata: Dict[str, Any]) -> Tuple[str, str, int, int]:
        """Find the best featured image for the post."""
        # Check for explicitly set featured image
        if post_metadata.get("featured_image"):
            img_info = post_metadata["featured_image"]
            if isinstance(img_info, dict):
                return (
                    img_info.get("url", ""),
                    img_info.get("alt", ""),
                    img_info.get("width", self.config["image_width"]),
                    img_info.get("height", self.config["image_height"])
                )
        
        # Look for assets in validation metadata
        validation = post_metadata.get("validation", {})
        fact_check = validation.get("fact_check", {})
        
        # Try to find assets folder based on slug
        slug = post_metadata.get("slug", "")
        if slug:
            # Look for latest assets with this slug pattern
            assets_base = os.path.join(BASE, "assets")
            if os.path.exists(assets_base):
                candidates = []
                for folder in os.listdir(assets_base):
                    if slug in folder and os.path.isdir(os.path.join(assets_base, folder)):
                        candidates.append(folder)
                
                if candidates:
                    # Use most recent folder
                    latest_folder = sorted(candidates, reverse=True)[0]
                    folder_path = os.path.join(assets_base, latest_folder)
                    
                    # Find first suitable image
                    for file in os.listdir(folder_path):
                        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                            img_url = f"{self.config['site_url']}/assets/{latest_folder}/{file}"
                            alt_text = file.replace('_', ' ').replace('-', ' ').split('.')[0].title()
                            return img_url, alt_text, self.config["image_width"], self.config["image_height"]
        
        # Fallback to default image
        return (
            self.config["default_image"],
            f"Featured image for {post_metadata.get('title', 'this article')}",
            self.config["image_width"],
            self.config["image_height"]
        )
    
    def generate_breadcrumbs(self, post_metadata: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate breadcrumb navigation."""
        breadcrumbs = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": self.config["site_url"]}
        ]
        
        category = post_metadata.get("category", "Content")
        if category:
            breadcrumbs.append({
                "@type": "ListItem", 
                "position": 2, 
                "name": category,
                "item": f"{self.config['site_url']}/category/{slugify(category)}"
            })
        
        title = post_metadata.get("title", "Post")
        url = post_metadata.get("url", "")
        breadcrumbs.append({
            "@type": "ListItem",
            "position": len(breadcrumbs) + 1,
            "name": title,
            "item": url
        })
        
        return breadcrumbs
    
    def analyze_content_quality(self, content: str, post_metadata: Dict[str, Any]) -> Dict[str, float]:
        """Analyze content quality for SEO scoring."""
        quality_scores = {}
        
        # Reading level analysis (simple)
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if sentences:
            words = re.findall(r'\b\w+\b', content)
            avg_sentence_length = len(words) / len(sentences)
            
            # Score based on readability (shorter sentences = more readable)
            if avg_sentence_length <= 15:
                quality_scores['readability'] = 100
            elif avg_sentence_length <= 20:
                quality_scores['readability'] = 80
            elif avg_sentence_length <= 25:
                quality_scores['readability'] = 60
            else:
                quality_scores['readability'] = 40
        else:
            quality_scores['readability'] = 50
        
        # Content structure analysis
        structure_score = 0
        
        # Check for headings
        h2_count = len(re.findall(r'^#{2}\s+', content, re.MULTILINE))
        h3_count = len(re.findall(r'^#{3}\s+', content, re.MULTILINE))
        
        if h2_count >= 2:
            structure_score += 30
        if h3_count >= 1:
            structure_score += 20
        
        # Check for lists
        list_count = len(re.findall(r'^\s*[-*+]\s+', content, re.MULTILINE))
        if list_count >= 3:
            structure_score += 25
        
        # Check for links
        link_count = len(re.findall(r'\[([^\]]+)\]\([^)]+\)', content))
        if link_count >= 2:
            structure_score += 25
        
        quality_scores['structure'] = min(100, structure_score)
        
        # Keyword density analysis
        keywords = self.extract_keywords(content, 5)
        if keywords:
            # Check if keywords appear in title
            title = post_metadata.get("title", "").lower()
            keyword_in_title = any(kw in title for kw in keywords)
            quality_scores['keyword_optimization'] = 90 if keyword_in_title else 60
        else:
            quality_scores['keyword_optimization'] = 50
        
        # Overall content quality
        overall = sum(quality_scores.values()) / len(quality_scores)
        quality_scores['overall'] = overall
        
        return quality_scores
    
    def generate_seo_metadata(self, content: str, post_metadata: Dict[str, Any]) -> SEOMetadata:
        """Generate comprehensive SEO metadata."""
        # Basic information
        title = post_metadata.get("title", "Untitled Post")
        slug = post_metadata.get("slug", slugify(title))
        base_url = self.config["site_url"].rstrip('/')
        post_url = f"{base_url}/posts/{slug}"
        
        # Generate description
        description = self.generate_meta_description(content)
        
        # Content analysis
        reading_time = self.calculate_reading_time(content)
        word_count = len(re.findall(r'\b\w+\b', content))
        keywords = self.extract_keywords(content)
        
        # Featured image
        img_url, img_alt, img_width, img_height = self.find_featured_image(post_metadata)
        
        # Dates
        current_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        published_date = post_metadata.get("published_at", current_time)
        modified_date = post_metadata.get("modified_at", current_time)
        
        # Quality metrics
        quality_analysis = self.analyze_content_quality(content, post_metadata)
        
        # Validation data
        validation = post_metadata.get("validation", {})
        fact_check = validation.get("fact_check", {})
        fact_check_score = None
        if fact_check:
            issues = fact_check.get("issues", [])
            if not issues:
                fact_check_score = 100.0
            else:
                error_count = sum(1 for issue in issues if issue.get("severity") == "error")
                warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
                fact_check_score = max(0, 100 - (error_count * 20) - (warning_count * 10))
        
        # Create SEO metadata
        seo_metadata = SEOMetadata(
            title=title,
            description=description,
            slug=slug,
            url=post_url,
            canonical_url=post_url,
            reading_time_minutes=reading_time,
            word_count=word_count,
            author_name=self.config["author_name"],
            author_url=self.config["author_url"],
            published_date=published_date,
            modified_date=modified_date,
            featured_image_url=img_url,
            featured_image_alt=img_alt,
            featured_image_width=img_width,
            featured_image_height=img_height,
            twitter_site=self.config["twitter_site"],
            twitter_creator=self.config["twitter_creator"],
            keywords=keywords,
            tags=post_metadata.get("tags", []),
            category=post_metadata.get("category", "AI Tools"),
            fact_check_score=fact_check_score,
            content_quality_score=quality_analysis.get("overall"),
            breadcrumbs=self.generate_breadcrumbs(post_metadata)
        )
        
        return seo_metadata
    
    def generate_html_head(self, seo_metadata: SEOMetadata) -> str:
        """Generate comprehensive HTML head section with all meta tags."""
        head_parts = []
        
        # Basic meta tags
        head_parts.append('<meta charset="utf-8">')
        head_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
        head_parts.append(f'<title>{seo_metadata.title}</title>')
        head_parts.append(f'<meta name="description" content="{seo_metadata.description}">')
        head_parts.append(f'<link rel="canonical" href="{seo_metadata.canonical_url}">')
        
        # Keywords (if any)
        if seo_metadata.keywords:
            keywords_str = ", ".join(seo_metadata.keywords[:10])
            head_parts.append(f'<meta name="keywords" content="{keywords_str}">')
        
        # Author information
        head_parts.append(f'<meta name="author" content="{seo_metadata.author_name}">')
        
        # Open Graph meta tags
        head_parts.append('<meta property="og:type" content="article">')
        head_parts.append(f'<meta property="og:title" content="{seo_metadata.title}">')
        head_parts.append(f'<meta property="og:description" content="{seo_metadata.description}">')
        head_parts.append(f'<meta property="og:url" content="{seo_metadata.url}">')
        head_parts.append(f'<meta property="og:site_name" content="{self.config["site_name"]}">')
        
        if seo_metadata.featured_image_url:
            head_parts.append(f'<meta property="og:image" content="{seo_metadata.featured_image_url}">')
            head_parts.append(f'<meta property="og:image:alt" content="{seo_metadata.featured_image_alt}">')
            head_parts.append(f'<meta property="og:image:width" content="{seo_metadata.featured_image_width}">')
            head_parts.append(f'<meta property="og:image:height" content="{seo_metadata.featured_image_height}">')
        
        # Article-specific Open Graph
        head_parts.append(f'<meta property="article:published_time" content="{seo_metadata.published_date}">')
        head_parts.append(f'<meta property="article:modified_time" content="{seo_metadata.modified_date}">')
        head_parts.append(f'<meta property="article:author" content="{seo_metadata.author_name}">')
        
        if seo_metadata.tags:
            for tag in seo_metadata.tags[:5]:  # Limit to 5 tags
                head_parts.append(f'<meta property="article:tag" content="{tag}">')
        
        # Twitter Card meta tags
        head_parts.append(f'<meta name="twitter:card" content="{seo_metadata.twitter_card}">')
        if seo_metadata.twitter_site:
            head_parts.append(f'<meta name="twitter:site" content="{seo_metadata.twitter_site}">')
        if seo_metadata.twitter_creator:
            head_parts.append(f'<meta name="twitter:creator" content="{seo_metadata.twitter_creator}">')
        head_parts.append(f'<meta name="twitter:title" content="{seo_metadata.title}">')
        head_parts.append(f'<meta name="twitter:description" content="{seo_metadata.description}">')
        
        if seo_metadata.featured_image_url:
            head_parts.append(f'<meta name="twitter:image" content="{seo_metadata.featured_image_url}">')
            head_parts.append(f'<meta name="twitter:image:alt" content="{seo_metadata.featured_image_alt}">')
        
        # Additional meta tags for reading time
        head_parts.append(f'<meta name="reading-time" content="{seo_metadata.reading_time_minutes}">')
        head_parts.append(f'<meta name="word-count" content="{seo_metadata.word_count}">')
        
        return '\n'.join(head_parts)
    
    def generate_schema_markup(self, seo_metadata: SEOMetadata) -> str:
        """Generate comprehensive schema.org JSON-LD markup."""
        # Main article schema
        article_schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": seo_metadata.title,
            "description": seo_metadata.description,
            "author": {
                "@type": "Person",
                "name": seo_metadata.author_name,
                "url": seo_metadata.author_url if seo_metadata.author_url else None
            },
            "publisher": {
                "@type": "Organization",
                "name": self.config["organization_name"],
                "logo": {
                    "@type": "ImageObject",
                    "url": self.config["organization_logo"]
                }
            },
            "datePublished": seo_metadata.published_date,
            "dateModified": seo_metadata.modified_date,
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": seo_metadata.url
            },
            "url": seo_metadata.url,
            "wordCount": seo_metadata.word_count,
            "keywords": seo_metadata.keywords
        }
        
        # Add image if available
        if seo_metadata.featured_image_url:
            article_schema["image"] = {
                "@type": "ImageObject",
                "url": seo_metadata.featured_image_url,
                "width": seo_metadata.featured_image_width,
                "height": seo_metadata.featured_image_height,
                "caption": seo_metadata.featured_image_alt
            }
        
        # Add category if available
        if seo_metadata.category:
            article_schema["genre"] = seo_metadata.category
        
        # Add reading time
        article_schema["timeRequired"] = f"PT{seo_metadata.reading_time_minutes}M"
        
        # Breadcrumb schema
        breadcrumb_schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": seo_metadata.breadcrumbs
        }
        
        # Combine schemas
        schemas = [article_schema, breadcrumb_schema]
        
        # Add quality indicators if available
        if seo_metadata.fact_check_score is not None:
            # Add credibility indicator
            article_schema["creditText"] = f"Fact-check score: {seo_metadata.fact_check_score:.1f}/100"
        
        return json.dumps(schemas, indent=2)


def main():
    """CLI interface for SEO enhancement testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate enhanced SEO metadata")
    parser.add_argument("content_file", help="Markdown content file")
    parser.add_argument("--metadata", help="Post metadata JSON file")
    parser.add_argument("--output", help="Output HTML file")
    parser.add_argument("--config", help="SEO configuration JSON file")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.content_file):
        print(f"Error: Content file not found: {args.content_file}")
        return 1
    
    # Load content
    with open(args.content_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Load metadata
    metadata = {}
    if args.metadata and os.path.exists(args.metadata):
        with open(args.metadata, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    
    # Load config
    config = {}
    if args.config and os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
    
    # Generate SEO
    enhancer = SEOEnhancer(config)
    seo_metadata = enhancer.generate_seo_metadata(content, metadata)
    
    # Display results
    print(f"\nSEO Analysis for: {seo_metadata.title}")
    print(f"  Description: {seo_metadata.description[:100]}...")
    print(f"  Reading Time: {seo_metadata.reading_time_minutes} minutes")
    print(f"  Word Count: {seo_metadata.word_count}")
    print(f"  Keywords: {', '.join(seo_metadata.keywords[:5])}")
    
    if seo_metadata.fact_check_score is not None:
        print(f"  Fact-check Score: {seo_metadata.fact_check_score:.1f}/100")
    
    if seo_metadata.content_quality_score is not None:
        print(f"  Content Quality: {seo_metadata.content_quality_score:.1f}/100")
    
    # Generate HTML if requested
    if args.output:
        html_head = enhancer.generate_html_head(seo_metadata)
        schema_markup = enhancer.generate_schema_markup(seo_metadata)
        
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
{html_head}
<script type="application/ld+json">
{schema_markup}
</script>
</head>
<body>
<article>
<!-- Content would be inserted here -->
<h1>{seo_metadata.title}</h1>
<p>Reading time: {seo_metadata.reading_time_minutes} minutes</p>
<div>Content goes here...</div>
</article>
</body>
</html>"""
        
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"\nEnhanced HTML saved to {args.output}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
