#!/usr/bin/env python3
"""
Local Blog Staging Script

Exports blog-ready content under exports/blog/YYYYMMDD_slug/ with:
- post.html (sanitized, SEO linted)
- post.md 
- post.meta.json (WordPress-ready metadata)
- schema.json (Article JSON-LD)
- assets/ (copied media files)
- credits.json (license info)
- wp_rest_payload.json (future POST body)
- Optional: YYYYMMDD_slug.zip bundle
"""

import json
import os
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path

# Ensure repo root on path
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, guard_system, load_config, log_state, single_lock, load_env
from bin.seo_lint import lint as seo_lint

log = get_logger("blog_stage_local")


def load_blog_cfg():
    """Load blog configuration with fallback to example"""
    p = os.path.join(BASE, "conf", "blog.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "blog.example.yaml")
    
    import yaml
    return yaml.safe_load(open(p, "r", encoding="utf-8"))


def sanitize_html_content(html_content):
    """Basic HTML sanitization and alt text validation"""
    # Check for images without alt text
    import re
    
    img_pattern = r'<img[^>]*>'
    images = re.findall(img_pattern, html_content, re.IGNORECASE)
    
    for img in images:
        if 'alt=' not in img.lower():
            # Add generic alt text for images missing it
            img_src = re.search(r'src=["\']([^"\']*)["\']', img, re.IGNORECASE)
            if img_src:
                filename = os.path.basename(img_src.group(1))
                alt_text = os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ')
                new_img = img.replace('>', f' alt="{alt_text}">')
                html_content = html_content.replace(img, new_img)
    
    return html_content


def extract_schema_from_html(html_content, metadata):
    """Extract or generate schema.org JSON-LD data"""
    import re
    
    # Try to extract existing JSON-LD
    json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
    match = re.search(json_ld_pattern, html_content, re.DOTALL)
    
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Generate basic Article schema
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": metadata.get("title", ""),
        "description": metadata.get("description", ""),
        "datePublished": metadata.get("generated_at", datetime.utcnow().isoformat() + "Z"),
        "author": {
            "@type": "Person",
            "name": "AI Pipeline"
        },
        "publisher": {
            "@type": "Organization", 
            "name": "Content Pipeline"
        }
    }
    
    if metadata.get("tags"):
        schema["keywords"] = metadata["tags"]
    
    return schema


def copy_assets(source_slug, export_dir):
    """Copy assets and return list of copied files"""
    assets_source = os.path.join(BASE, "assets", source_slug)
    assets_dest = os.path.join(export_dir, "assets")
    
    copied_files = []
    
    if not os.path.exists(assets_source):
        log.warning(f"Assets directory not found: {assets_source}")
        return copied_files
    
    os.makedirs(assets_dest, exist_ok=True)
    
    for item in os.listdir(assets_source):
        source_path = os.path.join(assets_source, item)
        dest_path = os.path.join(assets_dest, item)
        
        if os.path.isfile(source_path):
            shutil.copy2(source_path, dest_path)
            copied_files.append(item)
            log.debug(f"Copied asset: {item}")
    
    return copied_files


def aggregate_license_info(source_slug):
    """Aggregate license information from assets directory"""
    license_file = os.path.join(BASE, "assets", source_slug, "license.json")
    sources_file = os.path.join(BASE, "assets", source_slug, "sources_used.txt")
    
    credits = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "licenses": [],
        "sources": [],
        "attribution_required": False
    }
    
    # Load license.json if it exists
    if os.path.exists(license_file):
        try:
            with open(license_file, 'r', encoding='utf-8') as f:
                license_data = json.load(f)
                if isinstance(license_data, list):
                    credits["licenses"] = license_data
                else:
                    credits["licenses"] = [license_data]
                
                # Check if any license requires attribution
                for license_item in credits["licenses"]:
                    if license_item.get("license", "").lower() in ["attribution required", "cc by"]:
                        credits["attribution_required"] = True
        except (json.JSONDecodeError, FileNotFoundError):
            log.warning(f"Could not load license.json from {license_file}")
    
    # Load sources_used.txt if it exists  
    if os.path.exists(sources_file):
        try:
            with open(sources_file, 'r', encoding='utf-8') as f:
                sources = [line.strip() for line in f.readlines() if line.strip()]
                credits["sources"] = sources
        except FileNotFoundError:
            log.warning(f"Could not load sources_used.txt from {sources_file}")
    
    return credits


def generate_wp_rest_payload(metadata, html_content, credits):
    """Generate WordPress REST API payload structure"""
    
    # Extract title from metadata or HTML
    title = metadata.get("title", "Untitled Post")
    
    # Generate excerpt from description or first paragraph
    excerpt = metadata.get("description", "")
    if not excerpt and html_content:
        import re
        # Try to extract first paragraph
        p_match = re.search(r'<p[^>]*>(.*?)</p>', html_content, re.DOTALL)
        if p_match:
            # Strip HTML tags for excerpt
            excerpt = re.sub(r'<[^>]+>', '', p_match.group(1))[:160]
    
    payload = {
        "title": title,
        "content": html_content,
        "excerpt": excerpt,
        "status": "draft",  # Safe default
        "slug": metadata.get("slug", ""),
        "categories": [],  # Will be populated based on config
        "tags": metadata.get("tags", []),
        "meta": {
            "generated_by": "blog_stage_local",
            "generated_at": metadata.get("generated_at", ""),
            "validation": metadata.get("validation", {}),
            "attribution_required": credits.get("attribution_required", False)
        },
        "featured_media": None  # Placeholder - will be set during actual upload
    }
    
    return payload


def create_zip_bundle(export_dir):
    """Create optional zip bundle of the export directory"""
    zip_path = export_dir + ".zip"
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(export_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, export_dir)
                    zipf.write(file_path, arcname)
        
        log.info(f"Created zip bundle: {zip_path}")
        return zip_path
    except Exception as e:
        log.error(f"Failed to create zip bundle: {e}")
        return None


def main(brief=None):
    """Main function for local blog staging with optional brief context"""
    cfg = load_config()
    guard_system(cfg)
    env = load_env()
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("blog_stage_local", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")
    else:
        log_state("blog_stage_local", "START", "brief=none")
        log.info("Running without brief - using default behavior")
    
    blog_cfg = load_blog_cfg()
    staging_root = blog_cfg.get("wordpress", {}).get("staging_root", "exports/blog")
    
    # Check for required input files
    cache_dir = os.path.join(BASE, "data", "cache")
    post_html = os.path.join(cache_dir, "post.html")
    post_md = os.path.join(cache_dir, "post.md") 
    post_meta = os.path.join(cache_dir, "post.meta.json")
    
    missing_files = []
    for file_path in [post_html, post_md, post_meta]:
        if not os.path.exists(file_path):
            missing_files.append(os.path.basename(file_path))
    
    if missing_files:
        log_state("blog_stage_local", "SKIP", f"missing: {', '.join(missing_files)}")
        return
    
    # Load metadata and content
    try:
        with open(post_meta, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        with open(post_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        with open(post_md, 'r', encoding='utf-8') as f:
            md_content = f.read()
            
    except Exception as e:
        log_state("blog_stage_local", "FAIL", f"read_error: {e}")
        return
    
    # Generate export directory name
    date_tag = datetime.now().strftime("%Y%m%d")
    slug = metadata.get("slug", "untitled-post")
    export_name = f"{date_tag}_{slug}"
    export_dir = os.path.join(BASE, staging_root, export_name)
    
    # Check if export already exists (idempotency)
    if os.path.exists(export_dir):
        log.info(f"Export already exists: {export_dir}")
        log_state("blog_stage_local", "OK", f"exists: {export_name}")
        return
    
    # Create export directory
    os.makedirs(export_dir, exist_ok=True)
    log.info(f"Creating blog export: {export_dir}")
    
    try:
        # 1. Sanitize HTML and ensure alt text
        sanitized_html = sanitize_html_content(html_content)
        
        # 2. Run SEO lint validation
        title = metadata.get("title", "")
        description = metadata.get("description", "")
        seo_issues = seo_lint(title, description)
        if seo_issues:
            log.warning(f"SEO validation issues: {seo_issues}")
        
        # Apply brief-specific validation if available
        if brief:
            brief_validation_issues = []
            
            # Check if content length matches brief target
            target_length = brief.get('target_len_sec')
            if target_length:
                # Estimate content length (rough approximation)
                word_count = len(md_content.split())
                estimated_seconds = word_count / 150  # Assume ~150 WPM reading speed
                
                if abs(estimated_seconds - target_length) > target_length * 0.2:  # 20% tolerance
                    brief_validation_issues.append(f"Content length ({estimated_seconds:.1f}s) differs from brief target ({target_length}s)")
            
            # Check if brief keywords are present in content
            include_keywords = brief.get('keywords_include', [])
            if include_keywords:
                content_lower = md_content.lower()
                missing_keywords = [kw for kw in include_keywords if kw.lower() not in content_lower]
                if missing_keywords:
                    brief_validation_issues.append(f"Missing brief keywords: {', '.join(missing_keywords)}")
            
            # Log brief validation results
            if brief_validation_issues:
                log.warning(f"Brief validation issues: {brief_validation_issues}")
            else:
                log.info("Brief validation passed")
        
        # 3. Generate schema.org JSON-LD
        schema_data = extract_schema_from_html(sanitized_html, metadata)
        
        # 4. Copy assets
        source_slug = None
        # Try to determine source slug from existing script files
        scripts_dir = os.path.join(BASE, "scripts")
        if os.path.exists(scripts_dir):
            script_files = [f for f in os.listdir(scripts_dir) if f.endswith('.txt')]
            if script_files:
                # Use the most recent script file
                script_files.sort(reverse=True)
                source_slug = script_files[0].replace('.txt', '')
        
        copied_assets = []
        if source_slug:
            copied_assets = copy_assets(source_slug, export_dir)
        
        # 5. Aggregate license information
        credits = aggregate_license_info(source_slug) if source_slug else {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "licenses": [],
            "sources": [],
            "attribution_required": False
        }
        
        # 6. Generate WordPress REST payload
        wp_payload = generate_wp_rest_payload(metadata, sanitized_html, credits)
        
        # 7. Write all output files
        files_written = []
        
        # Write HTML
        html_path = os.path.join(export_dir, "post.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(sanitized_html)
        files_written.append("post.html")
        
        # Write Markdown
        md_path = os.path.join(export_dir, "post.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        files_written.append("post.md")
        
        # Write metadata
        meta_path = os.path.join(export_dir, "post.meta.json")
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        files_written.append("post.meta.json")
        
        # Write schema
        schema_path = os.path.join(export_dir, "schema.json")
        with open(schema_path, 'w', encoding='utf-8') as f:
            json.dump(schema_data, f, indent=2)
        files_written.append("schema.json")
        
        # Write credits
        credits_path = os.path.join(export_dir, "credits.json")
        with open(credits_path, 'w', encoding='utf-8') as f:
            json.dump(credits, f, indent=2)
        files_written.append("credits.json")
        
        # Write WordPress payload
        wp_path = os.path.join(export_dir, "wp_rest_payload.json")
        with open(wp_path, 'w', encoding='utf-8') as f:
            json.dump(wp_payload, f, indent=2)
        files_written.append("wp_rest_payload.json")
        
        # 8. Create optional zip bundle
        zip_path = create_zip_bundle(export_dir)
        
        # Log success
        notes = f"files={len(files_written)}, assets={len(copied_assets)}"
        if zip_path:
            notes += f", zip=true"
        
        log_state("blog_stage_local", "OK", notes)
        log.info(f"Blog staging completed: {export_dir}")
        log.info(f"Files written: {', '.join(files_written)}")
        if copied_assets:
            log.info(f"Assets copied: {len(copied_assets)} files")
        
    except Exception as e:
        log_state("blog_stage_local", "FAIL", str(e))
        log.error(f"Blog staging failed: {e}")
        # Clean up partial export on failure
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir, ignore_errors=True)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Blog local staging")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
            log.info(f"Loaded brief: {brief.get('title', 'Untitled')}")
        except (json.JSONDecodeError, TypeError) as e:
            log.warning(f"Failed to parse brief data: {e}")
    
    with single_lock():
        main(brief)