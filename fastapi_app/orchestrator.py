"""
Pipeline Orchestrator
Handles job execution, stage transitions, and HITL gate management.
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from threading import Lock

# Add repo root to path for imports
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from .models import Job, JobStatus, Stage, Event, Gate, Artifact
from .db import db
from .storage import storage_manager
from .events import event_logger

logger = logging.getLogger(__name__)


class StageRunner:
    """Executes individual pipeline stages with proper artifact management"""
    
    def __init__(self):
        self.log = logging.getLogger("stage_runner")
        self.storage = storage_manager
    
    async def run_outline(self, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Run outline generation stage"""
        try:
            self.log.info(f"[outline] Starting outline generation for {job.slug}")
            
            # Import pipeline modules
            from bin.core import load_config, load_brief
            from bin.llm_outline import main as run_outline
            
            # Load configuration
            cfg = load_config()
            brief = load_brief()
            
            # Create brief data for the module
            brief_data = {
                "title": job.slug,
                "intent": job.intent,
                "tone": job.cfg.brief.tone,
                "target_len_sec": job.cfg.brief.target_len_sec
            }
            
            # Run outline generation
            run_outline(brief=brief_data, models_config=job.cfg.models)
            
            # Find and copy the generated outline
            outline_path = self._find_outline_file(job.slug)
            if outline_path:
                # Copy to job artifacts
                target_path = self.storage.copy_pipeline_artifact(
                    str(outline_path), 
                    job.id, 
                    Stage.OUTLINE, 
                    "outline.json"
                )
                
                if target_path:
                    # Create artifact record
                    artifact = Artifact(
                        stage=Stage.OUTLINE,
                        kind="outline",
                        path=str(target_path),
                        meta={
                            "source": str(outline_path),
                            "generated_at": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    self.log.info(f"[outline] Completed outline generation for {job.slug}")
                    return {
                        "success": True,
                        "outline_path": str(target_path),
                        "artifact": artifact
                    }
                else:
                    raise Exception("Failed to copy outline artifact")
            else:
                raise Exception("Outline file not found after generation")
                
        except Exception as e:
            self.log.error(f"[outline] Failed outline generation for {job.slug}: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_research(self, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Run research collection stage"""
        try:
            self.log.info(f"[research] Starting research collection for {job.slug}")
            
            # Import pipeline modules
            from bin.research_collect import main as run_research
            from bin.core import load_config
            
            # Load configuration
            cfg = load_config()
            
            # Run research collection
            run_research(brief={"topic": job.intent}, models_config=job.cfg.models)
            
            # Find and copy research artifacts
            research_artifacts = self._find_research_artifacts(job.slug)
            artifacts = []
            
            for artifact_path in research_artifacts:
                filename = Path(artifact_path).name
                target_path = self.storage.copy_pipeline_artifact(
                    artifact_path, 
                    job.id, 
                    Stage.RESEARCH, 
                    filename
                )
                
                if target_path:
                    artifact = Artifact(
                        stage=Stage.RESEARCH,
                        kind="research_data",
                        path=str(target_path),
                        meta={
                            "source": artifact_path,
                            "filename": filename,
                            "generated_at": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    artifacts.append(artifact)
            
            self.log.info(f"[research] Completed research collection for {job.slug}")
            return {
                "success": True,
                "artifacts": artifacts,
                "research_count": len(artifacts)
            }
                
        except Exception as e:
            self.log.error(f"[research] Failed research collection for {job.slug}: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_script(self, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Run script generation stage"""
        try:
            self.log.info(f"[script] Starting script generation for {job.slug}")
            
            # Import pipeline modules
            from bin.llm_script import main as run_script
            from bin.core import load_config, load_brief
            
            # Load configuration
            cfg = load_config()
            brief = load_brief()
            
            # Create brief data for the module
            brief_data = {
                "title": job.slug,
                "intent": job.intent,
                "tone": job.cfg.brief.tone,
                "target_len_sec": job.cfg.brief.target_len_sec
            }
            
            # Run script generation
            run_script(brief=brief_data, models_config=job.cfg.models)
            
            # Find and copy the generated script
            script_path = self._find_script_file(job.slug)
            if script_path:
                # Copy to job artifacts
                target_path = self.storage.copy_pipeline_artifact(
                    str(script_path), 
                    job.id, 
                    Stage.SCRIPT, 
                    "script.txt"
                )
                
                if target_path:
                    # Create artifact record
                    artifact = Artifact(
                        stage=Stage.SCRIPT,
                        kind="script",
                        path=str(target_path),
                        meta={
                            "source": str(script_path),
                            "generated_at": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    self.log.info(f"[script] Completed script generation for {job.slug}")
                    return {
                        "success": True,
                        "script_path": str(target_path),
                        "artifact": artifact
                    }
                else:
                    raise Exception("Failed to copy script artifact")
            else:
                raise Exception("Script file not found after generation")
                
        except Exception as e:
            self.log.error(f"[script] Failed script generation for {job.slug}: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_storyboard(self, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Run storyboard planning stage"""
        try:
            self.log.info(f"[storyboard] Starting storyboard planning for {job.slug}")
            
            # Import pipeline modules
            from bin.storyboard_plan import main as run_storyboard
            from bin.core import load_config, load_brief
            
            # Load configuration
            cfg = load_config()
            brief = load_brief()
            
            # Create brief data for the module
            brief_data = {
                "title": job.slug,
                "intent": job.intent,
                "tone": job.cfg.brief.tone,
                "target_len_sec": job.cfg.brief.target_len_sec
            }
            
            # Run storyboard planning
            run_storyboard(brief=brief_data, models_config=job.cfg.models, slug=job.slug)
            
            # Find and copy the generated storyboard
            storyboard_path = self._find_storyboard_file(job.slug)
            if storyboard_path:
                # Copy to job artifacts
                target_path = self.storage.copy_pipeline_artifact(
                    str(storyboard_path), 
                    job.id, 
                    Stage.STORYBOARD, 
                    "storyboard.json"
                )
                
                if target_path:
                    # Create artifact record
                    artifact = Artifact(
                        stage=Stage.STORYBOARD,
                        kind="storyboard",
                        path=str(target_path),
                        meta={
                            "source": str(storyboard_path),
                            "generated_at": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    self.log.info(f"[storyboard] Completed storyboard planning for {job.slug}")
                    return {
                        "success": True,
                        "storyboard_path": str(target_path),
                        "artifact": artifact
                    }
                else:
                    raise Exception("Failed to copy storyboard artifact")
            else:
                raise Exception("Storyboard file not found after generation")
                
        except Exception as e:
            self.log.error(f"[storyboard] Failed storyboard planning for {job.slug}: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_assets(self, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Run asset generation stage"""
        try:
            self.log.info(f"[assets] Starting asset generation for {job.slug}")
            
            # Import pipeline modules
            from bin.asset_generator import main as run_assets
            from bin.core import load_config, load_brief
            
            # Load configuration
            cfg = load_config()
            brief = load_brief()
            
            # Create brief data for the module
            brief_data = {
                "title": job.slug,
                "intent": job.intent,
                "tone": job.cfg.brief.tone,
                "target_len_sec": job.cfg.brief.target_len_sec
            }
            
            # Run asset generation
            run_assets(brief=brief_data, models_config=job.cfg.models, slug=job.slug)
            
            # Find and copy generated assets
            assets_dir = self._find_assets_directory(job.slug)
            if assets_dir:
                # Copy assets to job artifacts
                target_dir = self.storage.resolve_pipeline_paths(job.id, Stage.ASSETS)["stage_dir"]
                shutil.copytree(assets_dir, target_dir, dirs_exist_ok=True)
                
                # Create artifact record
                artifact = Artifact(
                    stage=Stage.ASSETS,
                    kind="assets_directory",
                    path=str(target_dir),
                    meta={
                        "source": str(assets_dir),
                        "generated_at": datetime.now(timezone.utc).isoformat()
                    }
                )
                
                self.log.info(f"[assets] Completed asset generation for {job.slug}")
                return {
                    "success": True,
                    "assets_path": str(target_dir),
                    "artifact": artifact
                }
            else:
                raise Exception("Assets directory not found after generation")
                
        except Exception as e:
            self.log.error(f"[assets] Failed asset generation for {job.slug}: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_animatics(self, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Run animatics generation stage"""
        try:
            self.log.info(f"[animatics] Starting animatics generation for {job.slug}")
            
            # Import pipeline modules
            from bin.animatics_generate import main as run_animatics
            from bin.core import load_config, load_brief
            
            # Load configuration
            cfg = load_config()
            brief = load_brief()
            
            # Create brief data for the module
            brief_data = {
                "title": job.slug,
                "intent": job.intent,
                "tone": job.cfg.brief.tone,
                "target_len_sec": job.cfg.brief.target_len_sec
            }
            
            # Run animatics generation
            run_animatics(brief=brief_data, models_config=job.cfg.models, slug=job.slug)
            
            # Find and copy generated animatics
            animatics_dir = self._find_animatics_directory(job.slug)
            if animatics_dir:
                # Copy animatics to job artifacts
                target_dir = self.storage.resolve_pipeline_paths(job.id, Stage.ANIMATICS)["stage_dir"]
                shutil.copytree(animatics_dir, target_dir, dirs_exist_ok=True)
                
                # Create artifact record
                artifact = Artifact(
                    stage=Stage.ANIMATICS,
                    kind="animatics_directory",
                    path=str(target_dir),
                    meta={
                        "source": str(animatics_dir),
                        "generated_at": datetime.now(timezone.utc).isoformat()
                    }
                )
                
                self.log.info(f"[animatics] Completed animatics generation for {job.slug}")
                return {
                    "success": True,
                    "animatics_path": str(target_dir),
                    "artifact": artifact
                }
            else:
                raise Exception("Animatics directory not found after generation")
                
        except Exception as e:
            self.log.error(f"[animatics] Failed animatics generation for {job.slug}: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_audio(self, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Run audio generation stage"""
        try:
            self.log.info(f"[audio] Starting audio generation for {job.slug}")
            
            # Import pipeline modules
            from bin.tts_generate import main as run_tts
            from bin.core import load_config, load_brief
            
            # Load configuration
            cfg = load_config()
            brief = load_brief()
            
            # Create brief data for the module
            brief_data = {
                "title": job.slug,
                "intent": job.intent,
                "tone": job.cfg.brief.tone,
                "target_len_sec": job.cfg.brief.target_len_sec
            }
            
            # Run TTS generation
            run_tts(brief=brief_data, models_config=job.cfg.models)
            
            # Find and copy generated audio files
            audio_files = self._find_audio_files(job.slug)
            artifacts = []
            
            for audio_path in audio_files:
                filename = Path(audio_path).name
                target_path = self.storage.copy_pipeline_artifact(
                    audio_path, 
                    job.id, 
                    Stage.AUDIO, 
                    filename
                )
                
                if target_path:
                    # Determine kind based on file extension
                    if filename.endswith('.mp3'):
                        kind = "voiceover"
                    elif filename.endswith('.srt'):
                        kind = "captions"
                    else:
                        kind = "audio"
                    
                    artifact = Artifact(
                        stage=Stage.AUDIO,
                        kind=kind,
                        path=str(target_path),
                        meta={
                            "source": audio_path,
                            "filename": filename,
                            "generated_at": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    artifacts.append(artifact)
            
            self.log.info(f"[audio] Completed audio generation for {job.slug}")
            return {
                "success": True,
                "artifacts": artifacts,
                "audio_count": len(artifacts)
            }
                
        except Exception as e:
            self.log.error(f"[audio] Failed audio generation for {job.slug}: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_assemble(self, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Run video assembly stage"""
        try:
            self.log.info(f"[assemble] Starting video assembly for {job.slug}")
            
            # Import pipeline modules
            from bin.assemble_video import main as run_assemble
            from bin.core import load_config, load_brief
            
            # Load configuration
            cfg = load_config()
            brief = load_brief()
            
            # Create brief data for the module
            brief_data = {
                "title": job.slug,
                "intent": job.intent,
                "tone": job.cfg.brief.tone,
                "target_len_sec": job.cfg.brief.target_len_sec
            }
            
            # Run video assembly
            run_assemble(brief=brief_data, slug=job.slug)
            
            # Find and copy the generated video
            video_path = self._find_video_file(job.slug)
            if video_path:
                # Copy to job artifacts
                target_path = self.storage.copy_pipeline_artifact(
                    str(video_path), 
                    job.id, 
                    Stage.ASSEMBLE, 
                    "video.mp4"
                )
                
                if target_path:
                    # Create artifact record
                    artifact = Artifact(
                        stage=Stage.ASSEMBLE,
                        kind="video",
                        path=str(target_path),
                        meta={
                            "source": str(video_path),
                            "generated_at": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    self.log.info(f"[assemble] Completed video assembly for {job.slug}")
                    return {
                        "success": True,
                        "video_path": str(target_path),
                        "artifact": artifact
                    }
                else:
                    raise Exception("Failed to copy video artifact")
            else:
                raise Exception("Video file not found after assembly")
                
        except Exception as e:
            self.log.error(f"[assemble] Failed video assembly for {job.slug}: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_acceptance(self, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Run acceptance validation stage"""
        try:
            self.log.info(f"[acceptance] Starting acceptance validation for {job.slug}")
            
            # Import pipeline modules
            from bin.acceptance import main as run_acceptance
            from bin.core import load_config, load_blog_cfg
            
            # Load configuration
            cfg = load_config()
            blog_cfg = load_blog_cfg()
            
            # Run acceptance validation
            run_acceptance()
            
            # Find and copy the acceptance report
            acceptance_path = self._find_acceptance_file(job.slug)
            if acceptance_path:
                # Copy to job artifacts
                target_path = self.storage.copy_pipeline_artifact(
                    str(acceptance_path), 
                    job.id, 
                    Stage.ACCEPTANCE, 
                    "acceptance_report.json"
                )
                
                if target_path:
                    # Create artifact record
                    artifact = Artifact(
                        stage=Stage.ACCEPTANCE,
                        kind="acceptance_report",
                        path=str(target_path),
                        meta={
                            "source": str(acceptance_path),
                            "generated_at": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    self.log.info(f"[acceptance] Completed acceptance validation for {job.slug}")
                    return {
                        "success": True,
                        "acceptance_path": str(target_path),
                        "artifact": artifact
                    }
                else:
                    raise Exception("Failed to copy acceptance report artifact")
            else:
                raise Exception("Acceptance report not found after validation")
                
        except Exception as e:
            self.log.error(f"[acceptance] Failed acceptance validation for {job.slug}: {e}")
            return {"success": False, "error": str(e)}
    
    # Helper methods to find pipeline artifacts
    def _find_outline_file(self, slug: str) -> Optional[Path]:
        """Find the generated outline file"""
        scripts_dir = Path("scripts")
        if scripts_dir.exists():
            for file in scripts_dir.glob(f"*_{slug}.outline.json"):
                return file
        return None
    
    def _find_script_file(self, slug: str) -> Optional[Path]:
        """Find the generated script file"""
        scripts_dir = Path("scripts")
        if scripts_dir.exists():
            for file in scripts_dir.glob(f"*_{slug}.txt"):
                return file
        return None
    
    def _find_storyboard_file(self, slug: str) -> Optional[Path]:
        """Find the generated storyboard file"""
        scenescripts_dir = Path("scenescripts")
        if scenescripts_dir.exists():
            storyboard_path = scenescripts_dir / f"{slug}.json"
            if storyboard_path.exists():
                return storyboard_path
        return None
    
    def _find_assets_directory(self, slug: str) -> Optional[Path]:
        """Find the generated assets directory"""
        assets_dir = Path("assets")
        if assets_dir.exists():
            for subdir in assets_dir.iterdir():
                if subdir.is_dir() and slug in subdir.name:
                    return subdir
        return None
    
    def _find_animatics_directory(self, slug: str) -> Optional[Path]:
        """Find the generated animatics directory"""
        assets_dir = Path("assets")
        if assets_dir.exists():
            for subdir in assets_dir.iterdir():
                if subdir.is_dir() and f"{slug}_animatics" in subdir.name:
                    return subdir
        return None
    
    def _find_audio_files(self, slug: str) -> List[str]:
        """Find the generated audio files"""
        voiceovers_dir = Path("voiceovers")
        audio_files = []
        
        if voiceovers_dir.exists():
            for file in voiceovers_dir.glob(f"*_{slug}.*"):
                if file.suffix in ['.mp3', '.srt']:
                    audio_files.append(str(file))
        
        return audio_files
    
    def _find_video_file(self, slug: str) -> Optional[Path]:
        """Find the generated video file"""
        videos_dir = Path("videos")
        if videos_dir.exists():
            for file in videos_dir.glob(f"*_{slug}.mp4"):
                return file
        return None
    
    def _find_acceptance_file(self, slug: str) -> Optional[Path]:
        """Find the acceptance report file"""
        # Look for the most recent acceptance results
        for filename in ["acceptance_results.json", "acceptance_results_final.json"]:
            if Path(filename).exists():
                return Path(filename)
        return None
    
    def _find_research_artifacts(self, slug: str) -> List[str]:
        """Find research artifacts"""
        data_dir = Path("data") / slug
        artifacts = []
        
        if data_dir.exists():
            for file in data_dir.glob("*.json"):
                if "research" in file.name.lower() or "grounded" in file.name.lower():
                    artifacts.append(str(file))
        
        return artifacts


class Orchestrator:
    """Main orchestrator for pipeline execution"""
    
    def __init__(self):
        self.active_jobs: Dict[str, Job] = {}
        self.job_futures: Dict[str, Future] = {}
        self.executor = ThreadPoolExecutor(max_workers=1)  # Single lane constraint
        self.lock = Lock()
        self.stage_runner = StageRunner()
        logger.info("[orchestrator] Initialized with single-lane execution")
    
    async def start_job(self, job: Job) -> None:
        """Start execution of a job (async-safe)"""
        with self.lock:
            if job.id in self.active_jobs:
                logger.warning(f"[orchestrator] Job {job.id} already active")
                return
            
            # Update job status
            job.status = JobStatus.RUNNING
            job.stage = Stage.OUTLINE
            job.updated_at = datetime.now(timezone.utc)
            
            # Save to database
            db.update_job_status(job.id, job.status, job.stage)
            
            # Add to active jobs
            self.active_jobs[job.id] = job
            
            # Start execution in background
            future = self.executor.submit(self._run_job, job.id)
            self.job_futures[job.id] = future
            
            # Record event using event logger
            event_logger.job_started(job.id, job.slug, job.stage)
            
            logger.info(f"[orchestrator] Started job {job.id} ({job.slug})")
    
    async def advance(self, job_id: str) -> None:
        """Advance job to next stage (idempotent)"""
        with self.lock:
            if job_id not in self.active_jobs:
                logger.warning(f"[orchestrator] Job {job_id} not found")
                return
            
            job = self.active_jobs[job_id]
            
            # Check if job is paused or needs approval
            if job.status in [JobStatus.PAUSED, JobStatus.NEEDS_APPROVAL]:
                logger.info(f"[orchestrator] Resuming job {job_id} from {job.stage}")
                
                # Resume execution
                future = self.executor.submit(self._run_job, job_id)
                self.job_futures[job_id] = future
                
                # Update status
                job.status = JobStatus.RUNNING
                db.update_job_status(job.id, job.status)
                
                # Record event
                event = Event(
                    event_type="job_resumed",
                    stage=job.stage,
                    message=f"Job {job.slug} resumed from {job.stage.value}",
                    metadata={"stage": job.stage.value}
                )
                db.add_event(job.id, event)
            else:
                logger.info(f"[orchestrator] Job {job_id} is already running")
    
    async def pause_for_gate(self, job_id: str, stage: Stage) -> None:
        """Pause job at a specific gate"""
        with self.lock:
            if job_id not in self.active_jobs:
                logger.warning(f"[orchestrator] Job {job_id} not found")
                return
            
            job = self.active_jobs[job_id]
            
            # Ensure gate exists and is properly configured
            self._ensure_gate_exists(job, stage)
            
            # Find the gate for this stage
            gate = next((g for g in job.gates if g.stage == stage), None)
            if not gate:
                logger.error(f"[orchestrator] Gate not found for stage {stage.value} in job {job_id}")
                return
            
            # Update gate timestamp if not already set
            if not gate.at:
                gate.at = datetime.now(timezone.utc)
                # Update gate in database
                db.create_or_update_gate(
                    job.id, stage, None, None, gate.at.isoformat(), None, None, False
                )
            
            # Update job status
            job.status = JobStatus.NEEDS_APPROVAL
            job.updated_at = datetime.now(timezone.utc)
            
            # Save to database
            db.update_job_status(job.id, job.status)
            
            # Cancel current execution
            if job_id in self.job_futures:
                future = self.job_futures[job_id]
                if not future.done():
                    future.cancel()
                del self.job_futures[job_id]
            
            # Record event using event logger
            timeout_seconds = self._get_gate_timeout_seconds(stage)
            event_logger.gate_pause(job.id, stage, timeout_seconds)
            
            logger.info(f"[orchestrator] Job {job_id} paused at {stage.value} gate")
    
    async def record_event(self, job_id: str, event_type: str, payload: dict):
        """Record an event for a job"""
        event = Event(
            event_type=event_type,
            stage=payload.get("stage"),
            message=payload.get("message", ""),
            metadata=payload.get("metadata", {})
        )
        db.add_event(job_id, event)
    
    def _run_job(self, job_id: str) -> None:
        """Main job execution loop (runs in thread)"""
        try:
            job = self.active_jobs.get(job_id)
            if not job:
                logger.error(f"[orchestrator] Job {job_id} not found in active jobs")
                return
            
            # Create run directory
            run_dir = Path("runs") / job_id
            run_dir.mkdir(parents=True, exist_ok=True)
            
            # Save initial state
            self._save_job_state(job, run_dir)
            
            # Execute stages
            stages = [
                Stage.OUTLINE,
                Stage.RESEARCH, 
                Stage.SCRIPT,
                Stage.STORYBOARD,
                Stage.ASSETS,
                Stage.ANIMATICS,
                Stage.AUDIO,
                Stage.ASSEMBLE,
                Stage.ACCEPTANCE
            ]
            
            current_stage_index = stages.index(job.stage)
            
            for stage in stages[current_stage_index:]:
                # Check if job was cancelled
                if job.status == JobStatus.CANCELED:
                    logger.info(f"[orchestrator] Job {job_id} cancelled at {stage.value}")
                    return
                
                # Update current stage
                job.stage = stage
                job.updated_at = datetime.now(timezone.utc)
                db.update_job_status(job.id, job.status, job.stage)
                
                # Record stage start using event logger
                event_logger.stage_started(job.id, stage)
                
                logger.info(f"[orchestrator] Executing {stage.value} stage for job {job_id}")
                
                # Execute stage
                stage_result = asyncio.run(self._execute_stage(stage, job, run_dir))
                
                if not stage_result.get("success"):
                    # Stage failed
                    job.status = JobStatus.FAILED
                    db.update_job_status(job.id, job.status)
                    
                    event_logger.stage_failed(job.id, stage, stage_result.get("error", "Unknown error"))
                    
                    logger.error(f"[orchestrator] Stage {stage.value} failed for job {job_id}")
                    return
                
                # Stage completed successfully
                event_logger.stage_completed(job.id, stage, stage_result)
                
                # Add artifacts
                self._add_stage_artifacts(job, stage, stage_result, run_dir)
                
                # Save updated state
                self._save_job_state(job, run_dir)
                
                # Check if this stage requires approval
                if self._stage_requires_gate(stage):
                    logger.info(f"[orchestrator] Pausing job {job_id} at {stage.value} gate")
                    
                    # Create gate if it doesn't exist
                    self._ensure_gate_exists(job, stage)
                    
                    # Pause for gate approval
                    asyncio.run(self.pause_for_gate(job_id, stage))
                    return
                
                logger.info(f"[orchestrator] Completed {stage.value} stage for job {job_id}")
            
            # All stages completed
            job.status = JobStatus.COMPLETED
            job.updated_at = datetime.now(timezone.utc)
            db.update_job_status(job.id, job.status)
            
            event_logger.job_completed(job.id, job.slug)
            
            logger.info(f"[orchestrator] Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"[orchestrator] Job {job_id} execution failed: {e}")
            
            # Update job status
            job = self.active_jobs.get(job_id)
            if job:
                job.status = JobStatus.FAILED
                job.updated_at = datetime.now(timezone.utc)
                db.update_job_status(job.id, job.status)
                
                event_logger.job_failed(job.id, str(e))
        
        finally:
            # Clean up
            with self.lock:
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]
                if job_id in self.job_futures:
                    del self.job_futures[job_id]
    
    async def _execute_stage(self, stage: Stage, job: Job, run_dir: Path) -> Dict[str, Any]:
        """Execute a specific pipeline stage"""
        stage_methods = {
            Stage.OUTLINE: self.stage_runner.run_outline,
            Stage.RESEARCH: self.stage_runner.run_research,
            Stage.SCRIPT: self.stage_runner.run_script,
            Stage.STORYBOARD: self.stage_runner.run_storyboard,
            Stage.ASSETS: self.stage_runner.run_assets,
            Stage.ANIMATICS: self.stage_runner.run_animatics,
            Stage.AUDIO: self.stage_runner.run_audio,
            Stage.ASSEMBLE: self.stage_runner.run_assemble,
            Stage.ACCEPTANCE: self.stage_runner.run_acceptance
        }
        
        method = stage_methods.get(stage)
        if not method:
            return {"success": False, "error": f"Unknown stage: {stage.value}"}
        
        return await method(job, run_dir)
    
    def _stage_requires_gate(self, stage: Stage) -> bool:
        """Check if a stage requires gate approval"""
        from .config import operator_config
        
        stage_config = operator_config.get(f"gates.{stage.value}")
        return stage_config and stage_config.get("required", False)
    
    def _ensure_gate_exists(self, job: Job, stage: Stage):
        """Ensure a gate exists for the given stage"""
        # Check if gate already exists
        existing_gate = next((g for g in job.gates if g.stage == stage), None)
        
        if not existing_gate:
            # Create new gate
            from .config import operator_config
            
            stage_config = operator_config.get(f"gates.{stage.value}", {})
            gate = Gate(
                stage=stage,
                required=stage_config.get("required", True),
                approved=None,
                by=None,
                at=datetime.now(timezone.utc),
                notes=None,
                patch=None,
                auto_approved=False
            )
            
            job.gates.append(gate)
            
            # Save gate to database
            db.create_or_update_gate(
                job.id, stage, None, None, None, None, False
            )
            
            logger.info(f"[orchestrator] Created gate for {stage.value} stage in job {job.id}")
    
    def _get_gate_timeout_seconds(self, stage: Stage) -> Optional[int]:
        """Get timeout in seconds for a stage gate"""
        from .config import operator_config
        
        stage_config = operator_config.get(f"gates.{stage.value}")
        if stage_config and stage_config.get("auto_approve"):
            return stage_config.get("auto_approve_after_s")
        return None
    
    def _add_stage_artifacts(self, job: Job, stage: Stage, result: Dict[str, Any], run_dir: Path):
        """Add artifacts from stage execution"""
        if not result.get("success"):
            return
        
        # Extract artifact paths from result
        artifacts_to_add = []
        
        if stage == Stage.OUTLINE and "outline_path" in result:
            artifacts_to_add.append(Artifact(
                stage=stage,
                kind="outline",
                path=result["outline_path"],
                meta={"source": result.get("artifact", {}).get("source")}
            ))
        
        elif stage == Stage.RESEARCH and "artifacts" in result:
            for artifact in result["artifacts"]:
                artifacts_to_add.append(Artifact(
                    stage=stage,
                    kind="research_data",
                    path=artifact["path"],
                    meta={"source": artifact.get("source")}
                ))
        
        elif stage == Stage.SCRIPT and "script_path" in result:
            artifacts_to_add.append(Artifact(
                stage=stage,
                kind="script",
                path=result["script_path"],
                meta={"source": result.get("artifact", {}).get("source")}
            ))
        
        elif stage == Stage.STORYBOARD and "storyboard_path" in result:
            artifacts_to_add.append(Artifact(
                stage=stage,
                kind="storyboard",
                path=result["storyboard_path"],
                meta={"source": result.get("artifact", {}).get("source")}
            ))
        
        elif stage == Stage.ASSETS and "assets_path" in result:
            artifacts_to_add.append(Artifact(
                stage=stage,
                kind="assets_directory",
                path=result["assets_path"],
                meta={"source": result.get("artifact", {}).get("source")}
            ))
        
        elif stage == Stage.ANIMATICS and "animatics_path" in result:
            artifacts_to_add.append(Artifact(
                stage=stage,
                kind="animatics_directory",
                path=result["animatics_path"],
                meta={"source": result.get("artifact", {}).get("source")}
            ))
        
        elif stage == Stage.AUDIO and "artifacts" in result:
            for artifact in result["artifacts"]:
                artifacts_to_add.append(Artifact(
                    stage=stage,
                    kind=artifact["kind"],
                    path=artifact["path"],
                    meta={"source": artifact.get("source")}
                ))
        
        elif stage == Stage.ASSEMBLE and "video_path" in result:
            artifacts_to_add.append(Artifact(
                stage=stage,
                kind="video",
                path=result["video_path"],
                meta={"source": result.get("artifact", {}).get("source")}
            ))
        
        elif stage == Stage.ACCEPTANCE and "acceptance_path" in result:
            artifacts_to_add.append(Artifact(
                stage=stage,
                kind="acceptance_report",
                path=result["acceptance_path"],
                meta={"source": result.get("artifact", {}).get("source")}
            ))
        
        # Add artifacts to job and database
        for artifact in artifacts_to_add:
            job.artifacts.append(artifact)
            db.add_artifact(job.id, artifact)
    
    def _save_job_state(self, job: Job, run_dir: Path):
        """Save current job state to run directory"""
        try:
            state_file = run_dir / "state.json"
            state_data = {
                "id": job.id,
                "slug": job.slug,
                "status": job.status.value,
                "stage": job.stage.value,
                "updated_at": job.updated_at.isoformat(),
                "gates": [gate.dict() for gate in job.gates],
                "artifacts": [artifact.dict() for artifact in job.artifacts]
            }
            
            state_file.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
            
            # Also update repo root state file
            try:
                from bin.core import log_state
                log_state(job.slug, job.status.value, f"Stage: {job.stage.value}")
            except ImportError:
                # Fallback if core module not available
                logger.warning("[orchestrator] Core module not available, skipping log_state call")
            
        except Exception as e:
            logger.error(f"[orchestrator] Failed to save job state: {e}")
    
    async def approve_gate(self, job_id: str, stage: Stage, operator: str, notes: Optional[str] = None) -> bool:
        """Approve a gate for a specific stage"""
        with self.lock:
            if job_id not in self.active_jobs:
                logger.warning(f"[orchestrator] Job {job_id} not found")
                return False
            
            job = self.active_jobs[job_id]
            
            # Update gate decision
            for gate in job.gates:
                if gate.stage == stage:
                    gate.approved = True
                    gate.by = operator
                    gate.at = datetime.now(timezone.utc)
                    gate.notes = notes
                    break
            else:
                # Create new gate record
                gate = Gate(
                    stage=stage,
                    required=True,
                    approved=True,
                    by=operator,
                    at=datetime.now(timezone.utc),
                    notes=notes
                )
                job.gates.append(gate)
            
            # Update database
            db.update_gate_decision(job.id, stage, True, operator, notes)
            
            # Record event using event logger
            event_logger.gate_approved(job.id, stage, operator, notes)
            
            logger.info(f"[orchestrator] Gate {stage.value} approved for job {job_id}")
            
            # Resume job execution
            await self.advance(job_id)
            return True
    
    async def reject_gate(self, job_id: str, stage: Stage, operator: str, notes: Optional[str] = None) -> bool:
        """Reject a gate for a specific stage"""
        with self.lock:
            if job_id not in self.active_jobs:
                logger.warning(f"[orchestrator] Job {job_id} not found")
                return False
            
            job = self.active_jobs[job_id]
            
            # Update gate decision
            for gate in job.gates:
                if gate.stage == stage:
                    gate.approved = False
                    gate.by = operator
                    gate.at = datetime.now(timezone.utc)
                    gate.notes = notes
                    break
            else:
                # Create new gate record
                gate = Gate(
                    stage=stage,
                    required=True,
                    approved=False,
                    by=operator,
                    at=datetime.now(timezone.utc),
                    notes=notes
                )
                job.gates.append(gate)
            
            # Update database
            db.update_gate_decision(job.id, stage, False, operator, notes)
            
            # Pause job
            job.status = JobStatus.PAUSED
            job.updated_at = datetime.now(timezone.utc)
            db.update_job_status(job.id, job.status)
            
            # Record event using event logger
            event_logger.gate_rejected(job.id, stage, operator, notes)
            
            logger.info(f"[orchestrator] Gate {stage.value} rejected for job {job_id}")
            return True
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel execution of a job"""
        with self.lock:
            if job_id not in self.active_jobs:
                logger.warning(f"[orchestrator] Job {job_id} not found")
                return False
            
            job = self.active_jobs[job_id]
            
            # Update job status
            job.status = JobStatus.CANCELED
            job.updated_at = datetime.now(timezone.utc)
            db.update_job_status(job.id, job.status)
            
            # Cancel execution
            if job_id in self.job_futures:
                future = self.job_futures[job_id]
                if not future.done():
                    future.cancel()
                del self.job_futures[job_id]
            
            # Record event using event logger
            event_logger.job_canceled(job.id, "operator")
            
            logger.info(f"[orchestrator] Job {job_id} cancelled")
            return True
    
    async def get_job_status(self, job_id: str) -> Optional[Job]:
        """Get current job status"""
        return self.active_jobs.get(job_id) or db.get_job(job_id)
    
    async def list_active_jobs(self) -> List[Job]:
        """List all active jobs"""
        return list(self.active_jobs.values())
    
    async def cleanup_completed_jobs(self):
        """Clean up completed jobs from memory"""
        with self.lock:
            completed_ids = [
                job_id for job_id, job in self.active_jobs.items()
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELED]
            ]
            
            for job_id in completed_ids:
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]
                if job_id in self.job_futures:
                    del self.job_futures[job_id]
            
            if completed_ids:
                logger.info(f"[orchestrator] Cleaned up {len(completed_ids)} completed jobs")

    async def check_gate_timeouts(self):
        """Check for gates that should be auto-approved due to timeouts"""
        try:
            from .config import operator_config
            
            current_time = datetime.now(timezone.utc)
            
            for job_id, job in list(self.active_jobs.items()):
                if job.status != JobStatus.NEEDS_APPROVAL:
                    continue
                
                # Check each gate for timeout
                for gate in job.gates:
                    if gate.approved is None and gate.required:
                        # Get timeout configuration for this stage
                        stage_config = operator_config.get(f"gates.{gate.stage.value}")
                        if stage_config and stage_config.get("auto_approve"):
                            timeout_seconds = stage_config.get("auto_approve_after_s")
                            
                            # Check if gate has been waiting long enough
                            if timeout_seconds and gate.at and (current_time - gate.at).total_seconds() > timeout_seconds:
                                await self.auto_approve_gate(job_id, gate.stage, f"Auto-approved after {timeout_seconds} second timeout")
                                
        except Exception as e:
            logger.error(f"[orchestrator] Error checking gate timeouts: {e}")
    
    async def auto_approve_gate(self, job_id: str, stage: Stage, reason: str = "Auto-approved by timeout"):
        """Auto-approve a gate due to timeout"""
        try:
            with self.lock:
                if job_id not in self.active_jobs:
                    return False
                
                job = self.active_jobs[job_id]
                
                # Find and update the gate
                for gate in job.gates:
                    if gate.stage == stage:
                        gate.approved = True
                        gate.by = "timer"
                        gate.at = datetime.now(timezone.utc)
                        gate.notes = reason
                        gate.auto_approved = True
                        break
                else:
                    return False
                
                # Update database
                db.update_gate_decision(job.id, stage, True, "timer", reason, None, True)
                
                # Store gate decision to filesystem
                decision_data = {
                    "stage": stage.value,
                    "approved": True,
                    "by": "timer",
                    "at": datetime.now(timezone.utc).isoformat(),
                    "notes": reason,
                    "patch": None,
                    "auto_approved": True
                }
                db.store_gate_decision_file(job.id, stage, decision_data)
                
                # Check if all required gates are now approved
                all_gates_approved = all(
                    gate.approved for gate in job.gates 
                    if gate.required
                )
                
                if all_gates_approved:
                    # Resume job execution
                    job.status = JobStatus.RUNNING
                    job.updated_at = datetime.now(timezone.utc)
                    db.update_job_status(job.id, job.status)
                    
                    # Record event using event logger
                    event_logger.gate_auto_approved(job.id, stage, reason)
                    
                    logger.info(f"[orchestrator] Gate {stage.value} auto-approved for job {job_id}, resuming execution")
                    
                    # Resume job execution
                    await self.resume_job_execution(job_id)
                else:
                    # Record event using event logger
                    event_logger.gate_auto_approved(job.id, stage, reason)
                    
                    logger.info(f"[orchestrator] Gate {stage.value} auto-approved for job {job_id}")
                
                return True
                
        except Exception as e:
            logger.error(f"[orchestrator] Failed to auto-approve gate {stage.value} for job {job_id}: {e}")
            return False
    
    async def resume_job_execution(self, job_id: str):
        """Resume execution of a job after gate approval"""
        try:
            with self.lock:
                if job_id not in self.active_jobs:
                    return False
                
                job = self.active_jobs[job_id]
                
                # Resume from the current stage
                if job_id not in self.job_futures or self.job_futures[job_id].done():
                    # Start new execution
                    future = self.executor.submit(self._run_job, job_id)
                    self.job_futures[job_id] = future
                    
                    logger.info(f"[orchestrator] Resumed execution for job {job_id}")
                    return True
                else:
                    logger.info(f"[orchestrator] Job {job_id} already running")
                    return True
                    
        except Exception as e:
            logger.error(f"[orchestrator] Failed to resume job execution for {job_id}: {e}")
            return False

    async def resume_after_gate(self, job_id: str, stage: Stage) -> bool:
        """Resume job execution after gate approval"""
        try:
            with self.lock:
                if job_id not in self.active_jobs:
                    logger.warning(f"[orchestrator] Job {job_id} not found in active jobs")
                    return False
                
                job = self.active_jobs[job_id]
                
                # Verify gate is approved
                gate = next((g for g in job.gates if g.stage == stage), None)
                if not gate or gate.approved is not True:
                    logger.warning(f"[orchestrator] Gate {stage.value} not approved for job {job_id}")
                    return False
                
                # Update job status back to running
                job.status = JobStatus.RUNNING
                job.updated_at = datetime.now(timezone.utc)
                db.update_job_status(job.id, job.status)
                
                # Record event using event logger
                event_logger.job_resumed(job.id, stage)
                
                # Resume execution
                await self.resume_job_execution(job_id)
                
                logger.info(f"[orchestrator] Job {job_id} resumed after {stage.value} gate approval")
                return True
                
        except Exception as e:
            logger.error(f"[orchestrator] Failed to resume job {job_id} after gate {stage.value}: {e}")
            return False


# Global orchestrator instance
orchestrator = Orchestrator()
