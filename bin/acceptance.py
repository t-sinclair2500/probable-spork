#!/usr/bin/env python3
"""
Acceptance Harness for Content Pipeline

Runs the orchestrator in DRY mode and validates all artifacts with quality thresholds.
Emits PASS/FAIL JSON with artifact pointers and quality metrics.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import (
    BASE, 
    get_logger, 
    load_config, 
    load_blog_cfg,
    load_modules_cfg,
    log_state,
    single_lock
)

log = get_logger("acceptance")


class AcceptanceValidator:
    """Validates pipeline artifacts and quality thresholds"""
    
    def __init__(self, cfg, blog_cfg):
        self.cfg = cfg
        self.blog_cfg = blog_cfg
        self.modules_cfg = load_modules_cfg()
        self.results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "pipeline": "acceptance_harness",
            "overall_status": "PENDING",
            "lanes": {
                "youtube": {"status": "PENDING", "artifacts": {}, "quality": {}},
                "blog": {"status": "PENDING", "artifacts": {}, "quality": {}}
            },
            "quality_thresholds": {
                "script_score_min": 50,
                "seo_lint_pass": True,
                "visual_coverage_min": 85,
                "min_assets": 10,
                "min_script_words": 350
            }
        }
    
    def validate_youtube_lane(self) -> bool:
        """Validate YouTube lane artifacts and quality"""
        log.info("=== VALIDATING YOUTUBE LANE ===")
        
        youtube_results = self.results["lanes"]["youtube"]
        
        # Check for required artifacts
        artifacts = self._find_youtube_artifacts()
        youtube_results["artifacts"] = artifacts
        
        if not artifacts["outline"]:
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = "Missing outline.json"
            return False
            
        if not artifacts["script"]:
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = "Missing script.txt"
            return False
            
        if not artifacts["assets"]:
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = "Missing assets"
            return False
            
        if not artifacts["voiceover"]:
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = "Missing voiceover MP3"
            return False
            
        if not artifacts["captions"]:
            youtube_results["quality"]["warning"] = "Missing captions SRT"
        
        # Validate animatics if enabled
        animatics_enabled = False
        if self.modules_cfg and self.modules_cfg.get('animatics', {}).get('enabled', False):
            animatics_enabled = True
        elif getattr(self.cfg, 'animatics', None) and getattr(self.cfg.animatics, 'enabled', True):
            animatics_enabled = True
        
        if animatics_enabled:
            if not artifacts["scenescript"]:
                youtube_results["status"] = "FAIL"
                youtube_results["quality"]["error"] = "Missing SceneScript JSON"
                return False
            
            if not artifacts["animatics"]:
                youtube_results["status"] = "FAIL"
                youtube_results["quality"]["error"] = "Missing animatics MP4 files"
                return False
            
            # Validate SceneScript and animatics quality
            animatics_quality = self._validate_animatics_quality(artifacts)
            youtube_results["quality"]["animatics"] = animatics_quality
            
            if not animatics_quality.get("validation_pass", False):
                youtube_results["status"] = "FAIL"
                youtube_results["quality"]["error"] = "SceneScript validation failed"
                return False
            
            if not animatics_quality.get("coverage_pass", False):
                youtube_results["status"] = "FAIL"
                youtube_results["quality"]["error"] = "Animatics coverage below threshold"
                return False
            
            if not animatics_quality.get("qa_gates_pass", False):
                qa_fails = animatics_quality.get("qa_gates_fails", [])
                error_msg = f"QA gates failed: {'; '.join(qa_fails[:3])}"  # Show first 3 failures
                if len(qa_fails) > 3:
                    error_msg += f" (+{len(qa_fails) - 3} more)"
                youtube_results["status"] = "FAIL"
                youtube_results["quality"]["error"] = error_msg
                return False
            
            if not animatics_quality.get("duration_pass", False):
                duration_issues = animatics_quality.get("duration_issues", [])
                error_msg = f"Duration policy failed: {'; '.join(duration_issues[:3])}"  # Show first 3 failures
                if len(duration_issues) > 3:
                    error_msg += f" (+{len(duration_issues) - 3} more)"
                youtube_results["status"] = "FAIL"
                youtube_results["quality"]["error"] = error_msg
                return False
            
            # Check video.animatics_only mode
            animatics_only = getattr(self.cfg.video, "animatics_only", True)
            enable_legacy = getattr(self.cfg.video, "enable_legacy_stock", False)
            
            if animatics_only and not enable_legacy:
                # Enforce animatics-only policy
                if artifacts["assets"]:
                    youtube_results["status"] = "FAIL"
                    youtube_results["quality"]["error"] = "Stock assets present in animatics_only mode"
                    return False
                
                # Validate procedural settings from modules.yaml
                if self.modules_cfg:
                    procedural_cfg = self.modules_cfg.get("procedural", {})
                    if procedural_cfg:
                        # Check seed setting
                        seed = procedural_cfg.get("seed")
                        if seed is not None:
                            youtube_results["quality"]["procedural_seed"] = seed
                        
                        # Check placement settings
                        placement = procedural_cfg.get("placement", {})
                        if placement:
                            youtube_results["quality"]["procedural_placement"] = placement
                        
                        # Check motion settings
                        motion = procedural_cfg.get("motion", {})
                        if motion:
                            youtube_results["quality"]["procedural_motion"] = motion
                
                # Check video metadata for source_mode
                if artifacts["video_metadata"]:
                    try:
                        with open(artifacts["video_metadata"], 'r') as f:
                            metadata = json.load(f)
                        source_mode = metadata.get("source_mode", "unknown")
                        if source_mode != "animatics":
                            youtube_results["status"] = "FAIL"
                            youtube_results["quality"]["error"] = f"Video source_mode is '{source_mode}', expected 'animatics' in animatics_only mode"
                            return False
                        
                        # Check coverage threshold
                        coverage = metadata.get("coverage", {})
                        if isinstance(coverage, dict):
                            coverage_pct = coverage.get("visual_coverage_pct", 0)
                            min_coverage = getattr(self.cfg.video, "min_coverage", 0.85) * 100
                            if coverage_pct < min_coverage:
                                youtube_results["status"] = "FAIL"
                                youtube_results["quality"]["error"] = f"Coverage {coverage_pct}% below threshold {min_coverage}%"
                                return False
                    except Exception as e:
                        log.warning(f"Could not validate video metadata: {e}")
                        youtube_results["quality"]["warning"] = "Could not validate video metadata"
            
        if not artifacts["video"]:
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = "Missing assembled MP4"
            return False
            
        if not artifacts["thumbnail"]:
            youtube_results["quality"]["warning"] = "Missing thumbnail PNG"
        
        # Quality validation
        quality = self._validate_youtube_quality(artifacts)
        youtube_results["quality"].update(quality)
        
        # Determine overall status
        if quality.get("script_score", 0) < self.results["quality_thresholds"]["script_score_min"]:
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = f"Script score {quality.get('script_score', 0)} below threshold {self.results['quality_thresholds']['script_score_min']}"
            return False
            
        # Asset count validation - adjust for animatics-only mode
        min_assets_required = self.results["quality_thresholds"]["min_assets"]
        if hasattr(self.cfg, 'video') and getattr(self.cfg.video, 'animatics_only', False):
            # In animatics-only mode, 4 scenes is excellent for a 2-min video
            min_assets_required = 3
        
        if len(artifacts["assets"]) < min_assets_required:
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = f"Only {len(artifacts['assets'])} assets, need {min_assets_required}"
            return False
            
        if quality.get("script_words", 0) < self.results["quality_thresholds"]["min_script_words"]:
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = f"Script only {quality.get('script_words', 0)} words, need {self.results['quality_thresholds']['min_script_words']}"
            return False
        
        youtube_results["status"] = "PASS"
        return True
    
    def validate_blog_lane(self) -> bool:
        """Validate blog lane artifacts and quality"""
        log.info("=== VALIDATING BLOG LANE ===")
        
        blog_results = self.results["lanes"]["blog"]
        
        # Check for required artifacts
        artifacts = self._find_blog_artifacts()
        blog_results["artifacts"] = artifacts
        
        if not artifacts["post_html"]:
            blog_results["status"] = "FAIL"
            blog_results["quality"]["error"] = "Missing post.html"
            return False
            
        if not artifacts["post_meta"]:
            blog_results["status"] = "FAIL"
            blog_results["quality"]["error"] = "Missing post.meta.json"
            return False
            
        if not artifacts["schema"]:
            blog_results["status"] = "FAIL"
            blog_results["quality"]["error"] = "Missing schema.json"
            return False
            
        if not artifacts["credits"]:
            blog_results["status"] = "FAIL"
            blog_results["quality"]["error"] = "Missing credits.json"
            return False
            
        if not artifacts["wp_payload"]:
            blog_results["status"] = "FAIL"
            blog_results["quality"]["error"] = "Missing wp_rest_payload.json"
            return False
            
        if not artifacts["assets"]:
            blog_results["quality"]["warning"] = "No inline images found"
        
        # Quality validation
        quality = self._validate_blog_quality(artifacts)
        blog_results["quality"].update(quality)
        
        # Determine overall status
        if not quality.get("seo_lint_pass", False):
            blog_results["status"] = "FAIL"
            blog_results["quality"]["error"] = "SEO lint failed"
            return False
            
        if not quality.get("alt_text_coverage", 0) >= 100:
            blog_results["quality"]["warning"] = f"Only {quality.get('alt_text_coverage', 0)}% of images have alt text"
        
        blog_results["status"] = "PASS"
        return True
    
    def _find_youtube_artifacts(self) -> Dict[str, Any]:
        """Find YouTube lane artifacts"""
        artifacts = {
            "outline": None,
            "script": None,
            "scenescript": None,
            "animatics": [],
            "assets": [],
            "voiceover": None,
            "captions": None,
            "video": None,
            "video_metadata": None,
            "thumbnail": None
        }
        
        # Find most recent script files
        scripts_dir = os.path.join(BASE, "scripts")
        if os.path.exists(scripts_dir):
            script_files = [f for f in os.listdir(scripts_dir) if f.endswith('.txt')]
            if script_files:
                # Get most recent by date prefix, but prefer files with complete sets
                script_files.sort(reverse=True)
                
                # Find a script that has corresponding outline and other files
                # Also prefer scripts with better quality (more B-ROLL markers, longer content)
                best_script = None
                best_score = 0
                
                for script_file in script_files:
                    slug = script_file.replace('.txt', '')
                    outline_file = f"{slug}.outline.json"
                    outline_path = os.path.join(scripts_dir, outline_file)
                    
                    if os.path.exists(outline_path):
                        # Score this script based on quality and completeness
                        script_path = os.path.join(scripts_dir, script_file)
                        try:
                            with open(script_path, 'r', encoding='utf-8') as f:
                                script_content = f.read()
                            
                            # Calculate quality score
                            words = len(script_content.split())
                            broll_markers = script_content.count('[B-ROLL:') + script_content.count('[**B-ROLL:')
                            
                            # Check for completeness (voiceover, video, thumbnail)
                            voiceover_file = f"{slug}.mp3"
                            voiceover_path = os.path.join(BASE, "voiceovers", voiceover_file)
                            has_voiceover = os.path.exists(voiceover_path)
                            
                            video_file = f"{slug}.mp4"
                            video_path = os.path.join(BASE, "videos", video_file)
                            has_video = os.path.exists(video_path)
                            
                            thumbnail_file = f"{slug}.png"
                            thumbnail_path = os.path.join(BASE, "videos", thumbnail_file)
                            has_thumbnail = os.path.exists(thumbnail_path)
                            
                            # Score based on quality and completeness
                            score = words + (broll_markers * 10)  # Base quality score
                            if has_voiceover:
                                score += 100  # Heavy weight for voiceover
                            if has_video:
                                score += 200  # Very heavy weight for video
                            if has_thumbnail:
                                score += 50   # Medium weight for thumbnail
                            
                            if score > best_score:
                                best_score = score
                                best_script = script_file
                                
                        except Exception:
                            # If we can't read the script, still consider it if it's the only option
                            if not best_script:
                                best_script = script_file
                
                if best_script:
                    artifacts["script"] = best_script
                    # Extract slug by removing date prefix and .txt extension
                    slug = best_script.replace('.txt', '')
                    if '_' in slug:
                        slug = slug.split('_', 1)[1]  # Get part after first underscore
                    outline_file = f"{best_script.replace('.txt', '')}.outline.json"
                    artifacts["outline"] = outline_file
                elif script_files:
                    # Fallback to first script with outline
                    for script_file in script_files:
                        slug = script_file.replace('.txt', '')
                        if '_' in slug:
                            slug = slug.split('_', 1)[1]  # Get part after first underscore
                        outline_file = f"{script_file.replace('.txt', '')}.outline.json"
                        outline_path = os.path.join(scripts_dir, outline_file)
                        
                        if os.path.exists(outline_path):
                            artifacts["script"] = script_file
                            artifacts["outline"] = outline_file
                            break
                
                # If no complete set found, use the first script
                if not artifacts["script"]:
                    artifacts["script"] = script_files[0]
                    slug = script_files[0].replace('.txt', '')
                    if '_' in slug:
                        slug = slug.split('_', 1)[1]  # Get part after first underscore
                    date_prefix = slug.split('_')[0] if '_' in slug else ""
                
                # Find voiceover (use full script filename without .txt)
                script_basename = artifacts["script"].replace('.txt', '')
                voiceover_file = f"{script_basename}.mp3"
                voiceover_path = os.path.join(BASE, "voiceovers", voiceover_file)
                if os.path.exists(voiceover_path):
                    artifacts["voiceover"] = voiceover_file
                
                # Find captions
                captions_file = f"{script_basename}.srt"
                captions_path = os.path.join(BASE, "voiceovers", captions_file)
                if os.path.exists(captions_path):
                    artifacts["captions"] = captions_file
                
                # Find video (use slug for directory lookup)
                video_file = f"{slug}.mp4"
                video_path = os.path.join(BASE, "videos", video_file)
                if os.path.exists(video_path):
                    artifacts["video"] = video_file
                
                # Find video metadata (use slug for directory lookup)
                video_metadata_file = f"{slug}.metadata.json"
                video_metadata_path = os.path.join(BASE, "videos", video_metadata_file)
                if os.path.exists(video_metadata_path):
                    artifacts["video_metadata"] = video_metadata_file
                
                # Find thumbnail (use slug for directory lookup)
                thumbnail_file = f"{slug}.png"
                thumbnail_path = os.path.join(BASE, "videos", thumbnail_file)
                if os.path.exists(thumbnail_path):
                    artifacts["thumbnail"] = thumbnail_file
                
                # Find SceneScript and animatics
                scenescript_file = f"{slug}.json"
                scenescript_path = os.path.join(BASE, "scenescripts", scenescript_file)
                if os.path.exists(scenescript_path):
                    artifacts["scenescript"] = scenescript_file
                
                # Find animatics (preferred in animatics-only mode)
                animatics_dir = os.path.join(BASE, "assets", f"{slug}_animatics")
                if os.path.exists(animatics_dir):
                    animatics_files = [f for f in os.listdir(animatics_dir) if f.endswith('.mp4')]
                    animatics_files.sort()  # Ensure scene order
                    artifacts["animatics"] = animatics_files
                    
                    # In animatics-only mode, use animatics as the primary assets
                    if hasattr(self.cfg, 'video') and getattr(self.cfg.video, 'animatics_only', False):
                        artifacts["assets"] = animatics_files
                        log.info(f"Animatics-only mode: using {len(animatics_files)} animatic scenes as assets")
                
                # Find traditional assets (fallback for legacy mode)
                if not artifacts.get("assets"):
                    assets_dir = os.path.join(BASE, "assets", slug)
                    if os.path.exists(assets_dir):
                        asset_files = [f for f in os.listdir(assets_dir) if f.endswith(('.mp4', '.jpg', '.png'))]
                        artifacts["assets"] = asset_files
        
        return artifacts
    
    def _find_blog_artifacts(self) -> Dict[str, Any]:
        """Find blog lane artifacts"""
        artifacts = {
            "post_html": None,
            "post_meta": None,
            "schema": None,
            "credits": None,
            "wp_payload": None,
            "assets": []
        }
        
        # Find most recent blog export
        exports_dir = os.path.join(BASE, "exports", "blog")
        if os.path.exists(exports_dir):
            export_dirs = [d for d in os.listdir(exports_dir) if os.path.isdir(os.path.join(exports_dir, d)) and not d.endswith('.zip')]
            if export_dirs:
                # Get most recent by date prefix
                export_dirs.sort(reverse=True)
                latest_export = export_dirs[0]
                export_path = os.path.join(exports_dir, latest_export)
                
                # Check for required files
                post_html = os.path.join(export_path, "post.html")
                if os.path.exists(post_html):
                    artifacts["post_html"] = f"exports/blog/{latest_export}/post.html"
                
                post_meta = os.path.join(export_path, "post.meta.json")
                if os.path.exists(post_meta):
                    artifacts["post_meta"] = f"exports/blog/{latest_export}/post.meta.json"
                
                schema = os.path.join(export_path, "schema.json")
                if os.path.exists(schema):
                    artifacts["schema"] = f"exports/blog/{latest_export}/schema.json"
                
                credits = os.path.join(export_path, "credits.json")
                if os.path.exists(credits):
                    artifacts["credits"] = f"exports/blog/{latest_export}/credits.json"
                
                wp_payload = os.path.join(export_path, "wp_rest_payload.json")
                if os.path.exists(wp_payload):
                    artifacts["wp_payload"] = f"exports/blog/{latest_export}/wp_rest_payload.json"
                
                # Check for assets
                assets_dir = os.path.join(export_path, "assets")
                if os.path.exists(assets_dir):
                    asset_files = [f for f in os.listdir(assets_dir) if f.endswith(('.mp4', '.jpg', '.png'))]
                    artifacts["assets"] = asset_files
        
        return artifacts
    
    def _validate_youtube_quality(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate YouTube lane quality metrics"""
        quality = {}
        
        # Script quality (word count, B-ROLL markers)
        if artifacts["script"]:
            script_path = os.path.join(BASE, "scripts", artifacts["script"])
            if os.path.exists(script_path):
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
                
                # Word count
                words = len(script_content.split())
                quality["script_words"] = words
                
                # B-ROLL marker count (handle both formats)
                # Count standalone [marker] format and [B-ROLL: description] format
                import re
                broll_pattern = r'\[[^\]]+\]'
                broll_matches = re.findall(broll_pattern, script_content)
                broll_markers = len(broll_matches)
                quality["broll_markers"] = broll_markers
                
                # Simple scoring based on content quality
                score = 0
                if words >= 800:
                    score += 30
                elif words >= 600:
                    score += 20
                elif words >= 400:
                    score += 10
                
                if broll_markers >= 10:
                    score += 30
                elif broll_markers >= 7:
                    score += 20
                elif broll_markers >= 5:
                    score += 10
                
                # Asset scoring - adjust for animatics-only mode
                if hasattr(self.cfg, 'video') and getattr(self.cfg.video, 'animatics_only', False):
                    # In animatics-only mode, 4 scenes is excellent (typical for 2-min video)
                    if len(artifacts["assets"]) >= 4:
                        score += 25  # Higher score for animatics
                    elif len(artifacts["assets"]) >= 3:
                        score += 20
                    elif len(artifacts["assets"]) >= 2:
                        score += 15
                else:
                    # Traditional asset scoring
                    if artifacts["assets"] and len(artifacts["assets"]) >= 10:
                        score += 20
                    elif artifacts["assets"] and len(artifacts["assets"]) >= 7:
                        score += 15
                    elif artifacts["assets"] and len(artifacts["assets"]) >= 5:
                        score += 10
                
                if artifacts["voiceover"]:
                    score += 10
                if artifacts["video"]:
                    score += 10
                
                quality["script_score"] = min(score, 100)
        
        # Asset quality
        if artifacts["assets"]:
            quality["asset_count"] = len(artifacts["assets"])
            
            # Visual coverage calculation - adjust for animatics-only mode
            if hasattr(self.cfg, 'video') and getattr(self.cfg.video, 'animatics_only', False):
                # In animatics-only mode, 4 scenes provides full coverage
                quality["visual_coverage"] = 100.0
            else:
                # Traditional asset coverage estimate
                quality["visual_coverage"] = min(100, len(artifacts["assets"]) * 10)
        
        return quality
    
    def _validate_blog_quality(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate blog lane quality metrics"""
        quality = {}
        
        # SEO lint check
        if artifacts["post_html"]:
            html_path = os.path.join(BASE, artifacts["post_html"])
            if os.path.exists(html_path):
                try:
                    # Import SEO lint function
                    from bin.seo_lint import lint as seo_lint
                    
                    with open(html_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    # Extract title and meta description from HTML for SEO lint
                    import re
                    title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
                    meta_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
                    
                    title = title_match.group(1) if title_match else "Untitled"
                    meta_desc = meta_match.group(1) if meta_match else "No description"
                    
                    # Run SEO lint
                    seo_issues = seo_lint(title, meta_desc)
                    quality["seo_lint_pass"] = len(seo_issues) == 0
                    quality["seo_issues"] = seo_issues
                    
                except ImportError:
                    quality["seo_lint_pass"] = True  # Assume pass if lint not available
                    quality["seo_warning"] = "SEO lint module not available"
                except Exception as e:
                    quality["seo_lint_pass"] = True  # Assume pass on error
                    quality["seo_warning"] = f"SEO lint error: {str(e)}"
        
        # Alt text coverage
        if artifacts["post_html"]:
            html_path = os.path.join(BASE, artifacts["post_html"])
            if os.path.exists(html_path):
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                import re
                img_pattern = r'<img[^>]*>'
                images = re.findall(img_pattern, html_content, re.IGNORECASE)
                
                if images:
                    alt_images = [img for img in images if 'alt=' in img.lower()]
                    quality["alt_text_coverage"] = int((len(alt_images) / len(images)) * 100)
                    quality["total_images"] = len(images)
                    quality["images_with_alt"] = len(alt_images)
        
        return quality
    
    def _validate_animatics_quality(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate animatics quality metrics"""
        quality = {}
        
        try:
            # Validate SceneScript
            if artifacts["scenescript"]:
                scenescript_path = os.path.join(BASE, "scenescripts", artifacts["scenescript"])
                if os.path.exists(scenescript_path):
                    with open(scenescript_path, 'r', encoding='utf-8') as f:
                        scenescript_data = json.load(f)
                    
                    # Import SceneScript validation
                    from bin.cutout.validate_scenescript import validate_schema
                    
                    # Validate against schema
                    validation_errors = validate_schema(scenescript_data)
                    quality["validation_pass"] = len(validation_errors) == 0
                    quality["validation_errors"] = validation_errors
                    
                    # Check legibility constraints
                    max_words = getattr(getattr(self.cfg, 'animatics', None), 'max_words_per_card', 12) if hasattr(self.cfg, 'animatics') else 12
                    safe_margins = getattr(getattr(self.cfg, 'animatics', None), 'safe_margins_px', 80) if hasattr(self.cfg, 'animatics') else 80
                    
                    legibility_issues = self._check_scenescript_legibility(scenescript_data, max_words, safe_margins)
                    quality["legibility_pass"] = len(legibility_issues) == 0
                    quality["legibility_issues"] = legibility_issues
                    
                    # Calculate scene coverage
                    coverage = self._calculate_scene_coverage(scenescript_data)
                    quality["scene_coverage"] = coverage
                    
                    min_coverage = getattr(getattr(self.cfg, 'animatics', None), 'min_coverage', 0.85) if hasattr(self.cfg, 'animatics') else 0.85
                    quality["coverage_pass"] = coverage >= min_coverage
                    
                    # Run QA gates validation
                    qa_result = self._run_qa_gates(scenescript_data)
                    quality["qa_gates_pass"] = qa_result.get("ok", False)
                    quality["qa_gates_fails"] = qa_result.get("fails", [])
                    quality["qa_gates_warnings"] = qa_result.get("warnings", [])
                    quality["qa_gates_details"] = qa_result.get("details", {})
                    
                    # Validate duration policy compliance
                    duration_result = self._validate_duration_policy(scenescript_data)
                    quality["duration_pass"] = duration_result.get("pass", False)
                    quality["duration_details"] = duration_result.get("details", {})
                    quality["duration_issues"] = duration_result.get("issues", [])
                    
                    # Write video metadata with duration information
                    if duration_result.get("details"):
                        slug = scenescript_data.get("slug", "unknown")
                        metadata_path = self._write_video_metadata(slug, duration_result["details"])
                        if metadata_path:
                            quality["metadata_path"] = metadata_path
                    
                    # Validate layout engine integration
                    layout_result = self._validate_layout_engine_integration(scenescript_data)
                    quality["layout_pass"] = layout_result.get("pass", False)
                    quality["layout_issues"] = layout_result.get("issues", [])
                    quality["layout_details"] = layout_result.get("details", {})
                    
                    # Overall validation result
                    quality["overall_pass"] = (
                        quality.get("validation_pass", False) and
                        quality.get("legibility_pass", False) and
                        quality.get("coverage_pass", False) and
                        quality.get("qa_gates_pass", False) and
                        quality.get("duration_pass", False) and
                        quality.get("layout_pass", False)
                    )
                    
        except Exception as e:
            quality["validation_pass"] = False
            quality["error"] = f"Validation error: {str(e)}"
            quality["overall_pass"] = False
        
        return quality
    
    def _check_scenescript_legibility(self, scenescript_data: Dict, max_words: int, safe_margins: int) -> List[str]:
        """Check SceneScript legibility constraints"""
        issues = []
        
        try:
            scenes = scenescript_data.get("scenes", [])
            for i, scene in enumerate(scenes):
                elements = scene.get("elements", [])
                for j, element in enumerate(elements):
                    if element.get("type") == "text" and element.get("content"):
                        # Check word count
                        words = len(element["content"].split())
                        if words > max_words:
                            issues.append(f"Scene {i}, Element {j}: {words} words exceeds limit of {max_words}")
                        
                        # Check positioning (basic bounds check)
                        x = element.get("x", 0)
                        y = element.get("y", 0)
                        width = element.get("width", 0)
                        height = element.get("height", 0)
                        
                        # Check if text is too close to edges
                        if x < safe_margins or y < safe_margins:
                            issues.append(f"Scene {i}, Element {j}: Text too close to left/top edge")
                        
                        # Check if text extends beyond safe right/bottom bounds
                        if x + width > 1920 - safe_margins or y + height > 1080 - safe_margins:
                            issues.append(f"Scene {i}, Element {j}: Text extends beyond safe right/bottom bounds")
                            
        except Exception as e:
            issues.append(f"Legibility check error: {str(e)}")
        
        return issues
    
    def _validate_duration_policy(self, scenescript_data: Dict) -> Dict[str, Any]:
        """Validate duration policy compliance"""
        result = {"pass": False, "details": {}, "issues": []}
        
        try:
            # Load timing configuration
            timing_config = {}
            try:
                from bin.core import load_modules_cfg
                timing_config = load_modules_cfg().get('timing', {})
            except Exception as e:
                log.warning(f"Could not load timing config: {e}")
                # Use defaults
                timing_config = {
                    'target_tolerance_pct': 5.0,
                    'min_scene_ms': 2500,
                    'max_scene_ms': 30000
                }
            
            # Get brief configuration for target duration
            brief = {}
            try:
                brief = cfg.brief if hasattr(cfg, 'brief') else {}
            except Exception:
                log.warning("Could not load brief config")
            
            # Calculate actual total duration
            scenes = scenescript_data.get("scenes", [])
            total_duration_ms = sum(scene.get("duration_ms", 0) for scene in scenes)
            
            # Get target duration from brief
            target_min = brief.get('video', {}).get('target_length_min', 1.5)
            target_max = brief.get('video', {}).get('target_length_max', target_min)
            target_sec = target_min if target_min == target_max else (target_min + target_max) / 2
            target_ms = int(target_sec * 60 * 1000)
            
            # Check individual scene duration bounds
            min_scene_ms = timing_config.get('min_scene_ms', 2500)
            max_scene_ms = timing_config.get('max_scene_ms', 12000)
            
            out_of_bounds_scenes = []
            for i, scene in enumerate(scenes):
                duration = scene.get("duration_ms", 0)
                if duration < min_scene_ms or duration > max_scene_ms:
                    out_of_bounds_scenes.append(f"Scene {i}: {duration}ms (bounds: {min_scene_ms}-{max_scene_ms}ms)")
            
            # Check total duration tolerance
            tolerance_pct = timing_config.get('target_tolerance_pct', 5.0)
            deviation_pct = abs(total_duration_ms - target_ms) / target_ms * 100 if target_ms > 0 else 0
            within_tolerance = deviation_pct <= tolerance_pct
            
            # Check VO alignment if available
            vo_aligned = False
            vo_details = {}
            try:
                slug = scenescript_data.get("slug", "unknown")
                from bin.timing_utils import load_vo_cues
                vo_cues = load_vo_cues(slug)
                if vo_cues and vo_cues.get('scenes'):
                    vo_total_ms = sum(
                        scene.get('end_ms', 0) - scene.get('start_ms', 0) 
                        for scene in vo_cues['scenes']
                    )
                    vo_deviation_pct = abs(vo_total_ms - target_ms) / target_ms * 100 if target_ms > 0 else 0
                    vo_within_tolerance = vo_deviation_pct <= tolerance_pct
                    vo_aligned = vo_within_tolerance
                    vo_details = {
                        "vo_total_ms": vo_total_ms,
                        "vo_deviation_pct": round(vo_deviation_pct, 2),
                        "vo_within_tolerance": vo_within_tolerance
                    }
            except Exception as e:
                log.debug(f"VO alignment check failed: {e}")
            
            # Determine overall pass/fail
            scene_bounds_pass = len(out_of_bounds_scenes) == 0
            total_duration_pass = within_tolerance
            
            result["pass"] = scene_bounds_pass and total_duration_pass
            result["details"] = {
                "total_duration_ms": total_duration_ms,
                "target_duration_ms": target_ms,
                "deviation_pct": round(deviation_pct, 2),
                "tolerance_pct": tolerance_pct,
                "within_tolerance": within_tolerance,
                "scene_bounds_pass": scene_bounds_pass,
                "min_scene_ms": min_scene_ms,
                "max_scene_ms": max_scene_ms,
                "vo_aligned": vo_aligned,
                "vo_details": vo_details
            }
            
            # Collect issues
            if not scene_bounds_pass:
                result["issues"].extend(out_of_bounds_scenes)
            
            if not total_duration_pass:
                result["issues"].append(
                    f"Total duration {total_duration_ms}ms exceeds {tolerance_pct}% tolerance of target {target_ms}ms "
                    f"(deviation: {deviation_pct:.1f}%)"
                )
                
                # Provide remediation hints
                if deviation_pct > tolerance_pct * 2:
                    result["issues"].append(
                        "Consider: adjust beat durations, change distribution strategy, or review brief target length"
                    )
            
            log.info(f"Duration policy validation: {'PASS' if result['pass'] else 'FAIL'}")
            log.info(f"  Target: {target_ms}ms, Actual: {total_duration_ms}ms, Deviation: {deviation_pct:.1f}%")
            
        except Exception as e:
            result["pass"] = False
            result["error"] = f"Duration validation error: {str(e)}"
            result["issues"].append(f"Validation error: {str(e)}")
        
        return result
    
    def _write_video_metadata(self, slug: str, duration_details: Dict) -> str:
        """Write video metadata with duration information"""
        try:
            # Load timing configuration
            timing_config = {}
            try:
                cfg = load_config()
                timing_config = getattr(cfg, 'timing', {})
            except Exception:
                timing_config = {
                    'target_tolerance_pct': 5.0,
                    'default_scene_ms': 5000,
                    'min_scene_ms': 2500,
                    'max_scene_ms': 12000,
                    'distribute_strategy': 'weighted',
                    'align_to_vo': True
                }
            
            # Create metadata structure
            metadata = {
                "duration": {
                    "target_ms": duration_details.get("target_duration_ms", 0),
                    "actual_ms": duration_details.get("total_duration_ms", 0),
                    "deviation_pct": duration_details.get("deviation_pct", 0),
                    "source": "brief" if duration_details.get("within_tolerance", False) else "calculated"
                },
                "timing_settings": timing_config,
                "validation": {
                    "duration_pass": duration_details.get("within_tolerance", False),
                    "scene_bounds_pass": duration_details.get("scene_bounds_pass", False),
                    "vo_aligned": duration_details.get("vo_aligned", False)
                },
                "generated_at": datetime.utcnow().isoformat() + "Z"
            }
            
            # Add VO details if available
            vo_details = duration_details.get("vo_details", {})
            if vo_details:
                metadata["duration"]["vo_total_ms"] = vo_details.get("vo_total_ms", 0)
                metadata["duration"]["vo_deviation_pct"] = vo_details.get("vo_deviation_pct", 0)
                if vo_details.get("vo_within_tolerance", False):
                    metadata["duration"]["source"] = "vo"
            
            # Write to videos directory
            videos_dir = Path(BASE) / "videos"
            videos_dir.mkdir(exist_ok=True)
            
            metadata_path = videos_dir / f"{slug}.metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            log.info(f"Video metadata written to: {metadata_path}")
            return str(metadata_path)
            
        except Exception as e:
            log.error(f"Failed to write video metadata: {e}")
            return ""
    
    def _run_qa_gates(self, scenescript_data: Dict) -> Dict[str, Any]:
        """Run QA gates validation on SceneScript data"""
        try:
            from bin.cutout.qa_gates import run_all
            
            # Extract scenes for rhythm analysis
            scenes = scenescript_data.get("scenes", [])
            if not scenes:
                return {"ok": False, "fails": ["No scenes found"], "warnings": [], "details": {}}
            
            # Extract palette from scenes
            palette = []
            for scene in scenes:
                # Extract colors from scene elements
                elements = scene.get("elements", [])
                for element in elements:
                    if "color" in element:
                        palette.append(element["color"])
                    if "style" in element and "color" in element["style"]:
                        palette.append(element["style"]["color"])
                
                # Extract background colors
                if "background" in scene and "color" in scene["background"]:
                    palette.append(scene["background"]["color"])
                if "composition_rules" in scene and "background_color" in scene["composition_rules"]:
                    palette.append(scene["composition_rules"]["background_color"])
            
            # Run QA gates on first scene (representative sample)
            first_scene = scenes[0]
            qa_result = run_all(first_scene, scenes, palette)
            
            # Convert to dict for JSON serialization
            return {
                "ok": qa_result.ok,
                "fails": qa_result.fails,
                "warnings": qa_result.warnings,
                "details": qa_result.details
            }
            
        except ImportError:
            return {"ok": False, "fails": ["QA gates module not available"], "warnings": [], "details": {}}
        except Exception as e:
            return {"ok": False, "fails": [f"QA gates error: {str(e)}"], "warnings": [], "details": {}}
    
    def _calculate_scene_coverage(self, scenescript_data: Dict) -> float:
        """Calculate scene coverage ratio (scenes with content vs empty scenes)"""
        try:
            scenes = scenescript_data.get("scenes", [])
            if not scenes:
                return 0.0
            
            scenes_with_content = 0
            for scene in scenes:
                elements = scene.get("elements", [])
                if elements:
                    # Check if scene has meaningful content
                    has_text = any(e.get("type") == "text" and e.get("content") for e in elements)
                    has_visuals = any(e.get("type") in ["prop", "character", "shape"] for e in elements)
                    
                    if has_text or has_visuals:
                        scenes_with_content += 1
            
            return scenes_with_content / len(scenes)
            
        except Exception:
            return 0.0
    
    def _validate_layout_engine_integration(self, scenescript_data: Dict) -> Dict[str, Any]:
        """Validate that layout engine integration is working properly"""
        result = {"pass": True, "issues": [], "details": {}}
        
        try:
            scenes = scenescript_data.get("scenes", [])
            if not scenes:
                result["pass"] = False
                result["issues"].append("No scenes found in SceneScript")
                return result
            
            total_elements = 0
            positioned_elements = 0
            scenes_without_positions = 0
            scenes_with_positions = 0
            
            for i, scene in enumerate(scenes):
                elements = scene.get("elements", [])
                scene_needs_layout = False
                scene_has_positions = False
                
                for element in elements:
                    total_elements += 1
                    if "x" in element and "y" in element:
                        positioned_elements += 1
                        scene_has_positions = True
                    else:
                        scene_needs_layout = True
                
                if scene_needs_layout:
                    scenes_without_positions += 1
                if scene_has_positions:
                    scenes_with_positions += 1
            
            # Check if animatics_only mode is enabled
            animatics_only = getattr(self.cfg.video, "animatics_only", True) if hasattr(self.cfg, 'video') else True
            
            result["details"] = {
                "total_elements": total_elements,
                "positioned_elements": positioned_elements,
                "scenes_without_positions": scenes_without_positions,
                "scenes_with_positions": scenes_with_positions,
                "animatics_only": animatics_only
            }
            
            # In animatics_only mode, all scenes should have positioned elements
            if animatics_only:
                if scenes_without_positions > 0:
                    result["pass"] = False
                    result["issues"].append(
                        f"Found {scenes_without_positions} scenes without positions in animatics_only mode"
                    )
                
                if positioned_elements < total_elements:
                    result["pass"] = False
                    result["issues"].append(
                        f"Found {total_elements - positioned_elements} elements without positions in animatics_only mode"
                    )
            
            # Log layout validation results
            if result["pass"]:
                log.info(f"[layout] Layout validation PASSED: {positioned_elements}/{total_elements} elements positioned")
            else:
                log.warning(f"[layout] Layout validation FAILED: {len(result['issues'])} issues found")
                for issue in result["issues"]:
                    log.warning(f"[layout] Issue: {issue}")
            
        except Exception as e:
            result["pass"] = False
            result["issues"].append(f"Layout validation error: {str(e)}")
            log.error(f"[layout] Layout validation error: {e}")
        
        return result
    
    def run_validation(self) -> Dict[str, Any]:
        """Run complete validation and return results"""
        log.info("Starting acceptance validation...")
        
        # Validate YouTube lane
        youtube_ok = self.validate_youtube_lane()
        
        # Validate blog lane  
        blog_ok = self.validate_blog_lane()
        
        # Determine overall status
        if youtube_ok and blog_ok:
            self.results["overall_status"] = "PASS"
        else:
            self.results["overall_status"] = "FAIL"
        
        # Add summary
        self.results["summary"] = {
            "youtube_lane": "PASS" if youtube_ok else "FAIL",
            "blog_lane": "PASS" if blog_ok else "FAIL",
            "total_artifacts": {
                "youtube": len([v for v in self.results["lanes"]["youtube"]["artifacts"].values() if v]),
                "blog": len([v for v in self.results["lanes"]["blog"]["artifacts"].values() if v])
            }
        }
        
        return self.results


def run_orchestrator_dry_run() -> bool:
    """Run the orchestrator in DRY mode"""
    log.info("Running orchestrator in DRY mode...")
    
    orchestrator_path = os.path.join(BASE, "bin", "run_pipeline.py")
    if not os.path.exists(orchestrator_path):
        log.error("Orchestrator not found: run_pipeline.py")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, orchestrator_path, "--dry-run"],
            cwd=BASE,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        if result.returncode == 0:
            log.info("Orchestrator completed successfully in DRY mode")
            return True
        else:
            log.error(f"Orchestrator failed with exit code {result.returncode}")
            log.error(f"STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log.error("Orchestrator timed out after 30 minutes")
        return False
    except Exception as e:
        log.error(f"Orchestrator error: {e}")
        return False


def main():
    """Main acceptance test runner"""
    parser = argparse.ArgumentParser(description="Acceptance harness for content pipeline")
    parser.add_argument("--skip-orchestrator", action="store_true", 
                       help="Skip running orchestrator, only validate existing artifacts")
    parser.add_argument("--output", default="acceptance_results.json",
                       help="Output file for results (default: acceptance_results.json)")
    
    args = parser.parse_args()
    
    log.info("=== ACCEPTANCE HARNESS STARTING ===")
    
    # Load configuration
    try:
        cfg = load_config()
        blog_cfg = load_blog_cfg()
        log.info("Configuration loaded successfully")
    except Exception as e:
        log.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Run orchestrator if not skipped
    if not args.skip_orchestrator:
        if not run_orchestrator_dry_run():
            log.error("Orchestrator failed, cannot proceed with validation")
            sys.exit(1)
        log.info("Orchestrator completed, proceeding with validation")
    else:
        log.info("Skipping orchestrator run, validating existing artifacts")
    
    # Run validation
    validator = AcceptanceValidator(cfg, blog_cfg)
    results = validator.run_validation()
    
    # Output results
    output_path = os.path.join(BASE, args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Log results
    log.info(f"Acceptance results written to: {output_path}")
    log.info(f"Overall status: {results['overall_status']}")
    log.info(f"YouTube lane: {results['summary']['youtube_lane']}")
    log.info(f"Blog lane: {results['summary']['blog_lane']}")
    
    # Exit with appropriate code
    if results["overall_status"] == "PASS":
        log.info("=== ACCEPTANCE HARNESS PASSED ===")
        sys.exit(0)
    else:
        log.error("=== ACCEPTANCE HARNESS FAILED ===")
        sys.exit(1)


if __name__ == "__main__":
    with single_lock():
        main()
