"""
Events and Logging System
Handles structured logging and event emission for the orchestrator.
"""

import logging
import json
import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set, List
from pathlib import Path
import threading
import time

from .models import Event, Stage, JobStatus, EventStreamResponse
from .db import db

logger = logging.getLogger(__name__)


class EventStreamManager:
    """Manages real-time event streaming to SSE clients with heartbeat"""
    
    def __init__(self):
        self.active_streams: Dict[str, Set[asyncio.Queue]] = {}
        self.log = logging.getLogger("event_stream")
        self.heartbeat_task: Optional[asyncio.Task] = None
        self._start_heartbeat()
    
    def _start_heartbeat(self):
        """Start heartbeat task for SSE clients"""
        async def heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(5)  # Heartbeat every 5 seconds
                    await self._send_heartbeat()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.log.error(f"Heartbeat error: {e}")
                    await asyncio.sleep(1)
        
        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
    
    async def _send_heartbeat(self):
        """Send heartbeat to all active SSE clients"""
        heartbeat_data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "heartbeat",
            "message": "Server alive",
            "payload": {"timestamp": datetime.now(timezone.utc).isoformat()}
        }
        
        # Send to all active streams
        for job_id in list(self.active_streams.keys()):
            await self.broadcast_event(job_id, Event(**heartbeat_data, job_id=job_id))
    
    async def subscribe(self, job_id: str, queue: asyncio.Queue):
        """Subscribe to events for a specific job"""
        if job_id not in self.active_streams:
            self.active_streams[job_id] = set()
        self.active_streams[job_id].add(queue)
        self.log.info(f"[events] Client subscribed to job {job_id} events")
    
    async def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        """Unsubscribe from events for a specific job"""
        if job_id in self.active_streams:
            self.active_streams[job_id].discard(queue)
            if not self.active_streams[job_id]:
                del self.active_streams[job_id]
        self.log.info(f"[events] Client unsubscribed from job {job_id} events")
    
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
                self.log.warning(f"[events] Failed to send event to client: {e}")
                disconnected_queues.add(queue)
        
        # Clean up disconnected clients
        for queue in disconnected_queues:
            await self.unsubscribe(job_id, queue)
        
        if self.active_streams[job_id]:
            self.log.debug(f"[events] Broadcasted event {event.type} to {len(self.active_streams[job_id])} clients for job {job_id}")
    
    def stop(self):
        """Stop the event stream manager"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()


class EventLogger:
    """Structured logger that mirrors events to console, database, and JSONL files"""
    
    def __init__(self):
        self.log = logging.getLogger("events")
        self.stream_manager = EventStreamManager()
        self._setup_logging()
        self._ensure_runs_dir()
    
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
    
    def _ensure_runs_dir(self):
        """Ensure runs directory exists"""
        runs_dir = Path("runs")
        runs_dir.mkdir(exist_ok=True)
    
    def _write_event_to_jsonl(self, job_id: str, event: Event):
        """Write event to JSONL file in runs/<id>/events.jsonl"""
        try:
            # Ensure job run directory exists
            run_dir = Path("runs") / job_id
            run_dir.mkdir(exist_ok=True)
            
            # Write to events.jsonl
            events_file = run_dir / "events.jsonl"
            
            # Convert event to dict for JSON serialization
            event_dict = {
                "timestamp": event.ts.isoformat(),
                "event_type": event.type,
                "stage": event.stage.value if event.stage else None,
                "status": event.status,
                "message": event.message,
                "payload": event.payload,
                "job_id": event.job_id
            }
            
            # Append to JSONL file
            with open(events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_dict, ensure_ascii=False) + "\n")
                
            self.log.debug(f"[events] Wrote event {event.type} to {events_file}")
            
        except Exception as e:
            self.log.error(f"[events] Failed to write event to JSONL: {e}")
    
    async def emit_event(self, job_id: str, event_type: str, stage: Optional[Stage] = None, 
                   status: Optional[str] = None, message: str = "", payload: Optional[Dict[str, Any]] = None):
        """Emit an event and log it to console, database, JSONL, then broadcast to SSE clients"""
        try:
            # Create event with validation
            event = Event(
                ts=datetime.now(timezone.utc),
                type=event_type,
                stage=stage,
                status=status,
                message=message,
                payload=payload or {},
                job_id=job_id
            )
            
            # Write to JSONL file
            self._write_event_to_jsonl(job_id, event)
            
            # Add to database
            if db.add_event(job_id, event):
                # Log to console with [events] tag
                self._log_event_to_console(job_id, event)
                
                # Broadcast to SSE clients
                await self.stream_manager.broadcast_event(job_id, event)
                
                return event
            else:
                self.log.error(f"[events] Failed to add event to database: {event_type}")
                return None
                
        except Exception as e:
            self.log.error(f"[events] Failed to emit event {event_type}: {e}")
            return None
    
    def emit_event_sync(self, job_id: str, event_type: str, stage: Optional[Stage] = None, 
                   status: Optional[str] = None, message: str = "", payload: Optional[Dict[str, Any]] = None):
        """Synchronous version of emit_event for use in non-async contexts"""
        try:
            # Create event with validation
            event = Event(
                ts=datetime.now(timezone.utc),
                type=event_type,
                stage=stage,
                status=status,
                message=message,
                payload=payload or {},
                job_id=job_id
            )
            
            # Write to JSONL file
            self._write_event_to_jsonl(job_id, event)
            
            # Add to database
            if db.add_event(job_id, event):
                # Log to console with [events] tag
                self._log_event_to_console(job_id, event)
                return event
            else:
                self.log.error(f"[events] Failed to add event to database: {event_type}")
                return None
                
        except Exception as e:
            self.log.error(f"[events] Failed to emit event {event_type}: {e}")
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
            self.log.error(f"[events] Failed to log event to console: {e}")
    
    def get_job_events(self, job_id: str, limit: int = 100, since: Optional[datetime] = None) -> List[Event]:
        """Get events for a job from JSONL file with optional filtering"""
        try:
            events_file = Path("runs") / job_id / "events.jsonl"
            if not events_file.exists():
                return []
            
            events = []
            with open(events_file, "r", encoding="utf-8") as f:
                for line in f:
                    if len(events) >= limit:
                        break
                    
                    try:
                        event_data = json.loads(line.strip())
                        
                        # Filter by timestamp if since is provided
                        if since:
                            event_time = datetime.fromisoformat(event_data["timestamp"])
                            if event_time <= since:
                                continue
                        
                        # Convert to Event model
                        event = Event(
                            ts=datetime.fromisoformat(event_data["timestamp"]),
                            type=event_data["event_type"],
                            stage=Stage(event_data["stage"]) if event_data.get("stage") else None,
                            status=event_data.get("status"),
                            message=event_data.get("message", ""),
                            payload=event_data.get("payload", {}),
                            job_id=event_data.get("job_id", job_id)
                        )
                        events.append(event)
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        self.log.warning(f"[events] Skipping malformed event line: {e}")
                        continue
            
            return events
            
        except Exception as e:
            self.log.error(f"[events] Failed to read events from JSONL: {e}")
            return []
    
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
    
    def gate_approved(self, job_id: str, stage: Stage, operator: str, notes: Optional[str] = None, patch: Optional[Dict[str, Any]] = None):
        """Log gate approval event"""
        payload = {
            "stage": stage.value,
            "status": "approved",
            "operator": operator,
            "notes": notes
        }
        if patch:
            payload["patch"] = patch
        
        return self.emit_event_sync(
            job_id=job_id,
            event_type="gate_approved",
            stage=stage,
            status="approved",
            message=f"Gate {stage.value} approved by {operator}",
            payload=payload
        )
    
    def gate_rejected(self, job_id: str, stage: Stage, operator: str, notes: Optional[str] = None, patch: Optional[Dict[str, Any]] = None):
        """Log gate rejection event"""
        payload = {
            "stage": stage.value,
            "status": "rejected",
            "operator": operator,
            "notes": notes
        }
        if patch:
            payload["patch"] = patch
        
        return self.emit_event_sync(
            job_id=job_id,
            event_type="gate_rejected",
            stage=stage,
            status="rejected",
            message=f"Gate {stage.value} rejected by {operator}",
            payload=payload
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
    
    def stop(self):
        """Stop the event logger and stream manager"""
        self.stream_manager.stop()


# Global event logger instance
event_logger = EventLogger()
