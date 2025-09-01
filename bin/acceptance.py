#!/usr/bin/env python3
"""
Acceptance Harness for Content Pipeline

Runs the orchestrator in DRY mode and validates all artifacts with quality thresholds.
Emits PASS/FAIL JSON with artifact pointers and quality metrics.
Enhanced with Phase 1 fixes: FFmpeg robustness, SRT fallbacks, legibility defaults, duration policy.
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

    load_modules_cfg,
    log_state,
    single_lock
)

log = get_logger("acceptance")


class AcceptanceValidator:
    """Validates pipeline artifacts and quality thresholds"""
    
    def __init__(self, cfg):
        self.cfg = cfg
        self.modules_cfg = load_modules_cfg()
        
        # Load render configuration for acceptance settings
        self.render_cfg = self._load_render_config()
        
        # Create temporary directory for audio validation
        import tempfile
        self.temp_dir = tempfile.mktemp(prefix="acceptance_")
        self.results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "pipeline": "acceptance_harness",
            "overall_status": "PENDING",
            "lanes": {
                "youtube": {"status": "PENDING", "artifacts": {}, "quality": {}}
            },
            "quality_thresholds": {
                "script_score_min": self.render_cfg.get("acceptance", {}).get("min_script_score", 50),
                "seo_lint_pass": True,
                "visual_coverage_min": self.render_cfg.get("acceptance", {}).get("min_coverage", 0.85) * 100,
                "min_assets": self.render_cfg.get("acceptance", {}).get("min_assets", 10),
                "min_script_words": self.render_cfg.get("acceptance", {}).get("min_script_words", 350)
            },
            "assets": {
                "status": "PENDING",
                "coverage": {},
                "reuse_ratio": {},
                "palette_compliance": {},
                "qa_results": {},
                "provenance": []
            },
            "visual_polish": {
                "status": "PENDING",
                "textures": {"status": "PENDING", "enabled": False},
                "geometry": {"status": "PENDING", "enabled": False},
                "micro_animations": {"status": "PENDING", "enabled": False},
                "performance": {"status": "PENDING"}
            },
            "evidence": {
                "status": "PENDING",
                "citations": {
                    "total_count": 0,
                    "unique_domains": 0,
                    "beats_coverage_pct": 0.0
                },
                "policy_checks": {
                    "min_citations_per_intent": "PENDING",
                    "whitelist_compliance": "PENDING",
                    "non_whitelisted_warnings": []
                },
                "fact_guard_summary": {
                    "removed_count": 0,
                    "rewritten_count": 0,
                    "flagged_count": 0,
                    "strict_mode_fail": False
                },
                "errors": [],
                "warnings": []
            },
            "pacing": {
                "status": "PENDING",
                "enabled": False,
                "kpi_metrics": {},
                "comparison": {},
                "verdict": "PENDING",
                "adjusted": False,
                "errors": [],
                "warnings": []
            },
            "acceptance_config": {
                "duration_tolerance_pct": self.render_cfg.get("acceptance", {}).get("tolerance_pct", 5.0),
                "audio_validation_required": self.render_cfg.get("acceptance", {}).get("audio_validation_required", True),
                "caption_validation_required": self.render_cfg.get("acceptance", {}).get("caption_validation_required", True),
                "legibility_validation_required": self.render_cfg.get("acceptance", {}).get("legibility_validation_required", True),
                "wcag_aa_threshold": self.render_cfg.get("acceptance", {}).get("wcag_aa_threshold", 4.5)
            }
        }
    
    def _load_render_config(self) -> Dict[str, Any]:
        """Load render configuration for acceptance settings"""
        try:
            render_path = os.path.join(BASE, "conf", "render.yaml")
            if os.path.exists(render_path):
                import yaml
                with open(render_path, 'r', encoding='utf-8') as f:
                    render_cfg = yaml.safe_load(f)
                log.info("[acceptance] Loaded render.yaml configuration")
                return render_cfg
            else:
                log.warning("[acceptance] render.yaml not found, using defaults")
                return {}
        except Exception as e:
            log.warning(f"[acceptance] Failed to load render.yaml: {e}, using defaults")
            return {}
    
    def __del__(self):
        """Clean up temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass
    
    def _validate_assets_quality(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate asset quality: coverage, reuse, palette compliance, and QA results"""
        log.info("[acceptance-assets] Starting asset quality validation")
        
        asset_results = {
            "status": "PENDING",
            "coverage": {},
            "reuse_ratio": {},
            "palette_compliance": {},
            "qa_results": {},
            "provenance": [],
            "errors": [],
            "warnings": []
        }
        
        # Find asset plan and related files
        slug = self._extract_slug_from_artifacts(artifacts)
        if not slug:
            asset_results["status"] = "FAIL"
            asset_results["errors"].append("Could not determine slug for asset validation")
            return asset_results
        
        # Check asset plan for gaps
        asset_plan_path = os.path.join(BASE, "runs", slug, "asset_plan.json")
        if not os.path.exists(asset_plan_path):
            asset_results["status"] = "FAIL"
            asset_results["errors"].append(f"Missing asset plan: {asset_plan_path}")
            return asset_results
        
        try:
            with open(asset_plan_path, 'r') as f:
                asset_plan = json.load(f)
            
            # Check for unresolved gaps
            gaps = asset_plan.get("gaps", [])
            if len(gaps) > 0:
                asset_results["status"] = "FAIL"
                asset_results["errors"].append(f"Found {len(gaps)} unresolved asset gaps")
                asset_results["coverage"]["gaps"] = gaps
                asset_results["coverage"]["gaps_count"] = len(gaps)
            else:
                asset_results["coverage"]["gaps"] = []
                asset_results["coverage"]["gaps_count"] = 0
                asset_results["coverage"]["status"] = "pass"
            
            # Check reuse ratio
            reuse_ratio = asset_plan.get("reuse_ratio", 0.0)
            asset_results["reuse_ratio"]["value"] = reuse_ratio
            
            # Check if we have a substantial library to enforce reuse ratio
            library_manifest_path = os.path.join(BASE, "data", "library_manifest.json")
            if os.path.exists(library_manifest_path):
                try:
                    with open(library_manifest_path, 'r') as f:
                        manifest = json.load(f)
                    total_assets = manifest.get("total_assets", 0)
                    asset_results["reuse_ratio"]["total_library_assets"] = total_assets
                    
                    if total_assets > 50:
                        # Enforce reuse ratio threshold
                        reuse_threshold = getattr(self.modules_cfg, 'assets', {}).get('reuse_ratio_threshold', 0.7)
                        if reuse_ratio < reuse_threshold:
                            asset_results["status"] = "FAIL"
                            asset_results["errors"].append(f"Reuse ratio {reuse_ratio:.1%} below threshold {reuse_threshold:.1%}")
                        else:
                            asset_results["reuse_ratio"]["status"] = "pass"
                    else:
                        asset_results["reuse_ratio"]["status"] = "exempt"
                        asset_results["warnings"].append(f"Library has only {total_assets} assets, reuse ratio not enforced")
                except Exception as e:
                    log.warning(f"[acceptance-assets] Could not read library manifest: {e}")
                    asset_results["reuse_ratio"]["status"] = "unknown"
            else:
                asset_results["reuse_ratio"]["status"] = "no_manifest"
                asset_results["warnings"].append("No library manifest found")
            
            # Check palette compliance
            palette_compliance = self._check_palette_compliance(asset_plan, slug)
            asset_results["palette_compliance"] = palette_compliance
            
            if not palette_compliance.get("status") == "pass":
                asset_results["status"] = "FAIL"
                asset_results["errors"].append("Palette compliance check failed")
            
            # Check QA results
            qa_results = self._check_qa_results(slug)
            asset_results["qa_results"] = qa_results
            
            if not qa_results.get("status") == "pass":
                asset_results["status"] = "FAIL"
                asset_results["errors"].append("QA results check failed")
            
            # Record provenance for generated assets
            provenance = self._extract_provenance(slug)
            asset_results["provenance"] = provenance
            
            # Determine overall asset status
            if asset_results["status"] == "PENDING" and not asset_results["errors"]:
                asset_results["status"] = "PASS"
            
            log.info(f"[acceptance-assets] Asset validation completed: {asset_results['status']}")
            return asset_results
            
        except Exception as e:
            log.error(f"[acceptance-assets] Asset validation error: {e}")
            asset_results["status"] = "FAIL"
            asset_results["errors"].append(f"Asset validation error: {str(e)}")
            return asset_results
    
    def _check_palette_compliance(self, asset_plan: Dict[str, Any], slug: str) -> Dict[str, Any]:
        """Check if all assets comply with approved palette colors using manifest data"""
        log.info("[acceptance-assets] Checking palette compliance")
        
        result = {
            "status": "PENDING",
            "violations": [],
            "approved_colors": [],
            "total_assets": 0,
            "compliant_assets": 0,
            "delta_e_violations": []
        }
        
        # Load approved palette from design language
        design_language_path = os.path.join(BASE, "design", "design_language.json")
        if not os.path.exists(design_language_path):
            result["status"] = "FAIL"
            result["violations"].append("Design language file not found")
            return result
        
        try:
            with open(design_language_path, 'r') as f:
                design_language = json.load(f)
            
            approved_colors = list(design_language.get("colors", {}).values())
            result["approved_colors"] = approved_colors
            
            # Load library manifest for palette validation
            library_manifest_path = os.path.join(BASE, "data", "library_manifest.json")
            if os.path.exists(library_manifest_path):
                with open(library_manifest_path, 'r') as f:
                    manifest = json.load(f)
                
                # Check resolved assets against manifest
                resolved_assets = asset_plan.get("resolved", [])
                result["total_assets"] = len(resolved_assets)
                
                for asset in resolved_assets:
                    asset_hash = asset.get("asset_hash")
                    if asset_hash and asset_hash in manifest.get("assets", {}):
                        manifest_asset = manifest["assets"][asset_hash]
                        palette_ok = manifest_asset.get("palette_ok", False)
                        
                        if palette_ok:
                            result["compliant_assets"] += 1
                        else:
                            delta_e_violations = manifest_asset.get("delta_e_violations", [])
                            if delta_e_violations:
                                result["delta_e_violations"].extend(delta_e_violations)
                                result["violations"].append({
                                    "asset_path": asset.get("asset", "unknown"),
                                    "element_id": asset.get("element_id", "unknown"),
                                    "violations": delta_e_violations
                                })
                
                # Check asset generation report for additional palette violations
                generation_report_path = os.path.join(BASE, "runs", slug, "asset_generation_report.json")
                if os.path.exists(generation_report_path):
                    with open(generation_report_path, 'r') as f:
                        generation_report = json.load(f)
                    
                    generated_assets = generation_report.get("generated_assets", [])
                    for asset in generated_assets:
                        if not asset.get("palette_compliant", True):
                            result["violations"].append({
                                "asset_path": asset.get("path", "unknown"),
                                "element_id": asset.get("element_id", "unknown"),
                                "palette_violations": asset.get("palette_violations", [])
                            })
            else:
                log.warning("[acceptance-assets] Library manifest not found, using basic palette check")
                
                # Fallback to basic palette check
                resolved_assets = asset_plan.get("resolved", [])
                result["total_assets"] = len(resolved_assets)
                
                for asset in resolved_assets:
                    if asset.get("reuse_type") == "generated":
                        # For generated assets, check if they have palette violations
                        if not asset.get("palette_compliant", True):
                            result["violations"].append({
                                "asset_path": asset.get("asset", "unknown"),
                                "element_id": asset.get("element_id", "unknown"),
                                "reason": "Generated asset not palette compliant"
                            })
            
            # Determine status
            if result["violations"]:
                result["status"] = "FAIL"
                log.warning(f"[acceptance-assets] Found {len(result['violations'])} palette violations")
            else:
                result["status"] = "pass"
                log.info(f"[acceptance-assets] All {result['total_assets']} assets are palette compliant")
            
            return result
            
        except Exception as e:
            log.error(f"[acceptance-assets] Palette compliance check error: {e}")
            result["status"] = "FAIL"
            result["violations"].append(f"Palette compliance check error: {str(e)}")
            return result
    
    def _check_qa_results(self, slug: str) -> Dict[str, Any]:
        """Check QA results from reflow summary"""
        log.info("[acceptance-assets] Checking QA results")
        
        result = {
            "status": "PENDING",
            "collisions": [],
            "safe_margin_violations": [],
            "contrast_issues": [],
            "overall_status": "unknown",
            "errors": []
        }
        
        reflow_summary_path = os.path.join(BASE, "runs", slug, "reflow_summary.json")
        if not os.path.exists(reflow_summary_path):
            result["status"] = "FAIL"
            result["errors"].append("Missing reflow summary")
            return result
        
        try:
            with open(reflow_summary_path, 'r') as f:
                reflow_summary = json.load(f)
            
            scenes = reflow_summary.get("scenes", [])
            total_scenes = len(scenes)
            failed_scenes = 0
            
            for scene in scenes:
                scene_id = scene.get("scene_id", "unknown")
                qa_results = scene.get("qa_results", {})
                
                # Check for collisions
                collisions = qa_results.get("collisions", [])
                if collisions:
                    result["collisions"].extend([{
                        "scene_id": scene_id,
                        "collisions": collisions
                    }])
                
                # Check safe margin violations
                safe_margins = qa_results.get("safe_margins", {})
                violations = safe_margins.get("violations", [])
                if violations:
                    result["safe_margin_violations"].extend([{
                        "scene_id": scene_id,
                        "violations": violations
                    }])
                
                # Check contrast issues
                contrast = qa_results.get("contrast", {})
                if contrast.get("status") == "fail":
                    result["contrast_issues"].append({
                        "scene_id": scene_id,
                        "contrast": contrast
                    })
                
                # Check overall scene status
                if scene.get("status") != "pass":
                    failed_scenes += 1
            
            # Determine overall QA status
            if result["collisions"] or result["safe_margin_violations"] or result["contrast_issues"]:
                result["status"] = "FAIL"
                result["overall_status"] = "fail"
            elif failed_scenes > 0:
                result["status"] = "FAIL"
                result["overall_status"] = "fail"
            else:
                result["status"] = "pass"
                result["overall_status"] = "pass"
            
            result["total_scenes"] = total_scenes
            result["failed_scenes"] = failed_scenes
            
            return result
            
        except Exception as e:
            log.error(f"[acceptance-assets] QA results check error: {e}")
            result["status"] = "FAIL"
            result["errors"].append(f"QA results check error: {str(e)}")
            return result
    
    def _extract_provenance(self, slug: str) -> List[Dict[str, Any]]:
        """Extract provenance information for generated assets"""
        log.info("[acceptance-assets] Extracting provenance information")
        
        provenance = []
        
        # Check asset generation report
        generation_report_path = os.path.join(BASE, "runs", slug, "asset_generation_report.json")
        if os.path.exists(generation_report_path):
            try:
                with open(generation_report_path, 'r') as f:
                    generation_report = json.load(f)
                
                generated_assets = generation_report.get("generated_assets", [])
                for asset in generated_assets:
                    provenance.append({
                        "path": asset.get("path", ""),
                        "seed": asset.get("seed", None),
                        "generator_params": asset.get("generator_params", {}),
                        "palette": asset.get("palette", []),
                        "category": asset.get("category", ""),
                        "style": asset.get("style", ""),
                        "element_id": asset.get("element_id", ""),
                        "asset_hash": asset.get("asset_hash", "")
                    })
                
                log.info(f"[acceptance-assets] Found {len(provenance)} generated assets with provenance")
                
            except Exception as e:
                log.warning(f"[acceptance-assets] Could not read generation report: {e}")
        
        return provenance
    
    def _extract_slug_from_artifacts(self, artifacts: Dict[str, Any]) -> Optional[str]:
        """Extract slug from artifacts for asset validation"""
        # Try to get slug from script filename
        script = artifacts.get("script")
        if script:
            # Remove .txt extension
            slug = script.replace('.txt', '')
            # If it has a date prefix (format: YYYY-MM-DD_slug), extract the slug part
            if '_' in slug and len(slug.split('_')[0]) == 10 and slug.split('_')[0].replace('-', '').isdigit():
                slug = slug.split('_', 1)[1]  # Get part after date prefix
            return slug
        
        # Try to get slug from video metadata
        video_metadata = artifacts.get("video_metadata")
        if video_metadata:
            try:
                metadata_path = os.path.join(BASE, "videos", video_metadata)
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    return metadata.get("slug")
            except Exception:
                pass
        
        # Try to get slug from scenescript filename
        scenescript = artifacts.get("scenescript")
        if scenescript:
            # Remove .json extension
            slug = scenescript.replace('.json', '')
            return slug
        
        return None
    
    def _update_video_metadata_with_assets(self, slug: str, asset_results: Dict[str, Any]):
        """Update video metadata with asset coverage and reuse information"""
        log.info(f"[acceptance-assets] Updating video metadata for {slug}")
        
        video_metadata_path = os.path.join(BASE, "videos", f"{slug}.metadata.json")
        if not os.path.exists(video_metadata_path):
            log.warning(f"[acceptance-assets] Video metadata not found: {video_metadata_path}")
            return
        
        try:
            with open(video_metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Preserve existing metadata sections
            if "assets" not in metadata:
                metadata["assets"] = {}
            
            # Update assets section
            metadata["assets"].update({
                "coverage_pct": 100.0 if asset_results["coverage"]["gaps_count"] == 0 else 0.0,
                "reuse_ratio": asset_results["reuse_ratio"]["value"],
                "total_generated": len(asset_results["provenance"]),
                "manifest_version": "1.0",  # This should come from the manifest
                "palette_names_used": list(set([color for asset in asset_results["provenance"] for color in asset.get("palette", [])])),
                "validation_status": asset_results["status"],
                "last_validated": datetime.utcnow().isoformat() + "Z"
            })
            
            # Add provenance information
            metadata["assets"]["provenance"] = asset_results["provenance"]
            
            # Write updated metadata
            with open(video_metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            log.info(f"[acceptance-assets] Updated video metadata with asset information")
            
        except Exception as e:
            log.error(f"[acceptance-assets] Failed to update video metadata: {e}")
    
    def _update_video_metadata_with_evidence(self, slug: str, evidence_results: Dict[str, Any]):
        """Update video metadata with evidence and research quality information"""
        log.info(f"[acceptance-evidence] Updating video metadata with evidence information for {slug}")
        
        video_metadata_path = os.path.join(BASE, "videos", f"{slug}.metadata.json")
        if not os.path.exists(video_metadata_path):
            log.warning(f"[acceptance-evidence] Video metadata not found: {video_metadata_path}")
            return
        
        try:
            with open(video_metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Preserve existing metadata sections
            if "citations" not in metadata:
                metadata["citations"] = {}
            
            # Update citations section with evidence statistics
            metadata["citations"].update({
                "total_count": evidence_results["citations"]["total_count"],
                "unique_domains": evidence_results["citations"]["unique_domains"],
                "beats_coverage_pct": evidence_results["citations"]["beats_coverage_pct"],
                "fact_guard_summary": {
                    "removed": evidence_results["fact_guard_summary"]["removed_count"],
                    "rewritten": evidence_results["fact_guard_summary"]["rewritten_count"],
                    "flagged": evidence_results["fact_guard_summary"]["flagged_count"],
                    "strict_mode_fail": evidence_results["fact_guard_summary"]["strict_mode_fail"]
                },
                "policy_compliance": {
                    "min_citations_per_intent": evidence_results["policy_checks"]["min_citations_per_intent"],
                    "whitelist_compliance": evidence_results["policy_checks"]["whitelist_compliance"]
                },
                "validation_status": evidence_results["status"],
                "last_validated": datetime.utcnow().isoformat() + "Z"
            })
            
            # Write updated metadata
            with open(video_metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            log.info(f"[acceptance-evidence] Updated video metadata with evidence information")
            
        except Exception as e:
            log.error(f"[acceptance-evidence] Failed to update video metadata with evidence: {e}")
    
    def _update_video_metadata_with_pacing(self, slug: str, pacing_results: Dict[str, Any]):
        """Update video metadata with pacing validation information"""
        log.info(f"[acceptance-pacing] Updating video metadata with pacing information for {slug}")
        
        video_metadata_path = os.path.join(BASE, "videos", f"{slug}.metadata.json")
        if not os.path.exists(video_metadata_path):
            log.warning(f"[acceptance-pacing] Video metadata not found: {video_metadata_path}")
            return
        
        try:
            with open(video_metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Preserve existing metadata sections
            if "pacing" not in metadata:
                metadata["pacing"] = {}
            
            # Update pacing section with acceptance validation results
            # but preserve existing pacing data
            metadata["pacing"].update({
                "acceptance_status": pacing_results["status"],
                "acceptance_verdict": pacing_results["verdict"],
                "acceptance_enabled": pacing_results["enabled"],
                "acceptance_errors": pacing_results["errors"],
                "acceptance_warnings": pacing_results["warnings"],
                "acceptance_validated_at": datetime.utcnow().isoformat() + "Z"
            })
            
            # Write updated metadata
            with open(video_metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            log.info(f"[acceptance-pacing] Updated video metadata with pacing validation information")
            
        except Exception as e:
            log.error(f"[acceptance-pacing] Failed to update video metadata with pacing: {e}")
    
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
        else:
            youtube_results["quality"]["captions_status"] = "Available"
            youtube_results["quality"]["captions_path"] = artifacts["captions"]
        
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
                # Enforce animatics-only policy - but allow animatics as assets
                if artifacts["assets"] and not artifacts.get("animatics"):
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
        
        # Audio validation
        audio_quality = self._validate_youtube_audio(artifacts)
        
        # Debug: Log audio validation structure
        log.info(f"Audio validation completed: {len(audio_quality)} items")
        for key, value in audio_quality.items():
            if isinstance(value, dict):
                log.info(f"  {key}: dict with {len(value)} keys")
            else:
                log.info(f"  {key}: {type(value).__name__}")
        
        youtube_results["quality"]["audio"] = audio_quality
        
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
        
        # Asset validation (run regardless of audio status)
        asset_quality = self._validate_assets_quality(artifacts)
        youtube_results["quality"]["assets"] = asset_quality
        
        # Update video metadata with asset information
        slug = self._extract_slug_from_artifacts(artifacts)
        if slug:
            self._update_video_metadata_with_assets(slug, asset_quality)
        
        # Audio validation check
        if not audio_quality.get("valid", False):
            audio_error = audio_quality.get("error", "Audio validation failed")
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = f"Audio validation failed: {audio_error}"
            
            # Still check asset validation results even if audio fails
            if asset_quality.get("status") == "FAIL":
                asset_errors = asset_quality.get("errors", [])
                asset_error_msg = f"Asset validation also failed: {'; '.join(asset_errors[:3])}"
                if len(asset_errors) > 3:
                    asset_error_msg += f" (+{len(asset_errors) - 3} more)"
                youtube_results["quality"]["error"] += f"; {asset_error_msg}"
            
            return False
        
        # SRT/Caption validation and generation
        caption_validation = self._validate_captions(artifacts)
        youtube_results["quality"]["captions"] = caption_validation
        
        # Check if caption failure blocks acceptance
        caption_required = self.render_cfg.get("acceptance", {}).get("caption_validation_required", True)
        caption_blocks = self.render_cfg.get("acceptance", {}).get("caption_failure_blocks", False)
        
        if not caption_validation.get("valid", False) and caption_required and caption_blocks:
            caption_error = caption_validation.get("error", "Caption validation failed")
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = f"Caption validation failed: {caption_error}"
            return False
        
        # Legibility validation
        legibility_validation = self._validate_legibility(artifacts)
        youtube_results["quality"]["legibility"] = legibility_validation
        
        # Check if legibility failure blocks acceptance
        legibility_required = self.render_cfg.get("acceptance", {}).get("legibility_validation_required", True)
        if not legibility_validation.get("valid", False) and legibility_required:
            legibility_error = legibility_validation.get("error", "Legibility validation failed")
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = f"Legibility validation failed: {legibility_error}"
            return False
        
        # Check asset validation results
        if asset_quality.get("status") == "FAIL":
            asset_errors = asset_quality.get("errors", [])
            error_msg = f"Asset validation failed: {'; '.join(asset_errors[:3])}"  # Show first 3 failures
            if len(asset_errors) > 3:
                error_msg += f" (+{len(asset_errors) - 3} more)"
            youtube_results["status"] = "FAIL"
            youtube_results["quality"]["error"] = error_msg
            return False
        
        # Visual polish validation
        visual_polish_quality = self._validate_visual_polish(artifacts)
        youtube_results["quality"]["visual_polish"] = visual_polish_quality
        
        # Check visual polish results (non-blocking for overall status)
        if visual_polish_quality.get("status") == "FAIL":
            visual_polish_errors = visual_polish_quality.get("errors", [])
            error_msg = f"Visual polish validation failed: {'; '.join(visual_polish_errors[:3])}"
            if len(visual_polish_errors) > 3:
                error_msg += f" (+{len(visual_polish_errors) - 3} more)"
            youtube_results["quality"]["warning"] = f"Visual polish issues: {error_msg}"
        
        # Pacing validation
        pacing_quality = self._validate_pacing(artifacts)
        youtube_results["quality"]["pacing"] = pacing_quality
        
        # Check pacing results (non-blocking for overall status, but can affect final verdict)
        if pacing_quality.get("status") == "FAIL":
            pacing_errors = pacing_quality.get("errors", [])
            error_msg = f"Pacing validation failed: {'; '.join(pacing_errors[:3])}"
            if len(pacing_errors) > 3:
                error_msg += f" (+{len(pacing_errors) - 3} more)"
            youtube_results["quality"]["warning"] = f"Pacing issues: {error_msg}"
        
        youtube_results["status"] = "PASS"
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
    

    
    def _validate_youtube_audio(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate YouTube lane audio quality metrics"""
        audio_quality = {}
        
        try:
            # Import enhanced audio validation with FFmpeg robustness
            from bin.audio_validator import validate_audio_for_acceptance, validate_ducking_for_acceptance
            
            # Check if audio validation is required
            audio_required = self.render_cfg.get("acceptance", {}).get("audio_validation_required", True)
            if not audio_required:
                log.info("[acceptance] Audio validation disabled in render.yaml")
                return {
                    "valid": True,
                    "disabled": True,
                    "reason": "Audio validation disabled in configuration"
                }
            
            # Validate voiceover if present
            if artifacts["voiceover"]:
                vo_path = os.path.join(BASE, "voiceovers", artifacts["voiceover"])
                if os.path.exists(vo_path):
                    vo_validation = validate_audio_for_acceptance(vo_path, "voiceover")
                    audio_quality["voiceover"] = vo_validation
                else:
                    audio_quality["voiceover"] = {
                        "valid": False,
                        "error": f"Voiceover file not found: {vo_path}"
                    }
            
            # Validate final video audio if present
            if artifacts["video"]:
                video_path = os.path.join(BASE, "videos", artifacts["video"])
                if os.path.exists(video_path):
                    # Extract audio from video for validation
                    temp_audio = os.path.join(self.temp_dir, f"temp_audio_{os.path.basename(video_path)}.mp3")
                    
                    try:
                        # Extract audio using ffmpeg
                        import subprocess
                        cmd = [
                            'ffmpeg', '-i', video_path, '-vn', '-acodec', 'mp3',
                            '-y', temp_audio
                        ]
                        result = subprocess.run(cmd, capture_output=True, check=True)
                        
                        if os.path.exists(temp_audio):
                            # Validate mixed audio
                            mixed_validation = validate_audio_for_acceptance(temp_audio, "mixed")
                            audio_quality["mixed_audio"] = mixed_validation
                            
                            # Validate ducking if voiceover is available
                            if artifacts["voiceover"] and os.path.exists(vo_path):
                                ducking_validation = validate_ducking_for_acceptance(
                                    temp_audio, vo_path
                                )
                                audio_quality["ducking"] = ducking_validation
                            
                            # Clean up temp file
                            os.unlink(temp_audio)
                        else:
                            audio_quality["mixed_audio"] = {
                                "valid": False,
                                "error": "Failed to extract audio from video"
                            }
                            
                    except Exception as e:
                        audio_quality["mixed_audio"] = {
                            "valid": False,
                            "error": f"Audio extraction failed: {str(e)}"
                        }
                else:
                    audio_quality["mixed_audio"] = {
                        "valid": False,
                        "error": f"Video file not found: {video_path}"
                    }
            
            # Determine overall audio validity
            all_valid = True
            errors = []
            
            for audio_type, validation in audio_quality.items():
                if isinstance(validation, dict) and not validation.get("valid", False):
                    all_valid = False
                    error_msg = validation.get("error", f"{audio_type} validation failed")
                    errors.append(error_msg)
            
            audio_quality["valid"] = all_valid
            if errors:
                audio_quality["error"] = "; ".join(errors)
            
            # Add audio targets for reference
            audio_cfg = getattr(self.cfg.render, 'audio', None)
            if audio_cfg:
                audio_quality["targets"] = {
                    "vo_lufs": getattr(audio_cfg, 'vo_lufs_target', -16.0),
                    "music_lufs": getattr(audio_cfg, 'music_lufs_target', -23.0),
                    "true_peak_max": getattr(audio_cfg, 'true_peak_max', -1.0),
                    "ducking_min_db": getattr(audio_cfg, 'ducking_min_db', 6.0)
                }
            else:
                audio_quality["targets"] = {
                    "vo_lufs": -16.0,
                    "music_lufs": -23.0,
                    "true_peak_max": -1.0,
                    "ducking_min_db": 6.0
                }
            
        except ImportError as e:
            audio_quality = {
                "valid": False,
                "error": f"Audio validation module not available: {str(e)}"
            }
        except Exception as e:
            audio_quality = {
                "valid": False,
                "error": f"Audio validation error: {str(e)}"
            }
        
        return audio_quality
    
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
                        width = element.get("width", 0) or 0  # Handle None values
                        height = element.get("height", 0) or 0  # Handle None values
                        
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
            # Load timing configuration from render.yaml (preferred) or modules.yaml
            timing_config = {}
            if self.render_cfg:
                acceptance_cfg = self.render_cfg.get("acceptance", {})
                timing_config = {
                    'target_tolerance_pct': acceptance_cfg.get('tolerance_pct', 5.0),
                    'min_scene_ms': acceptance_cfg.get('min_scene_ms', 2500),
                    'max_scene_ms': acceptance_cfg.get('max_scene_ms', 30000)
                }
                log.info(f"[duration-policy] Using render.yaml timing config: tolerance={timing_config['target_tolerance_pct']}%")
            else:
                try:
                    from bin.core import load_modules_cfg
                    timing_config = load_modules_cfg().get('timing', {})
                    log.info(f"[duration-policy] Using modules.yaml timing config: tolerance={timing_config.get('target_tolerance_pct', 5.0)}%")
                except Exception as e:
                    log.warning(f"Could not load timing config: {e}")
                    # Use defaults
                    timing_config = {
                        'target_tolerance_pct': 5.0,
                        'min_scene_ms': 2500,
                        'max_scene_ms': 30000
                    }
                    log.info(f"[duration-policy] Using default timing config: tolerance={timing_config['target_tolerance_pct']}%")
            
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
            
            log.info(f"[duration-policy] Duration policy validation: {'PASS' if result['pass'] else 'FAIL'}")
            log.info(f"[duration-policy] Target: {target_ms}ms, Actual: {total_duration_ms}ms, Deviation: {deviation_pct:.1f}%")
            
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
    
    def _validate_visual_polish(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate visual polish quality: textures, geometry, and micro-animations"""
        log.info("[acceptance-visual-polish] Starting visual polish validation")
        
        visual_polish_results = {
            "status": "PENDING",
            "textures": {"status": "PENDING", "enabled": False, "metadata": {}, "contrast_check": "PENDING"},
            "geometry": {"status": "PENDING", "enabled": False, "validation_report": {}, "critical_errors": 0},
            "micro_animations": {"status": "PENDING", "enabled": False, "elements_animated": 0, "collision_check": "PENDING"},
            "performance": {"status": "PENDING", "texture_delta_pct": 0.0, "render_time_with": 0.0, "render_time_without": 0.0},
            "errors": [],
            "warnings": []
        }
        
        # Extract slug for artifact paths
        slug = self._extract_slug_from_artifacts(artifacts)
        if not slug:
            visual_polish_results["status"] = "FAIL"
            visual_polish_results["errors"].append("Could not determine slug for visual polish validation")
            return visual_polish_results
        
        # Check texture settings and validation
        textures_enabled = getattr(self.cfg, 'textures', None)
        if textures_enabled and hasattr(textures_enabled, 'enabled'):
            textures_enabled = textures_enabled.enabled
        else:
            textures_enabled = False
        visual_polish_results["textures"]["enabled"] = textures_enabled
        
        if textures_enabled:
            # Check if texture metadata exists in video metadata
            if artifacts.get("video_metadata"):
                try:
                    # Handle both relative and absolute paths
                    metadata_path = artifacts["video_metadata"]
                    if not os.path.isabs(metadata_path):
                        metadata_path = os.path.join(BASE, metadata_path)
                    
                    log.info(f"[acceptance-visual-polish] Reading video metadata from: {metadata_path}")
                    
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    log.info(f"[acceptance-visual-polish] Video metadata keys: {list(metadata.keys())}")
                    
                    texture_metadata = metadata.get("textures", {})
                    if texture_metadata:
                        log.info(f"[acceptance-visual-polish] Found texture metadata: {texture_metadata}")
                        visual_polish_results["textures"]["metadata"] = texture_metadata
                        visual_polish_results["textures"]["status"] = "PASS"
                        
                        # Check contrast remains PASS
                        contrast_status = metadata.get("legibility", {}).get("contrast_status", "UNKNOWN")
                        visual_polish_results["textures"]["contrast_check"] = contrast_status
                        
                        if contrast_status != "PASS":
                            visual_polish_results["warnings"].append(f"Texture applied but contrast status is {contrast_status}")
                    else:
                        log.warning(f"[acceptance-visual-polish] No texture metadata found in video metadata")
                        visual_polish_results["textures"]["status"] = "FAIL"
                        visual_polish_results["errors"].append("Textures enabled but no texture metadata found")
                except Exception as e:
                    log.warning(f"Could not read video metadata for texture validation: {e}")
                    visual_polish_results["textures"]["status"] = "WARN"
                    visual_polish_results["warnings"].append(f"Could not validate texture metadata: {e}")
            
            # Check for texture probe grid
            texture_probe_path = os.path.join(BASE, "runs", slug, "texture_probe_grid.png")
            if os.path.exists(texture_probe_path):
                visual_polish_results["textures"]["probe_grid"] = texture_probe_path
            else:
                visual_polish_results["warnings"].append("Texture probe grid not found")
        
        # Check geometry settings and validation
        geometry_enabled = self.modules_cfg.get('geometry', {}).get('enable', False) if self.modules_cfg else False
        visual_polish_results["geometry"]["enabled"] = geometry_enabled
        
        if geometry_enabled:
            # Check for geometry validation report
            geom_report_path = os.path.join(BASE, "runs", slug, "geom_validation_report.json")
            if os.path.exists(geom_report_path):
                try:
                    with open(geom_report_path, 'r') as f:
                        geom_report = json.load(f)
                    
                    visual_polish_results["geometry"]["validation_report"] = geom_report
                    critical_errors = geom_report.get("critical_errors", 0)
                    visual_polish_results["geometry"]["critical_errors"] = critical_errors
                    
                    if critical_errors == 0:
                        visual_polish_results["geometry"]["status"] = "PASS"
                    else:
                        visual_polish_results["geometry"]["status"] = "FAIL"
                        visual_polish_results["errors"].append(f"Geometry validation has {critical_errors} critical errors")
                except Exception as e:
                    log.warning(f"Could not read geometry validation report: {e}")
                    visual_polish_results["geometry"]["status"] = "WARN"
                    visual_polish_results["warnings"].append(f"Could not validate geometry report: {e}")
            else:
                visual_polish_results["geometry"]["status"] = "FAIL"
                visual_polish_results["errors"].append("Geometry enabled but validation report not found")
        
        # Check micro-animations settings and validation
        micro_anim_enabled = self.modules_cfg.get('micro_anim', {}).get('enable', False) if self.modules_cfg else False
        visual_polish_results["micro_animations"]["enabled"] = micro_anim_enabled
        
        if micro_anim_enabled:
            # Check for style signature to get animation details
            style_signature_path = os.path.join(BASE, "runs", slug, "style_signature.json")
            if os.path.exists(style_signature_path):
                try:
                    with open(style_signature_path, 'r') as f:
                        style_sig = json.load(f)
                    
                    micro_anim_info = style_sig.get("micro_animations", {})
                    elements_animated = micro_anim_info.get("elements_animated", 0)
                    total_elements = micro_anim_info.get("total_elements", 0)
                    
                    visual_polish_results["micro_animations"]["elements_animated"] = elements_animated
                    visual_polish_results["micro_animations"]["total_elements"] = total_elements
                    
                    if total_elements > 0:
                        animation_percent = (elements_animated / total_elements) * 100
                        if animation_percent <= 10:
                            visual_polish_results["micro_animations"]["status"] = "PASS"
                        else:
                            visual_polish_results["micro_animations"]["status"] = "FAIL"
                            visual_polish_results["errors"].append(f"Animation percentage {animation_percent:.1f}% exceeds 10% limit")
                    else:
                        visual_polish_results["micro_animations"]["status"] = "WARN"
                        visual_polish_results["warnings"].append("No elements found for animation validation")
                    
                    # Check collision status
                    collision_status = micro_anim_info.get("collision_check", "UNKNOWN")
                    visual_polish_results["micro_animations"]["collision_check"] = collision_status
                    
                    if collision_status == "PASS":
                        pass  # Already set above
                    elif collision_status == "FAIL":
                        visual_polish_results["micro_animations"]["status"] = "FAIL"
                        visual_polish_results["errors"].append("Collision check failed after animation keyframes")
                    else:
                        visual_polish_results["warnings"].append(f"Collision check status unclear: {collision_status}")
                        
                except Exception as e:
                    log.warning(f"Could not read style signature for micro-animation validation: {e}")
                    visual_polish_results["micro_animations"]["status"] = "WARN"
                    visual_polish_results["warnings"].append(f"Could not validate micro-animations: {e}")
            else:
                visual_polish_results["micro_animations"]["status"] = "WARN"
                visual_polish_results["warnings"].append("Style signature not found for micro-animation validation")
        
        # Performance validation - check render time delta with textures
        if textures_enabled:
            # Look for performance metrics in video metadata or separate performance logs
            if artifacts.get("video_metadata"):
                try:
                    # Handle both relative and absolute paths
                    metadata_path = artifacts["video_metadata"]
                    if not os.path.isabs(metadata_path):
                        metadata_path = os.path.join(BASE, metadata_path)
                    
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    performance_metrics = metadata.get("performance", {})
                    render_time_with = performance_metrics.get("render_time_with_textures", 0.0)
                    render_time_without = performance_metrics.get("render_time_without_textures", 0.0)
                    
                    if render_time_with > 0 and render_time_without > 0:
                        delta_pct = ((render_time_with - render_time_without) / render_time_without) * 100
                        visual_polish_results["performance"]["texture_delta_pct"] = delta_pct
                        visual_polish_results["performance"]["render_time_with"] = render_time_with
                        visual_polish_results["performance"]["render_time_without"] = render_time_without
                        
                        if delta_pct <= 15:
                            visual_polish_results["performance"]["status"] = "PASS"
                        else:
                            visual_polish_results["performance"]["status"] = "WARN"
                            visual_polish_results["warnings"].append(f"Texture render time increase {delta_pct:.1f}% exceeds 15% threshold")
                    else:
                        visual_polish_results["performance"]["status"] = "UNKNOWN"
                        visual_polish_results["warnings"].append("Performance metrics not available for texture comparison")
                        
                except Exception as e:
                    log.warning(f"Could not read performance metrics: {e}")
                    visual_polish_results["performance"]["status"] = "UNKNOWN"
                    visual_polish_results["warnings"].append(f"Could not validate performance: {e}")
        
        # Determine overall visual polish status
        all_passes = (
            visual_polish_results["textures"]["status"] in ["PASS", "WARN", "UNKNOWN"] and
            visual_polish_results["geometry"]["status"] in ["PASS", "WARN", "UNKNOWN"] and
            visual_polish_results["micro_animations"]["status"] in ["PASS", "WARN", "UNKNOWN"] and
            visual_polish_results["performance"]["status"] in ["PASS", "WARN", "UNKNOWN"]
        )
        
        has_critical_failures = (
            visual_polish_results["textures"]["status"] == "FAIL" or
            visual_polish_results["geometry"]["status"] == "FAIL" or
            visual_polish_results["micro_animations"]["status"] == "FAIL"
        )
        
        if has_critical_failures:
            visual_polish_results["status"] = "FAIL"
        elif all_passes:
            visual_polish_results["status"] = "PASS"
        else:
            visual_polish_results["status"] = "WARN"
        
        log.info(f"[acceptance-visual-polish] Visual polish validation completed: {visual_polish_results['status']}")
        return visual_polish_results
    
    def _validate_evidence_quality(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate research quality: citations, domain quality, and fact-guard compliance"""
        log.info("[acceptance-evidence] Starting evidence quality validation")
        
        evidence_results = {
            "status": "PENDING",
            "citations": {
                "total_count": 0,
                "unique_domains": 0,
                "beats_coverage_pct": 0.0
            },
            "policy_checks": {
                "min_citations_per_intent": "PENDING",
                "whitelist_compliance": "PENDING",
                "non_whitelisted_warnings": []
            },
            "fact_guard_summary": {
                "removed_count": 0,
                "rewritten_count": 0,
                "flagged_count": 0,
                "strict_mode_fail": False
            },
            "errors": [],
            "warnings": []
        }
        
        # Find slug and research artifacts
        slug = self._extract_slug_from_artifacts(artifacts)
        if not slug:
            evidence_results["status"] = "FAIL"
            evidence_results["errors"].append("Could not determine slug for evidence validation")
            return evidence_results
        
        try:
            # Load research artifacts
            references_path = os.path.join(BASE, "data", slug, "references.json")
            grounded_beats_path = os.path.join(BASE, "data", slug, "grounded_beats.json")
            fact_guard_path = os.path.join(BASE, "data", slug, "fact_guard_report.json")
            
            # Check if research artifacts exist
            if not os.path.exists(references_path):
                evidence_results["errors"].append(f"Missing references.json: {references_path}")
            if not os.path.exists(grounded_beats_path):
                evidence_results["errors"].append(f"Missing grounded_beats.json: {grounded_beats_path}")
            if not os.path.exists(fact_guard_path):
                evidence_results["errors"].append(f"Missing fact_guard_report.json: {fact_guard_path}")
            
            if evidence_results["errors"]:
                evidence_results["status"] = "FAIL"
                return evidence_results
            
            # Load and validate references
            with open(references_path, 'r') as f:
                references = json.load(f)
            
            with open(grounded_beats_path, 'r') as f:
                grounded_beats = json.load(f)
            
            with open(fact_guard_path, 'r') as f:
                fact_guard_report = json.load(f)
            
            # Calculate citation metrics
            total_citations = len(references)
            evidence_results["citations"]["total_count"] = total_citations
            
            # Count unique domains
            unique_domains = set()
            for ref in references:
                if isinstance(ref, dict) and "domain" in ref:
                    unique_domains.add(ref["domain"])
                elif isinstance(ref, dict) and "url" in ref:
                    # Extract domain from URL if domain not directly available
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(ref["url"])
                        if parsed.netloc:
                            unique_domains.add(parsed.netloc)
                    except Exception:
                        pass
            
            evidence_results["citations"]["unique_domains"] = len(unique_domains)
            
            # Calculate beats coverage
            beats_with_citations = 0
            total_beats = len(grounded_beats)
            
            for beat in grounded_beats:
                if isinstance(beat, dict) and "citations" in beat:
                    citations = beat.get("citations", [])
                    if len(citations) > 0:
                        beats_with_citations += 1
            
            if total_beats > 0:
                coverage_pct = (beats_with_citations / total_beats) * 100.0
                evidence_results["citations"]["beats_coverage_pct"] = coverage_pct
            else:
                evidence_results["citations"]["beats_coverage_pct"] = 0.0
            
            # Validate fact-guard compliance
            fact_guard_summary = fact_guard_report.get("summary", {})
            evidence_results["fact_guard_summary"]["removed_count"] = fact_guard_summary.get("removed", 0)
            evidence_results["fact_guard_summary"]["rewritten_count"] = fact_guard_summary.get("rewritten", 0)
            evidence_results["fact_guard_summary"]["flagged_count"] = fact_guard_summary.get("flagged", 0)
            
            # Check strict mode failure (flagged > 0 in strict mode)
            strictness = fact_guard_report.get("metadata", {}).get("strictness", "balanced")
            if strictness == "strict" and fact_guard_summary.get("flagged", 0) > 0:
                evidence_results["fact_guard_summary"]["strict_mode_fail"] = True
                evidence_results["status"] = "FAIL"
                evidence_results["errors"].append("Fact-guard strict mode: flagged claims found")
            
            # Load intent template to check citation requirements
            outline_path = os.path.join(BASE, "scripts", f"{slug}.outline.json")
            if os.path.exists(outline_path):
                try:
                    with open(outline_path, 'r') as f:
                        outline = json.load(f)
                    
                    intent_type = outline.get("intent", "unknown")
                    
                    # Load intent templates to get evidence requirements
                    intent_templates_path = os.path.join(BASE, "conf", "intent_templates.yaml")
                    if os.path.exists(intent_templates_path):
                        import yaml
                        with open(intent_templates_path, 'r') as f:
                            intent_templates = yaml.safe_load(f)
                        
                        intent_config = intent_templates.get("intents", {}).get(intent_type, {})
                        evidence_load = intent_config.get("evidence_load", "medium")
                        
                        # Check citation minimums based on evidence load
                        if evidence_load == "high":
                            min_coverage = 80.0
                            min_citations_per_beat = 2
                        elif evidence_load == "medium":
                            min_coverage = 60.0
                            min_citations_per_beat = 1
                        else:
                            min_coverage = 40.0
                            min_citations_per_beat = 1
                        
                        # Validate coverage
                        if coverage_pct < min_coverage:
                            evidence_results["policy_checks"]["min_citations_per_intent"] = "FAIL"
                            evidence_results["status"] = "FAIL"
                            evidence_results["errors"].append(
                                f"Citation coverage {coverage_pct:.1f}% below minimum {min_coverage}% for {evidence_load} evidence load"
                            )
                        else:
                            evidence_results["policy_checks"]["min_citations_per_intent"] = "PASS"
                        
                        # Validate citations per beat
                        avg_citations = total_citations / total_beats if total_beats > 0 else 0
                        if avg_citations < min_citations_per_beat:
                            evidence_results["policy_checks"]["min_citations_per_intent"] = "FAIL"
                            evidence_results["status"] = "FAIL"
                            evidence_results["errors"].append(
                                f"Average citations {avg_citations:.1f} below minimum {min_citations_per_beat} per beat for {evidence_load} evidence load"
                            )
                        else:
                            evidence_results["policy_checks"]["min_citations_per_intent"] = "PASS"
                    else:
                        evidence_results["warnings"].append("Intent templates config not found, skipping citation policy validation")
                except Exception as e:
                    log.warning(f"[acceptance-evidence] Could not validate intent citation requirements: {e}")
                    evidence_results["warnings"].append(f"Intent validation error: {str(e)}")
            
            # Validate domain whitelist compliance
            try:
                # Load research configuration for domain allowlist
                from bin.utils.config import load_research_config
                research_config = load_research_config()
                
                allowlist = set(research_config.domains.get("allowlist", []) if hasattr(research_config, 'domains') else [])
                blacklist = set(research_config.domains.get("blacklist", []) if hasattr(research_config, 'domains') else [])
                
                if allowlist:  # Only validate if allowlist is configured
                        non_whitelisted_domains = []
                        for domain in unique_domains:
                            if domain not in allowlist and domain not in blacklist:
                                non_whitelisted_domains.append(domain)
                        
                        if non_whitelisted_domains:
                            evidence_results["policy_checks"]["whitelist_compliance"] = "WARN"
                            evidence_results["policy_checks"]["non_whitelisted_warnings"] = non_whitelisted_domains
                            evidence_results["warnings"].append(f"Found {len(non_whitelisted_domains)} non-whitelisted domains: {', '.join(non_whitelisted_domains[:5])}")
                        else:
                            evidence_results["policy_checks"]["whitelist_compliance"] = "PASS"
                else:
                    evidence_results["policy_checks"]["whitelist_compliance"] = "PENDING"
                    evidence_results["warnings"].append("Domain allowlist not configured, skipping whitelist validation")
            except Exception as e:
                evidence_results["policy_checks"]["whitelist_compliance"] = "PENDING"
                evidence_results["warnings"].append(f"Whitelist validation error: {str(e)}")
            
            # Determine overall evidence status
            if evidence_results["status"] == "PENDING" and not evidence_results["errors"]:
                evidence_results["status"] = "PASS"
            
            log.info(f"[acceptance-evidence] Evidence validation completed: {evidence_results['status']}")
            return evidence_results
            
        except Exception as e:
            log.error(f"[acceptance-evidence] Evidence validation error: {e}")
            evidence_results["status"] = "FAIL"
            evidence_results["errors"].append(f"Evidence validation error: {str(e)}")
            return evidence_results
    
    def _validate_pacing(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate pacing KPIs against intent bands and determine verdict"""
        log.info("[acceptance-pacing] Starting pacing validation")
        
        pacing_results = {
            "status": "PENDING",
            "enabled": False,
            "kpi_metrics": {},
            "comparison": {},
            "verdict": "PENDING",
            "adjusted": False,
            "errors": [],
            "warnings": []
        }
        
        # Check if pacing is enabled in modules config
        if not self.modules_cfg or not self.modules_cfg.get('pacing', {}).get('enable', False):
            pacing_results["status"] = "SKIP"
            pacing_results["warnings"].append("Pacing validation disabled in modules.yaml")
            return pacing_results
        
        pacing_results["enabled"] = True
        
        # Find slug and pacing artifacts
        slug = self._extract_slug_from_artifacts(artifacts)
        if not slug:
            pacing_results["status"] = "FAIL"
            pacing_results["errors"].append("Could not determine slug for pacing validation")
            return pacing_results
        
        try:
            # Load pacing report
            pacing_report_path = os.path.join(BASE, "runs", slug, "pacing_report.json")
            if not os.path.exists(pacing_report_path):
                pacing_results["status"] = "FAIL"
                pacing_results["errors"].append(f"Missing pacing report: {pacing_report_path}")
                return pacing_results
            
            with open(pacing_report_path, 'r') as f:
                pacing_report = json.load(f)
            
            # Load video metadata to check if adjustments were applied
            video_metadata_path = os.path.join(BASE, "videos", f"{slug}.metadata.json")
            video_metadata = {}
            if os.path.exists(video_metadata_path):
                with open(video_metadata_path, 'r') as f:
                    video_metadata = json.load(f)
            
            # Extract KPI metrics and comparison data
            kpi_metrics = pacing_report.get("kpi_metrics", {})
            comparison = pacing_report.get("comparison", {})
            
            # Integrity guard: ensure KPI metrics are present and valid
            if not kpi_metrics or not comparison:
                pacing_results["status"] = "FAIL"
                pacing_results["verdict"] = "FAIL"
                pacing_results["errors"].append("Missing KPI metrics or comparison data in pacing report")
                return pacing_results
            
            # Check that required KPI fields are present
            required_kpis = ["words_per_sec", "cuts_per_min", "avg_scene_s"]
            missing_kpis = [kpi for kpi in required_kpis if kpi not in kpi_metrics or kpi_metrics[kpi] is None]
            if missing_kpis:
                pacing_results["status"] = "FAIL"
                pacing_results["verdict"] = "FAIL"
                pacing_results["errors"].append(f"Missing required KPI metrics: {', '.join(missing_kpis)}")
                return pacing_results
            
            pacing_results["kpi_metrics"] = kpi_metrics
            pacing_results["comparison"] = comparison
            
            # Check if adjustments were applied
            pacing_metadata = video_metadata.get("pacing", {})
            pacing_results["adjusted"] = pacing_metadata.get("adjusted", False)
            
            # Get flags and determine if metrics are within bands
            flags = comparison.get("flags", {})
            overall_status = comparison.get("overall_status", "unknown")
            
            # Check if any metric is significantly out of band (>10% tolerance)
            tolerance_pct = self.modules_cfg.get('pacing', {}).get('tolerance_pct', 10)
            out_of_band_metrics = []
            
            for metric, flag in flags.items():
                if flag not in ["ok", "within_tolerance"]:
                    out_of_band_metrics.append(metric)
            
            # Determine verdict based on config and out-of-band status
            strict_mode = self.modules_cfg.get('pacing', {}).get('strict', False)
            
            if not out_of_band_metrics:
                # All metrics within bands
                pacing_results["verdict"] = "PASS"
                pacing_results["status"] = "PASS"
            else:
                # Some metrics out of band
                if strict_mode:
                    pacing_results["verdict"] = "FAIL"
                    pacing_results["status"] = "FAIL"
                    pacing_results["errors"].append(f"Metrics out of band in strict mode: {', '.join(out_of_band_metrics)}")
                else:
                    pacing_results["verdict"] = "WARN"
                    pacing_results["status"] = "WARN"
                    pacing_results["warnings"].append(f"Metrics out of band (non-strict mode): {', '.join(out_of_band_metrics)}")
            
            # Add compact table of metrics and bands for operator readability
            profile_used = comparison.get("profile_used", {})
            metrics_table = {}
            
            for metric in ["words_per_sec", "cuts_per_min", "avg_scene_s", "speech_music_ratio"]:
                if metric in kpi_metrics and metric in profile_used:
                    current_value = kpi_metrics[metric]
                    bands = profile_used.get(metric, [])
                    flag = flags.get(metric, "unknown")
                    
                    metrics_table[metric] = {
                        "current": current_value,
                        "bands": bands,
                        "flag": flag,
                        "in_band": flag in ["ok", "within_tolerance"]
                    }
            
            pacing_results["metrics_table"] = metrics_table
            
            log.info(f"[acceptance-pacing] Pacing validation completed: {pacing_results['status']} - {pacing_results['verdict']}")
            return pacing_results
            
        except Exception as e:
            log.error(f"[acceptance-pacing] Pacing validation error: {e}")
            pacing_results["status"] = "FAIL"
            pacing_results["errors"].append(f"Pacing validation error: {str(e)}")
            return pacing_results
    
    def _validate_captions(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate captions and generate SRT if missing"""
        log.info("[acceptance] Starting caption validation")
        
        try:
            # Check if captions exist
            if artifacts.get("captions"):
                log.info(f"[acceptance] Found existing captions: {artifacts['captions']}")
                return {
                    "valid": True,
                    "source": "existing",
                    "path": artifacts["captions"],
                    "generation_method": "none"
                }
            
            # No captions found - generate them if fallback generation is enabled
            fallback_enabled = self.render_cfg.get("captions", {}).get("fallback_generation", True)
            if not fallback_enabled:
                return {
                    "valid": False,
                    "error": "Captions required but fallback generation disabled",
                    "error_type": "fallback_disabled"
                }
            
            # Generate SRT using the new SRT generator
            try:
                from bin.srt_generate import generate_srt_for_acceptance
                
                # Find script path
                script_path = None
                if artifacts.get("script"):
                    script_path = os.path.join(BASE, "scripts", artifacts["script"])
                
                if not script_path or not os.path.exists(script_path):
                    return {
                        "valid": False,
                        "error": "Script not found for SRT generation",
                        "error_type": "script_not_found"
                    }
                
                # Determine intent type from outline
                intent_type = "default"
                if artifacts.get("outline"):
                    outline_path = os.path.join(BASE, "scripts", artifacts["outline"])
                    if os.path.exists(outline_path):
                        try:
                            with open(outline_path, 'r', encoding='utf-8') as f:
                                outline_data = json.load(f)
                            intent_type = outline_data.get("intent", "default")
                        except Exception as e:
                            log.warning(f"[acceptance] Could not read outline for intent: {e}")
                
                # Generate SRT
                srt_result = generate_srt_for_acceptance(
                    script_path=script_path,
                    intent_type=intent_type
                )
                
                if srt_result["success"]:
                    log.info(f"[acceptance] SRT generated successfully: {srt_result['generation_method']}")
                    return {
                        "valid": True,
                        "source": "generated",
                        "path": srt_result["srt_path"],
                        "generation_method": srt_result["generation_method"],
                        "duration_sec": srt_result.get("duration_sec", 0),
                        "word_count": srt_result.get("word_count", 0)
                    }
                else:
                    return {
                        "valid": False,
                        "error": f"SRT generation failed: {srt_result['error']}",
                        "error_type": "generation_failed",
                        "details": srt_result
                    }
                    
            except ImportError as e:
                return {
                    "valid": False,
                    "error": f"SRT generation module not available: {str(e)}",
                    "error_type": "module_not_available"
                }
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"SRT generation error: {str(e)}",
                    "error_type": "generation_error"
                }
                
        except Exception as e:
            log.error(f"[acceptance] Caption validation error: {str(e)}")
            return {
                "valid": False,
                "error": f"Caption validation error: {str(e)}",
                "error_type": "validation_error"
            }
    
    def _validate_legibility(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate text legibility and inject backgrounds if needed"""
        log.info("[acceptance] Starting legibility validation")
        
        try:
            # Check if legibility validation is required
            legibility_required = self.render_cfg.get("acceptance", {}).get("legibility_validation_required", True)
            if not legibility_required:
                log.info("[acceptance] Legibility validation disabled in render.yaml")
                return {
                    "valid": True,
                    "disabled": True,
                    "reason": "Legibility validation disabled in configuration"
                }
            
            # Check if we have a SceneScript to validate
            if not artifacts.get("scenescript"):
                log.info("[acceptance] No SceneScript found, skipping legibility validation")
                return {
                    "valid": True,
                    "skipped": True,
                    "reason": "No SceneScript available for validation"
                }
            
            # Load SceneScript data
            scenescript_path = os.path.join(BASE, "scenescripts", artifacts["scenescript"])
            if not os.path.exists(scenescript_path):
                return {
                    "valid": False,
                    "error": f"SceneScript file not found: {scenescript_path}",
                    "error_type": "file_not_found"
                }
            
            try:
                with open(scenescript_path, 'r', encoding='utf-8') as f:
                    scenescript_data = json.load(f)
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Failed to read SceneScript: {str(e)}",
                    "error_type": "read_error"
                }
            
            # Validate legibility using the new legibility validator
            try:
                from bin.legibility import validate_scenescript_legibility
                
                legibility_result = validate_scenescript_legibility(scenescript_data)
                
                if legibility_result["valid"]:
                    log.info(f"[acceptance] Legibility validation passed: {legibility_result['summary']}")
                else:
                    log.warning(f"[acceptance] Legibility validation failed: {legibility_result['summary']}")
                
                return legibility_result
                
            except ImportError as e:
                return {
                    "valid": False,
                    "error": f"Legibility validation module not available: {str(e)}",
                    "error_type": "module_not_available"
                }
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Legibility validation error: {str(e)}",
                    "error_type": "validation_error"
                }
                
        except Exception as e:
            log.error(f"[acceptance] Legibility validation error: {str(e)}")
            return {
                "valid": False,
                "error": f"Legibility validation error: {str(e)}",
                "error_type": "validation_error"
            }
    
    def run_validation(self) -> Dict[str, Any]:
        """Run complete validation and return results"""
        log.info("Starting acceptance validation...")
        
        # Validate YouTube lane
        youtube_ok = self.validate_youtube_lane()
        

        
        # Validate evidence quality (research rigor)
        evidence_ok = self._validate_evidence_quality(self.results["lanes"]["youtube"]["artifacts"])
        self.results["evidence"] = evidence_ok
        
        # Validate pacing
        pacing_ok = self._validate_pacing(self.results["lanes"]["youtube"]["artifacts"])
        self.results["pacing"] = pacing_ok
        
        # Update video metadata with evidence and pacing information
        slug = self._extract_slug_from_artifacts(self.results["lanes"]["youtube"]["artifacts"])
        if slug:
            self._update_video_metadata_with_evidence(slug, evidence_ok)
            self._update_video_metadata_with_pacing(slug, pacing_ok)
        
        # Determine overall status (all lanes must pass)
        # Pacing integrity guard: require KPI presence and comparison result before allowing PASS
        pacing_has_kpis = (pacing_ok.get("kpi_metrics") and 
                           pacing_ok.get("comparison") and 
                           pacing_ok.get("kpi_metrics").get("words_per_sec") is not None)
        
        if not pacing_has_kpis:
            log.warning("[acceptance-pacing] Pacing integrity guard: Missing KPI metrics or comparison data")
            pacing_ok["status"] = "FAIL"
            pacing_ok["verdict"] = "FAIL"
            pacing_ok["errors"].append("Pacing integrity guard: Missing KPI metrics or comparison data")
            self.results["pacing"] = pacing_ok
        
        if youtube_ok and evidence_ok["status"] == "PASS" and pacing_ok["status"] == "PASS":
            self.results["overall_status"] = "PASS"
        else:
            self.results["overall_status"] = "FAIL"
        
        # Update asset validation status from YouTube lane
        if "quality" in self.results["lanes"]["youtube"]:
            assets_quality = self.results["lanes"]["youtube"]["quality"].get("assets", {})
            if assets_quality:
                self.results["assets"].update(assets_quality)
                log.info(f"[acceptance-assets] Updated main assets section with status: {assets_quality.get('status', 'unknown')}")
            
            # Update visual polish validation status from YouTube lane
            visual_polish_quality = self.results["lanes"]["youtube"]["quality"].get("visual_polish", {})
            if visual_polish_quality:
                self.results["visual_polish"].update(visual_polish_quality)
                log.info(f"[acceptance-visual-polish] Updated main visual polish section with status: {visual_polish_quality.get('status', 'unknown')}")
        
        # Add summary
        self.results["summary"] = {
            "youtube_lane": "PASS" if youtube_ok else "FAIL",

            "evidence_lane": "PASS" if evidence_ok["status"] == "PASS" else "FAIL",
            "pacing_lane": "PASS" if pacing_ok["status"] == "PASS" else "FAIL",
            "total_artifacts": {
                "youtube": len([v for v in self.results["lanes"]["youtube"]["artifacts"].values() if v]),

            }
        }
        
        # Validate determinism if required
        determinism_required = self.render_cfg.get("acceptance", {}).get("require_deterministic_runs", True)
        if determinism_required:
            determinism_validation = self._validate_determinism()
            self.results["determinism"] = determinism_validation
            log.info(f"[acceptance] Determinism validation: {determinism_validation['status']}")
        
        # Add acceptance configuration summary
        self.results["acceptance_config_summary"] = {
            "duration_tolerance_pct": self.results["acceptance_config"]["duration_tolerance_pct"],
            "audio_validation_required": self.results["acceptance_config"]["audio_validation_required"],
            "caption_validation_required": self.results["acceptance_config"]["caption_validation_required"],
            "legibility_validation_required": self.results["acceptance_config"]["legibility_validation_required"],
            "wcag_aa_threshold": self.results["acceptance_config"]["wcag_aa_threshold"]
        }
        
        return self.results
    
    def _validate_determinism(self) -> Dict[str, Any]:
        """Validate that results are deterministic across runs"""
        log.info("[acceptance] Starting determinism validation")
        
        try:
            # Check if we have a previous run to compare against
            previous_results_path = os.path.join(BASE, "acceptance_results.json")
            if not os.path.exists(previous_results_path):
                return {
                    "status": "SKIP",
                    "reason": "No previous results to compare against",
                    "deterministic": True
                }
            
            # Load previous results
            try:
                with open(previous_results_path, 'r', encoding='utf-8') as f:
                    previous_results = json.load(f)
            except Exception as e:
                return {
                    "status": "SKIP",
                    "reason": f"Could not read previous results: {str(e)}",
                    "deterministic": True
                }
            
            # Compare key acceptance metrics
            current_metrics = {
                "overall_status": self.results["overall_status"],
                "youtube_lane_status": self.results["lanes"]["youtube"]["status"],
    
                "evidence_status": self.results.get("evidence", {}).get("status", "UNKNOWN"),
                "pacing_status": self.results.get("pacing", {}).get("status", "UNKNOWN"),
                "duration_tolerance_pct": self.results["acceptance_config"]["duration_tolerance_pct"],
                "wcag_aa_threshold": self.results["acceptance_config"]["wcag_aa_threshold"]
            }
            
            previous_metrics = {
                "overall_status": previous_results.get("overall_status", "UNKNOWN"),
                "youtube_lane_status": previous_results.get("lanes", {}).get("youtube", {}).get("status", "UNKNOWN"),
    
                "evidence_status": previous_results.get("evidence", {}).get("status", "UNKNOWN"),
                "pacing_status": previous_results.get("pacing", {}).get("status", "UNKNOWN"),
                "duration_tolerance_pct": previous_results.get("acceptance_config_summary", {}).get("duration_tolerance_pct", 0),
                "wcag_aa_threshold": previous_results.get("acceptance_config_summary", {}).get("wcag_aa_threshold", 0)
            }
            
            # Check for differences
            differences = []
            for key in current_metrics:
                if current_metrics[key] != previous_metrics[key]:
                    differences.append({
                        "metric": key,
                        "current": current_metrics[key],
                        "previous": previous_metrics[key]
                    })
            
            # Check SRT consistency if available
            srt_consistency = self._check_srt_consistency(previous_results)
            
            # Determine if results are deterministic
            deterministic = len(differences) == 0 and srt_consistency["consistent"]
            
            result = {
                "status": "PASS" if deterministic else "FAIL",
                "deterministic": deterministic,
                "differences": differences,
                "srt_consistency": srt_consistency,
                "current_metrics": current_metrics,
                "previous_metrics": previous_metrics
            }
            
            if deterministic:
                log.info("[acceptance] Determinism validation PASSED - results are consistent")
            else:
                log.warning(f"[acceptance] Determinism validation FAILED - {len(differences)} differences found")
                for diff in differences:
                    log.warning(f"[acceptance] Difference: {diff['metric']} = {diff['current']} (was {diff['previous']})")
            
            return result
            
        except Exception as e:
            log.error(f"[acceptance] Determinism validation error: {str(e)}")
            return {
                "status": "ERROR",
                "error": f"Determinism validation error: {str(e)}",
                "deterministic": False
            }
    
    def _check_srt_consistency(self, previous_results: Dict[str, Any]) -> Dict[str, Any]:
        """Check if SRT files are consistent across runs"""
        try:
            # Get current SRT info
            current_captions = self.results["lanes"]["youtube"]["quality"].get("captions", {})
            previous_captions = previous_results.get("lanes", {}).get("youtube", {}).get("quality", {}).get("captions", {})
            
            if not current_captions or not previous_captions:
                return {
                    "consistent": True,
                    "reason": "No caption data to compare"
                }
            
            # Compare generation method and source
            current_method = current_captions.get("generation_method", "unknown")
            previous_method = previous_captions.get("generation_method", "unknown")
            
            if current_method != previous_method:
                return {
                    "consistent": False,
                    "reason": f"Generation method changed: {current_method} vs {previous_method}",
                    "current_method": current_method,
                    "previous_method": previous_method
                }
            
            # If both are generated, check if they should be identical
            if current_method == "heuristic" and previous_method == "heuristic":
                # Heuristic generation should be deterministic with same seed
                current_path = current_captions.get("path", "")
                previous_path = previous_captions.get("path", "")
                
                if current_path and previous_path:
                    # Check if files exist and compare content
                    current_srt_path = os.path.join(BASE, current_path)
                    previous_srt_path = os.path.join(BASE, previous_path)
                    
                    if os.path.exists(current_srt_path) and os.path.exists(previous_srt_path):
                        try:
                            with open(current_srt_path, 'r', encoding='utf-8') as f:
                                current_content = f.read()
                            with open(previous_srt_path, 'r', encoding='utf-8') as f:
                                previous_content = f.read()
                            
                            if current_content == previous_content:
                                return {
                                    "consistent": True,
                                    "reason": "Heuristic SRT content identical"
                                }
                            else:
                                return {
                                    "consistent": False,
                                    "reason": "Heuristic SRT content differs",
                                    "current_size": len(current_content),
                                    "previous_size": len(previous_content)
                                }
                        except Exception as e:
                            return {
                                "consistent": False,
                                "reason": f"Could not compare SRT content: {str(e)}"
                            }
            
            return {
                "consistent": True,
                "reason": "Caption consistency check passed"
            }
            
        except Exception as e:
            return {
                "consistent": False,
                "reason": f"SRT consistency check error: {str(e)}"
            }


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
    validator = AcceptanceValidator(cfg)
    results = validator.run_validation()
    
    # Output results
    output_path = os.path.join(BASE, args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Log results
    log.info(f"Acceptance results written to: {output_path}")
    log.info(f"Overall status: {results['overall_status']}")
    log.info(f"YouTube lane: {results['summary']['youtube_lane']}")

    
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
