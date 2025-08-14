"""
Events and Logging System
Handles structured logging and event emission for the orchestrator.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set
from pathlib import Path

from .models import Event, Stage, JobStatus
from .db import db

logger = logging.getLogger(__name__)


class EventStreamManager:
    """Manages real-time event streaming to SSE clients"""
    
    def __init__(self):
        self.active_streams: Dict[str, Set[asyncio.Queue]] = {}
        self.log = logging.getLogger("event_stream")
    
    async def subscribe(self, job_id: str, queue: asyncio.Queue):
        """Subscribe to events for a specific job"""
        if job_id not in self.active_streams:
            self.active_streams[job_id] = set()
        self.active_streams[job_id].add(queue)
        self.log.info(f"Client subscribed to job {job_id} events")
    
    async def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        """Unsubscribe from events for a specific job"""
        if job_id in self.active_streams:
            self.active_streams[job_id].discard(queue)
            if not self.active_streams[job_id]:
                del self.active_streams[job_id]
        self.log.info(f"Client unsubscribed from job {job_id} events")
    
    async def broadcast_event(self, job_id: str, event: Event):
        """Broadcast an event to all subscribed clients for a job"""
        if job_id not in self.active_streams:
            return
        
        # Convert event to SSE format
        event_data = {
            "ts": event.ts.isoformat(),
            "type": event.type,
            "stage": event.stage.value if event.stage else None,
            "status": event.status,
            "message": event.message,
            "payload": event.payload
        }
        
        # Broadcast to all subscribers
        disconnected_queues = set()
        for queue in self.active_streams[job_id]:
            try:
                await queue.put(event_data)
            except Exception as e:
                self.log.warning(f"Failed to send event to client: {e}")
                disconnected_queues.add(queue)
        
        # Clean up disconnected clients
        for queue in disconnected_queues:
            await self.unsubscribe(job_id, queue)
        
        if self.active_streams[job_id]:
            self.log.debug(f"Broadcasted event {event.type} to {len(self.active_streams[job_id])} clients for job {job_id}")


class EventLogger:
    """Structured logger that mirrors events to console and database"""
    
    def __init__(self):
        self.log = logging.getLogger("events")
        self.stream_manager = EventStreamManager()
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup structured logging with proper formatting"""
        # Create a custom formatter that includes job context
        formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        )
        
        # Ensure we have a handler
        if not self.log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.log.addHandler(handler)
            self.log.setLevel(logging.INFO)
    
    async def emit_event(self, job_id: str, event_type: str, stage: Optional[Stage] = None, 
                   status: Optional[str] = None, message: str = "", payload: Optional[Dict[str, Any]] = None):
        """Emit an event and log it to console and database, then broadcast to SSE clients"""
        try:
            # Create event
            event = Event(
                ts=datetime.now(timezone.utc),
                type=event_type,
                stage=stage,
                status=status,
                message=message,
                payload=payload or {}
            )
            
            # Add to database and JSONL
            if db.add_event(job_id, event):
                # Log to console with [events] tag
                self._log_event_to_console(job_id, event)
                
                # Broadcast to SSE clients
                await self.stream_manager.broadcast_event(job_id, event)
                
                return event
            else:
                self.log.error(f"Failed to add event to database: {event_type}")
                return None
                
        except Exception as e:
            self.log.error(f"Failed to emit event {event_type}: {e}")
            return None
    
    def emit_event_sync(self, job_id: str, event_type: str, stage: Optional[Stage] = None, 
                   status: Optional[str] = None, message: str = "", payload: Optional[Dict[str, Any]] = None):
        """Synchronous version of emit_event for use in non-async contexts"""
        try:
            # Create event
            event = Event(
                ts=datetime.now(timezone.utc),
                type=event_type,
                stage=stage,
                status=status,
                message=message,
                payload=payload or {}
            )
            
            # Add to database and JSONL
            if db.add_event(job_id, event):
                # Log to console with [events] tag
                self._log_event_to_console(job_id, event)
                return event
            else:
                self.log.error(f"Failed to add event to database: {event_type}")
                return None
                
        except Exception as e:
            self.log.error(f"Failed to emit event {event_type}: {e}")
            return None
    
    def _log_event_to_console(self, job_id: str, event: Event):
        """Log event to console with proper formatting and tags"""
        try:
            # Build log message
            log_parts = [f"[events] Job {job_id}"]
            
            if event.stage:
                log_parts.append(f"Stage: {event.stage.value}")
            
            if event.status:
                log_parts.append(f"Status: {event.status}")
            
            log_parts.append(f"Type: {event.type}")
            
            if event.message:
                log_parts.append(f"Message: {event.message}")
            
            if event.payload:
                # Include key payload items
                payload_summary = []
                for key, value in event.payload.items():
                    if isinstance(value, str) and len(value) < 100:
                        payload_summary.append(f"{key}: {value}")
                    elif isinstance(value, (int, float, bool)):
                        payload_summary.append(f"{key}: {value}")
                    else:
                        payload_summary.append(f"{key}: <{type(value).__name__}>")
                
                if payload_summary:
                    log_parts.append(f"Payload: {', '.join(payload_summary)}")
            
            # Log with appropriate level
            log_message = " | ".join(log_parts)
            
            if event.type in ["error", "stage_failed", "job_failed"]:
                self.log.error(log_message)
            elif event.type in ["warning", "gate_rejected"]:
                self.log.warning(log_message)
            elif event.type in ["heartbeat"]:
                self.log.debug(log_message)
            else:
                self.log.info(log_message)
                
        except Exception as e:
            self.log.error(f"Failed to log event to console: {e}")
    
    # Convenience methods for common events
    def job_created(self, job_id: str, slug: str, operator: str):
        """Log job creation event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="job_created",
            message=f"Job created by {operator}",
            payload={"operator": operator, "slug": slug}
        )
    
    def job_started(self, job_id: str, slug: str, stage: Stage):
        """Log job start event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="job_started",
            stage=stage,
            status="running",
            message=f"Job {slug} started execution",
            payload={"stage": stage.value, "status": "running"}
        )
    
    def stage_started(self, job_id: str, stage: Stage):
        """Log stage start event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="stage_started",
            stage=stage,
            status="running",
            message=f"Started {stage.value} stage",
            payload={"stage": stage.value, "status": "running"}
        )
    
    def stage_completed(self, job_id: str, stage: Stage, result: Dict[str, Any]):
        """Log stage completion event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="stage_completed",
            stage=stage,
            status="completed",
            message=f"Completed {stage.value} stage",
            payload={"stage": stage.value, "status": "completed", "result": result}
        )
    
    def stage_failed(self, job_id: str, stage: Stage, error: str):
        """Log stage failure event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="stage_failed",
            stage=stage,
            status="failed",
            message=f"Stage {stage.value} failed: {error}",
            payload={"stage": stage.value, "status": "failed", "error": error}
        )
    
    def gate_pause(self, job_id: str, stage: Stage, timeout_seconds: Optional[int] = None):
        """Log gate pause event"""
        payload = {
            "stage": stage.value,
            "gate_type": "required",
            "gate_id": f"{job_id}_{stage.value}"
        }
        if timeout_seconds:
            payload["timeout_seconds"] = timeout_seconds
        
        return self.emit_event_sync(
            job_id=job_id,
            event_type="gate_pause",
            stage=stage,
            status="needs_approval",
            message=f"Job paused at {stage.value} gate",
            payload=payload
        )
    
    def gate_approved(self, job_id: str, stage: Stage, operator: str, notes: Optional[str] = None):
        """Log gate approval event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="gate_approved",
            stage=stage,
            status="approved",
            message=f"Gate {stage.value} approved by {operator}",
            payload={
                "stage": stage.value,
                "status": "approved",
                "operator": operator,
                "notes": notes
            }
        )
    
    def gate_rejected(self, job_id: str, stage: Stage, operator: str, notes: Optional[str] = None):
        """Log gate rejection event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="gate_rejected",
            stage=stage,
            status="rejected",
            message=f"Gate {stage.value} rejected by {operator}",
            payload={
                "stage": stage.value,
                "status": "rejected",
                "operator": operator,
                "notes": notes
            }
        )
    
    def gate_auto_approved(self, job_id: str, stage: Stage, reason: str):
        """Log gate auto-approval event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="gate_auto_approved",
            stage=stage,
            status="auto_approved",
            message=f"Gate {stage.value} auto-approved: {reason}",
            payload={
                "stage": stage.value,
                "status": "auto_approved",
                "reason": reason
            }
        )
    
    def job_completed(self, job_id: str, slug: str):
        """Log job completion event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="job_completed",
            status="completed",
            message=f"Job {slug} completed successfully",
            payload={"status": "completed", "final_stage": "acceptance"}
        )
    
    def job_failed(self, job_id: str, error: str):
        """Log job failure event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="job_failed",
            status="failed",
            message=f"Job execution failed: {error}",
            payload={"status": "failed", "error": error}
        )
    
    def job_canceled(self, job_id: str, operator: str):
        """Log job cancellation event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="job_canceled",
            status="canceled",
            message=f"Job canceled by {operator}",
            payload={"status": "canceled", "operator": operator}
        )
    
    def job_resumed(self, job_id: str, stage: Stage):
        """Log job resume event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="job_resumed",
            stage=stage,
            status="running",
            message=f"Job resumed from {stage.value}",
            payload={"stage": stage.value, "status": "running"}
        )
    
    def artifact_created(self, job_id: str, stage: Stage, artifact_type: str, path: str):
        """Log artifact creation event"""
        return self.emit_event_sync(
            job_id=job_id,
            event_type="artifact_created",
            stage=stage,
            message=f"Created {artifact_type} artifact",
            payload={
                "stage": stage.value,
                "artifact_type": artifact_type,
                "path": path
            }
        )


# Global event logger instance
event_logger = EventLogger()
