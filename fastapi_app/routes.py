from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
import json
import logging
import uuid
import time
import asyncio
from datetime import datetime, timezone
from collections import defaultdict, deque

from .models import (
    Job, JobCreate, JobUpdate, GateAction, 
    HealthResponse, Event, JobStatus, Stage, GateDecision, Gate, Artifact
)
from .db import db
from .security import get_current_operator
from .config import operator_config

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple in-memory rate limiter for job creation
job_creation_requests = defaultdict(lambda: deque(maxlen=100))

def check_job_creation_rate_limit(request: Request):
    """Check rate limit for job creation"""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Get rate limit configuration
    rate_limiting_enabled = operator_config.get("security.rate_limiting.enabled", True)
    if not rate_limiting_enabled:
        return
    
    job_limit = operator_config.get("security.rate_limiting.job_creation_per_minute", 5)
    requests = job_creation_requests[client_ip]
    
    # Remove old requests outside the 1-minute window
    while requests and requests[0] < now - 60:
        requests.popleft()
    
    # Check if we're under the limit
    if len(requests) >= job_limit:
        logger.warning(f"Job creation rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Job creation rate limit exceeded. Please wait before creating another job.",
            headers={"Retry-After": "60"}
        )
    
    # Add current request
    requests.append(now)


@router.get("/config/operator")
async def get_operator_config(
    current_operator: str = Depends(get_current_operator)
):
    """Get sanitized operator configuration"""
    # Return a sanitized version of the config (no secrets)
    config = {
        "server": {
            "host": operator_config.get("server.host"),
            "port": operator_config.get("server.port"),
            "workers": operator_config.get("server.workers"),
            "log_level": operator_config.get("server.log_level"),
            "allow_external_bind": operator_config.get("server.allow_external_bind")
        },
        "security": {
            "rate_limiting": {
                "enabled": operator_config.get("security.rate_limiting.enabled"),
                "job_creation_per_minute": operator_config.get("security.rate_limiting.job_creation_per_minute"),
                "api_requests_per_minute": operator_config.get("security.rate_limiting.api_requests_per_minute")
            },
            "cors": {
                "enabled": operator_config.get("security.cors.enabled"),
                "allow_origins": operator_config.get("security.cors.allow_origins"),
                "allow_credentials": operator_config.get("security.cors.allow_credentials"),
                "allow_methods": operator_config.get("security.cors.allow_methods"),
                "allow_headers": operator_config.get("security.cors.allow_headers")
            },
            "security_headers": {
                "enabled": operator_config.get("security.security_headers.enabled"),
                "hsts_seconds": operator_config.get("security.security_headers.hsts_seconds"),
                "content_security_policy": operator_config.get("security.security_headers.content_security_policy"),
                "x_content_type_options": operator_config.get("security.security_headers.x_content_type_options"),
                "x_frame_options": operator_config.get("security.security_headers.x_frame_options"),
                "x_xss_protection": operator_config.get("security.security_headers.x_xss_protection")
            }
        },
        "gates": operator_config.get("gates"),
        "storage": {
            "db_path": operator_config.get("storage.db_path"),
            "runs_dir": operator_config.get("storage.runs_dir"),
            "artifacts_dir": operator_config.get("storage.artifacts_dir")
        },
        "pipeline": {
            "max_concurrent_jobs": operator_config.get("pipeline.max_concurrent_jobs"),
            "job_timeout_hours": operator_config.get("pipeline.job_timeout_hours")
        }
    }
    
    logger.info(f"Configuration requested by {current_operator} (sanitized)")
    return config


@router.post("/config/validate")
async def validate_config(
    current_operator: str = Depends(get_current_operator)
):
    """Validate operator configuration"""
    try:
        # Test database connection
        test_jobs = db.list_jobs(limit=1)
        
        # Test config loading
        operator_config.reload()
        
        return {
            "valid": True,
            "message": "Configuration is valid",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration validation failed: {str(e)}"
        )


@router.post("/jobs", response_model=Job, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_create: JobCreate,
    request: Request,
    current_operator: str = Depends(get_current_operator)
):
    """Create a new job"""
    try:
        # Check rate limiting
        check_job_creation_rate_limit(request)
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create configuration snapshot
        from bin.core import load_config, load_modules_cfg, load_brief
        
        try:
            global_cfg = load_config()
            modules_cfg = load_modules_cfg()
            
            # Use brief_config from request, fallback to core if not provided
            if job_create.brief_config:
                brief_cfg = job_create.brief_config
            else:
                brief_cfg = load_brief()
            
            # Create config snapshot
            cfg_snapshot = {
                "brief": brief_cfg,
                "render": global_cfg.dict() if hasattr(global_cfg, 'dict') else global_cfg,
                "models": global_cfg.dict() if hasattr(global_cfg, 'dict') else global_cfg,
                "modules": modules_cfg
            }
        except Exception as e:
            logger.warning(f"Failed to load pipeline configs: {e}, using minimal config")
            cfg_snapshot = {
                "brief": {"slug": job_create.slug, "intent": job_create.intent},
                "render": {},
                "models": {},
                "modules": {}
            }
        
        # Create initial gates based on config
        gates = []
        for stage_name, gate_config in operator_config.get("gates", {}).items():
            try:
                stage = Stage(stage_name)
                gate = Gate(
                    stage=stage,
                    required=gate_config.get("required", True),
                    approved=None  # Will be set when decision is made
                )
                gates.append(gate)
            except ValueError:
                logger.warning(f"Invalid stage name in config: {stage_name}")
        
        # Create job
        job = Job(
            id=job_id,
            slug=job_create.slug,
            intent=job_create.intent,
            status=JobStatus.QUEUED,
            stage=Stage.OUTLINE,
            cfg=cfg_snapshot,
            gates=gates,
            artifacts=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Save to database
        if db.create_job(job):
            # Add initial event using event logger
            from .events import event_logger
            event_logger.job_created(job_id, job_create.slug, current_operator)
            
            logger.info(f"Job {job_id} created successfully by {current_operator}")
            return job
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create job in database"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job creation failed: {str(e)}"
        )


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    current_operator: str = Depends(get_current_operator)
):
    """Get job details by ID"""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    return job


@router.get("/jobs", response_model=List[Job])
async def list_jobs(
    current_operator: str = Depends(get_current_operator)
):
    """List all jobs"""
    try:
        jobs = db.list_jobs(limit=100)
        logger.info(f"Job listing requested by {current_operator}, returned {len(jobs)} jobs")
        return jobs
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve jobs"
        )


@router.post("/jobs/{job_id}/approve")
async def approve_gate(
    job_id: str,
    gate_action: GateAction,
    current_operator: str = Depends(get_current_operator)
):
    """Approve a gate for a specific stage"""
    try:
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Find the gate for the specified stage
        stage = gate_action.stage if hasattr(gate_action, 'stage') else job.stage
        gate_found = False
        
        for gate in job.gates:
            if gate.stage == stage:
                gate_found = True
                if gate.approved is not None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Gate for stage {stage.value} has already been decided"
                    )
                
                # Update gate decision
                if db.update_gate_decision(job_id, stage, True, current_operator, gate_action.notes, gate_action.patch, False):
                    # Store gate decision to filesystem
                    decision_data = {
                        "stage": stage.value,
                        "approved": True,
                        "by": current_operator,
                        "at": datetime.now(timezone.utc).isoformat(),
                        "notes": gate_action.notes,
                        "patch": gate_action.patch,
                        "auto_approved": False
                    }
                    db.store_gate_decision_file(job_id, stage, decision_data)
                    
                    # Add event using event logger
                    from .events import event_logger
                    event_logger.gate_approved(job_id, stage, current_operator, gate_action.notes)
                    
                    # Update job status if needed
                    if job.status == JobStatus.NEEDS_APPROVAL:
                        db.update_job_status(job_id, JobStatus.RUNNING)
                    
                    logger.info(f"Gate {stage.value} approved for job {job_id} by {current_operator}")
                    return {"message": f"Gate {stage.value} approved successfully"}
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update gate decision"
                    )
        
        if not gate_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No gate found for stage {stage.value}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve gate for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gate approval failed: {str(e)}"
        )


@router.post("/jobs/{job_id}/reject")
async def reject_gate(
    job_id: str,
    gate_action: GateAction,
    current_operator: str = Depends(get_current_operator)
):
    """Reject a gate for a specific stage"""
    try:
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Find the gate for the specified stage
        stage = gate_action.stage if hasattr(gate_action, 'stage') else job.stage
        gate_found = False
        
        for gate in job.gates:
            if gate.stage == stage:
                gate_found = True
                if gate.approved is not None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Gate for stage {stage.value} has already been decided"
                    )
                
                # Update gate decision
                if db.update_gate_decision(job_id, stage, False, current_operator, gate_action.notes, gate_action.patch, False):
                    # Store gate decision to filesystem
                    decision_data = {
                        "stage": stage.value,
                        "approved": False,
                        "by": current_operator,
                        "at": datetime.now(timezone.utc).isoformat(),
                        "notes": gate_action.notes,
                        "patch": gate_action.patch,
                        "auto_approved": False
                    }
                    db.store_gate_decision_file(job_id, stage, decision_data)
                    
                    # Add event using event logger
                    from .events import event_logger
                    event_logger.gate_rejected(job_id, stage, current_operator, gate_action.notes)
                    
                    # Update job status to paused
                    db.update_job_status(job_id, JobStatus.PAUSED)
                    
                    logger.info(f"Gate {stage.value} rejected for job {job_id} by {current_operator}")
                    return {"message": f"Gate {stage.value} rejected successfully"}
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update gate decision"
                    )
        
        if not gate_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No gate found for stage {stage.value}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reject gate for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gate rejection failed: {str(e)}"
        )


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    job_id: str,
    current_operator: str = Depends(get_current_operator)
):
    """Resume a paused job, applying any patches from rejected gates"""
    try:
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        if job.status != JobStatus.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_id} is not paused (current status: {job.status.value})"
            )
        
        # Check if there are any rejected gates with patches
        rejected_gates_with_patches = []
        for gate in job.gates:
            if gate.approved is False and gate.patch:
                rejected_gates_with_patches.append(gate)
        
        if rejected_gates_with_patches:
            # Apply patches to artifacts
            for gate in rejected_gates_with_patches:
                await apply_patch_to_artifact(job_id, gate.stage, gate.patch)
                
                # Mark gate as approved after patch application
                db.update_gate_decision(job_id, gate.stage, True, current_operator, f"Auto-approved after patch application", None, False)
                
                # Store updated decision
                decision_data = {
                    "stage": gate.stage.value,
                    "approved": True,
                    "by": f"{current_operator} (patch applied)",
                    "at": datetime.now(timezone.utc).isoformat(),
                    "notes": f"Auto-approved after patch application",
                    "patch": gate.patch,
                    "auto_approved": False
                }
                db.store_gate_decision_file(job_id, gate.stage, decision_data)
        
        # Resume job using orchestrator
        from .orchestrator import orchestrator
        
        # Find the current stage that needs to be resumed
        current_stage = job.stage
        
        # Resume the job
        if await orchestrator.resume_after_gate(job_id, current_stage):
            logger.info(f"Job {job_id} resumed by {current_operator} with {len(rejected_gates_with_patches)} patches applied")
            return {"message": "Job resumed successfully", "patches_applied": len(rejected_gates_with_patches)}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resume job execution"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job resume failed: {str(e)}"
        )


async def apply_patch_to_artifact(job_id: str, stage: Stage, patch: Dict[str, Any]):
    """Apply a patch to an artifact for a specific stage"""
    try:
        from pathlib import Path
        
        # Get the artifact path for this stage
        job = db.get_job(job_id)
        if not job:
            raise Exception(f"Job {job_id} not found")
        
        # Find artifacts for this stage
        stage_artifacts = [a for a in job.artifacts if a.stage == stage]
        if not stage_artifacts:
            logger.warning(f"No artifacts found for stage {stage.value} in job {job_id}")
            return
        
        # Apply patch based on stage type
        if stage == Stage.SCRIPT:
            await apply_script_patch(job_id, stage_artifacts, patch)
        elif stage == Stage.STORYBOARD:
            await apply_storyboard_patch(job_id, stage_artifacts, patch)
        elif stage == Stage.AUDIO:
            await apply_audio_patch(job_id, stage_artifacts, patch)
        else:
            logger.warning(f"Patch application not implemented for stage {stage.value}")
            
    except Exception as e:
        logger.error(f"Failed to apply patch to artifact for job {job_id} stage {stage}: {e}")
        raise


async def apply_script_patch(job_id: str, artifacts: List[Artifact], patch: Dict[str, Any]):
    """Apply patch to script artifacts"""
    try:
        from pathlib import Path
        
        # Find script file
        script_artifact = next((a for a in artifacts if a.kind == "script"), None)
        if not script_artifact:
            logger.warning(f"No script artifact found for job {job_id}")
            return
        
        script_path = Path(script_artifact.path)
        if not script_path.exists():
            logger.warning(f"Script file not found at {script_path}")
            return
        
        # Apply patch based on patch type
        if patch.get("type") == "text_replace":
            # Simple text replacement
            script_content = script_path.read_text(encoding="utf-8")
            for replacement in patch.get("replacements", []):
                old_text = replacement.get("old")
                new_text = replacement.get("new")
                if old_text and new_text:
                    script_content = script_content.replace(old_text, new_text)
            
            # Write updated script
            script_path.write_text(script_content, encoding="utf-8")
            logger.info(f"Applied text replacement patch to script {script_path}")
            
        elif patch.get("type") == "section_replace":
            # Section replacement
            script_content = script_path.read_text(encoding="utf-8")
            section_marker = patch.get("section_marker")
            new_section = patch.get("new_section")
            
            if section_marker and new_section:
                # Simple section replacement (could be enhanced with proper parsing)
                if section_marker in script_content:
                    script_content = script_content.replace(section_marker, new_section)
                    script_path.write_text(script_content, encoding="utf-8")
                    logger.info(f"Applied section replacement patch to script {script_path}")
        
    except Exception as e:
        logger.error(f"Failed to apply script patch: {e}")
        raise


async def apply_storyboard_patch(job_id: str, artifacts: List[Artifact], patch: Dict[str, Any]):
    """Apply patch to storyboard artifacts"""
    try:
        from pathlib import Path
        import json
        
        # Find storyboard file
        storyboard_artifact = next((a for a in artifacts if a.kind == "storyboard"), None)
        if not storyboard_artifact:
            logger.warning(f"No storyboard artifact found for job {job_id}")
            return
        
        storyboard_path = Path(storyboard_artifact.path)
        if not storyboard_path.exists():
            logger.warning(f"Storyboard file not found at {storyboard_path}")
            return
        
        # Load storyboard
        with open(storyboard_path, 'r', encoding='utf-8') as f:
            storyboard_data = json.load(f)
        
        # Apply patch
        if patch.get("type") == "duration_adjust":
            # Adjust beat durations
            for beat_adjustment in patch.get("beat_adjustments", []):
                beat_id = beat_adjustment.get("beat_id")
                new_duration = beat_adjustment.get("duration")
                
                if beat_id and new_duration:
                    # Find and update beat duration
                    for section in storyboard_data.get("sections", []):
                        for beat in section.get("beats", []):
                            if beat.get("id") == beat_id:
                                beat["duration"] = new_duration
                                logger.info(f"Updated beat {beat_id} duration to {new_duration}")
                                break
        
        # Write updated storyboard
        with open(storyboard_path, 'w', encoding='utf-8') as f:
            json.dump(storyboard_data, f, indent=2)
            
        logger.info(f"Applied storyboard patch to {storyboard_path}")
        
    except Exception as e:
        logger.error(f"Failed to apply storyboard patch: {e}")
        raise


async def apply_audio_patch(job_id: str, artifacts: List[Artifact], patch: Dict[str, Any]):
    """Apply patch to audio artifacts"""
    try:
        from pathlib import Path
        import json
        
        # Find audio metadata file
        audio_artifact = next((a for a in artifacts if a.kind == "audio"), None)
        if not audio_artifact:
            logger.warning(f"No audio artifact found for job {job_id}")
            return
        
        # Apply audio-level adjustments
        if patch.get("type") == "level_adjust":
            # This would typically involve re-processing the audio with new levels
            # For now, we'll just log the adjustment
            level_change = patch.get("level_change_db", 0)
            logger.info(f"Audio level adjustment requested: {level_change} dB")
            
            # In a full implementation, this would trigger audio re-processing
            # with the new level settings
            
    except Exception as e:
        logger.error(f"Failed to apply audio patch: {e}")
        raise


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    current_operator: str = Depends(get_current_operator)
):
    """Cancel a running job"""
    try:
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_id} cannot be canceled (current status: {job.status.value})"
            )
        
        # Cancel job
        if db.update_job_status(job_id, JobStatus.CANCELED):
            # Add event using event logger
            from .events import event_logger
            event_logger.job_canceled(job_id, current_operator)
            
            logger.info(f"Job {job_id} canceled by {current_operator}")
            return {"message": "Job canceled successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel job"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job cancellation failed: {str(e)}"
        )


@router.get("/jobs/{job_id}/artifacts")
async def get_job_artifacts(
    job_id: str,
    current_operator: str = Depends(get_current_operator)
):
    """Get artifacts for a specific job"""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    return job.artifacts


@router.get("/jobs/{job_id}/events")
async def get_job_events(
    job_id: str,
    since: Optional[str] = None,
    limit: int = 100,
    current_operator: str = Depends(get_current_operator)
):
    """Get events for a specific job (polling endpoint)"""
    try:
        events = db.get_job_events(job_id, limit=limit, since=since)
        return {
            "job_id": job_id,
            "events": events,
            "count": len(events),
            "since": since,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get events for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job events"
        )


@router.get("/jobs/{job_id}/events/stream")
async def stream_job_events(
    job_id: str,
    current_operator: str = Depends(get_current_operator)
):
    """Stream job events via Server-Sent Events (SSE)"""
    try:
        # Verify job exists
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        async def event_stream():
            """Stream events for the job"""
            try:
                # Create a queue for this client
                from .events import event_logger
                queue = asyncio.Queue()
                
                # Subscribe to events
                await event_logger.stream_manager.subscribe(job_id, queue)
                
                # Send initial connection event
                initial_event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "connected",
                    "stage": None,
                    "status": None,
                    "message": f"Connected to job {job_id} event stream",
                    "payload": {"job_id": job_id, "operator": current_operator}
                }
                yield f"data: {json.dumps(initial_event)}\n\n"
                
                # Send heartbeat every 5 seconds as required
                last_heartbeat = time.time()
                
                while True:
                    current_time = time.time()
                    
                    # Send heartbeat every 5 seconds
                    if current_time - last_heartbeat >= 5:
                        heartbeat_event = {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "type": "heartbeat",
                            "stage": None,
                            "status": None,
                            "message": "",
                            "payload": {}
                        }
                        yield f"data: {json.dumps(heartbeat_event)}\n\n"
                        last_heartbeat = current_time
                    
                    # Check for new events (non-blocking)
                    try:
                        # Wait for events with timeout
                        event_data = await asyncio.wait_for(queue.get(), timeout=1.0)
                        yield f"data: {json.dumps(event_data)}\n\n"
                    except asyncio.TimeoutError:
                        # No events, continue to next heartbeat check
                        continue
                    
            except asyncio.CancelledError:
                # Client disconnected
                logger.info(f"SSE stream ended for job {job_id}")
                # Unsubscribe from events
                await event_logger.stream_manager.unsubscribe(job_id, queue)
                return
            except Exception as e:
                logger.error(f"Error in SSE stream for job {job_id}: {e}")
                error_event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "error",
                    "stage": None,
                    "status": None,
                    "message": str(e),
                    "payload": {"error": str(e)}
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                # Unsubscribe from events
                await event_logger.stream_manager.unsubscribe(job_id, queue)
                return
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start SSE stream for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Event streaming failed: {str(e)}"
        )


@router.get("/jobs/{job_id}/gates/{stage}/decision")
async def get_gate_decision(
    job_id: str,
    stage: Stage,
    current_operator: str = Depends(get_current_operator)
):
    """Get gate decision from filesystem for a specific stage"""
    try:
        # Verify job exists
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Get gate decision from filesystem
        decision_data = db.get_gate_decision_file(job_id, stage)
        if decision_data:
            return decision_data
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No gate decision found for stage {stage.value}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get gate decision for job {job_id} stage {stage}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve gate decision: {str(e)}"
        )


@router.get("/jobs/{job_id}/gates/decisions")
async def list_gate_decisions(
    job_id: str,
    current_operator: str = Depends(get_current_operator)
):
    """List all gate decisions for a job from filesystem"""
    try:
        # Verify job exists
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Get all gate decisions from filesystem
        decisions = {}
        for stage in Stage:
            decision_data = db.get_gate_decision_file(job_id, stage)
            if decision_data:
                decisions[stage.value] = decision_data
        
        return {
            "job_id": job_id,
            "decisions": decisions,
            "total_decisions": len(decisions)
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list gate decisions for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve gate decisions: {str(e)}"
        )


@router.post("/jobs/{job_id}/patches/{stage}/apply")
async def apply_patch_direct(
    job_id: str,
    stage: Stage,
    patch: Dict[str, Any],
    current_operator: str = Depends(get_current_operator)
):
    """Apply a patch directly to an artifact for a specific stage"""
    try:
        # Verify job exists
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Apply the patch
        await apply_patch_to_artifact(job_id, stage, patch)
        
        # Record the patch application using event logger
        from .events import event_logger
        event_logger.emit_event(
            job_id=job_id,
            event_type="patch_applied_direct",
            stage=stage,
            message=f"Patch applied directly by {current_operator}",
            payload={
                "operator": current_operator,
                "patch": patch,
                "stage": stage.value
            }
        )
        
        logger.info(f"Patch applied directly to {stage.value} for job {job_id} by {current_operator}")
        return {"message": f"Patch applied successfully to {stage.value}"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply patch to {stage.value} for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Patch application failed: {str(e)}"
        )


@router.get("/jobs/{job_id}/gates/status")
async def get_gates_status(
    job_id: str,
    current_operator: str = Depends(get_current_operator)
):
    """Get current status of all gates for a job"""
    try:
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Get gate statuses
        gate_statuses = []
        for gate in job.gates:
            status_info = {
                "stage": gate.stage.value,
                "required": gate.required,
                "approved": gate.approved,
                "by": gate.by,
                "at": gate.at.isoformat() if gate.at else None,
                "notes": gate.notes,
                "auto_approved": gate.auto_approved,
                "has_patch": gate.patch is not None
            }
            
            # Add timeout information if gate is pending
            if gate.approved is None and gate.required:
                from .config import operator_config
                stage_config = operator_config.get(f"gates.{gate.stage.value}")
                if stage_config:
                    status_info["timeout_seconds"] = stage_config.get("auto_approve_after_s")
                    status_info["auto_approve_enabled"] = stage_config.get("auto_approve", False)
                    
                    # Calculate time remaining if timeout is set
                    if gate.at and status_info["timeout_seconds"]:
                        elapsed = (datetime.now(timezone.utc) - gate.at).total_seconds()
                        status_info["time_remaining"] = max(0, status_info["timeout_seconds"] - elapsed)
                        status_info["time_elapsed"] = elapsed
            
            gate_statuses.append(status_info)
        
        return {
            "job_id": job_id,
            "job_status": job.status.value,
            "current_stage": job.stage.value,
            "gates": gate_statuses,
            "total_gates": len(gate_statuses),
            "approved_gates": len([g for g in gate_statuses if g["approved"] is True]),
            "rejected_gates": len([g for g in gate_statuses if g["approved"] is False]),
            "pending_gates": len([g for g in gate_statuses if g["approved"] is None])
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get gates status for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve gates status: {str(e)}"
        )


@router.get("/patches/types")
async def get_patch_types(
    current_operator: str = Depends(get_current_operator)
):
    """Get information about supported patch types and examples"""
    return {
        "patch_types": {
            "script": {
                "description": "Script text modifications",
                "examples": [
                    {
                        "type": "text_replace",
                        "description": "Replace specific text in script",
                        "example": {
                            "type": "text_replace",
                            "replacements": [
                                {"old": "old text", "new": "new text"}
                            ]
                        }
                    },
                    {
                        "type": "section_replace",
                        "description": "Replace entire script section",
                        "example": {
                            "type": "section_replace",
                            "section_marker": "## Introduction",
                            "new_section": "## Introduction\n\nUpdated introduction content"
                        }
                    }
                ]
            },
            "storyboard": {
                "description": "Storyboard timing and structure modifications",
                "examples": [
                    {
                        "type": "duration_adjust",
                        "description": "Adjust beat durations",
                        "example": {
                            "type": "duration_adjust",
                            "beat_adjustments": [
                                {"beat_id": "intro_beat", "duration": 15}
                            ]
                        }
                    }
                ]
            },
            "audio": {
                "description": "Audio level and processing modifications",
                "examples": [
                    {
                        "type": "level_adjust",
                        "description": "Adjust audio levels in dB",
                        "example": {
                            "type": "level_adjust",
                            "level_change_db": 3
                        }
                    }
                ]
            }
        },
        "usage": "Send patches in the 'patch' field when approving/rejecting gates, or use the direct patch application endpoint"
    }
