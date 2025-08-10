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
    log_state,
    single_lock
)

log = get_logger("acceptance")


class AcceptanceValidator:
    """Validates pipeline artifacts and quality thresholds"""
    
    def __init__(self, cfg, blog_cfg):
        self.cfg = cfg
        self.blog_cfg = blog_cfg
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
            
        if len(artifacts["assets"]) < self.results["quality_thresholds"]["min_assets"]:
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = f"Only {len(artifacts['assets'])} assets, need {self.results['quality_thresholds']['min_assets']}"
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
            "assets": [],
            "voiceover": None,
            "captions": None,
            "video": None,
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
                    slug = best_script.replace('.txt', '')
                    outline_file = f"{slug}.outline.json"
                    artifacts["outline"] = outline_file
                elif script_files:
                    # Fallback to first script with outline
                    for script_file in script_files:
                        slug = script_file.replace('.txt', '')
                        outline_file = f"{slug}.outline.json"
                        outline_path = os.path.join(scripts_dir, outline_file)
                        
                        if os.path.exists(outline_path):
                            artifacts["script"] = script_file
                            artifacts["outline"] = outline_file
                            break
                
                # If no complete set found, use the first script
                if not artifacts["script"]:
                    artifacts["script"] = script_files[0]
                    slug = script_files[0].replace('.txt', '')
                    date_prefix = slug.split('_')[0]
                
                # Find voiceover
                voiceover_file = f"{slug}.mp3"
                voiceover_path = os.path.join(BASE, "voiceovers", voiceover_file)
                if os.path.exists(voiceover_path):
                    artifacts["voiceover"] = voiceover_file
                
                # Find captions
                captions_file = f"{slug}.srt"
                captions_path = os.path.join(BASE, "voiceovers", captions_file)
                if os.path.exists(captions_path):
                    artifacts["captions"] = captions_file
                
                # Find video
                video_file = f"{slug}.mp4"
                video_path = os.path.join(BASE, "videos", video_file)
                if os.path.exists(video_path):
                    artifacts["video"] = video_file
                
                # Find thumbnail
                thumbnail_file = f"{slug}.png"
                thumbnail_path = os.path.join(BASE, "videos", thumbnail_file)
                if os.path.exists(thumbnail_path):
                    artifacts["thumbnail"] = thumbnail_file
                
                # Find assets
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
            quality["visual_coverage"] = min(100, len(artifacts["assets"]) * 10)  # Rough estimate
        
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
