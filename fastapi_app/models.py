from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator


class JobStatus(str, Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    NEEDS_APPROVAL = "needs_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class Stage(str, Enum):
    """Pipeline stage enumeration"""
    OUTLINE = "outline"
    RESEARCH = "research"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    ASSETS = "assets"
    ANIMATICS = "animatics"
    AUDIO = "audio"
    ASSEMBLE = "assemble"
    ACCEPTANCE = "acceptance"


class GateDecision(str, Enum):
    """Gate decision enumeration"""
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


class Brief(BaseModel):
    """Brief configuration snapshot"""
    title: str = ""
    intent: str = "narrative_history"
    audience: List[str] = []
    tone: str = "informative"
    video: Dict[str, Any] = {"target_length_min": 5, "target_length_max": 7}

    keywords_include: List[str] = []
    keywords_exclude: List[str] = []
    sources_preferred: List[str] = []
    monetization: Dict[str, Any] = {
        "primary": ["lead_magnet", "email_capture"],
        "cta_text": "Download our free guide"
    }
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    _source: Optional[str] = None


class ConfigSnapshot(BaseModel):
    """Configuration snapshot for a job"""
    brief: Brief
    render: Dict[str, Any]
    models: Dict[str, Any]
    modules: Dict[str, Any]
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Gate(BaseModel):
    """HITL gate configuration and state"""
    stage: Stage
    required: bool = True
    approved: Optional[bool] = None
    by: Optional[str] = None
    at: Optional[datetime] = None
    notes: Optional[str] = None
    patch: Optional[Dict[str, Any]] = None  # Applied patch if any
    auto_approved: bool = False  # Whether this was auto-approved by timeout
    timeout_seconds: Optional[int] = None  # Auto-approve timeout


class Artifact(BaseModel):
    """Pipeline artifact metadata"""
    stage: Stage
    kind: str
    path: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None


class JobCreate(BaseModel):
    """Job creation request"""
    slug: str
    intent: str
    brief: Optional[Brief] = None  # Optional structured brief
    brief_config: Optional[Dict[str, Any]] = None  # Legacy brief_config field
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)  # Additional metadata including free_text_brief


class Job(BaseModel):
    """Job model with all metadata"""
    id: str
    slug: str
    intent: str
    status: JobStatus
    stage: Stage
    cfg: ConfigSnapshot
    gates: List[Gate] = Field(default_factory=list)
    artifacts: List[Artifact] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    operator: Optional[str] = None  # Who created the job


class JobUpdate(BaseModel):
    """Job update request"""
    status: Optional[JobStatus] = None
    stage: Optional[Stage] = None
    notes: Optional[str] = None


class GateAction(BaseModel):
    """Gate approval/rejection action with JSON patch support"""
    decision: GateDecision
    stage: Stage
    notes: Optional[str] = None
    operator: str
    patch: Optional[Dict[str, Any]] = None  # JSON patch for artifact modification
    
    @validator('patch')
    def validate_patch(cls, v):
        """Validate JSON patch structure"""
        if v is not None:
            # Basic patch validation - should have 'op', 'path', 'value' structure
            if not isinstance(v, dict):
                raise ValueError("Patch must be a dictionary")
            if 'op' not in v or 'path' not in v:
                raise ValueError("Patch must have 'op' and 'path' fields")
            if v['op'] not in ['add', 'remove', 'replace', 'copy', 'move', 'test']:
                raise ValueError("Invalid patch operation")
        return v


class Event(BaseModel):
    """Job event for logging and SSE with validation"""
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="timestamp")
    type: str = Field(alias="event_type")
    stage: Optional[Stage] = None
    status: Optional[str] = None
    message: str = ""
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata")
    job_id: str  # Required job ID for event routing
    
    @validator('type')
    def validate_event_type(cls, v):
        """Validate event type is not empty"""
        if not v or not v.strip():
            raise ValueError("Event type cannot be empty")
        return v.strip()
    
    @validator('message')
    def validate_message(cls, v):
        """Ensure message is not None"""
        return v or ""
    
    @validator('payload')
    def validate_payload(cls, v):
        """Ensure payload is a valid dict"""
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError("Payload must be a dictionary")
        return v
    
    class Config:
        allow_population_by_field_name = True
        fields = {
            "ts": "timestamp",
            "type": "event_type",
            "payload": "metadata"
        }


class HealthResponse(BaseModel):
    """Health check response"""
    ok: bool = True
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "0.1.0"
    services: Dict[str, bool] = Field(default_factory=dict)


class EventStreamResponse(BaseModel):
    """SSE event response"""
    data: str
    event: Optional[str] = None
    id: Optional[str] = None
    retry: Optional[int] = None


class JobEventsResponse(BaseModel):
    """Job events response for polling"""
    job_id: str
    events: List[Event]
    total: int
    has_more: bool
    last_event_time: Optional[datetime] = None
