from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
    slug: str
    intent: str
    tone: str
    target_len_sec: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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


class Artifact(BaseModel):
    """Pipeline artifact metadata"""
    stage: Stage
    kind: str
    path: str
    meta: Dict[str, Any] = Field(default_factory=dict)


class JobCreate(BaseModel):
    """Job creation request"""
    slug: str
    intent: str
    brief_config: Dict[str, Any]


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


class JobUpdate(BaseModel):
    """Job update request"""
    status: Optional[JobStatus] = None
    stage: Optional[Stage] = None
    notes: Optional[str] = None


class GateAction(BaseModel):
    """Gate approval/rejection action"""
    decision: GateDecision
    stage: Optional[Stage] = None
    notes: Optional[str] = None
    operator: str
    patch: Optional[Dict[str, Any]] = None  # JSON patch for artifact modification


class Event(BaseModel):
    """Job event for logging and SSE"""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    stage: Optional[Stage] = None
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response"""
    ok: bool = True
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "0.1.0"
