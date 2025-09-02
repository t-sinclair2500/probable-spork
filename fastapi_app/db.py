import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import Artifact, Event, Gate, Job, JobStatus, Stage

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for the orchestrator"""

    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    cfg_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    required BOOLEAN NOT NULL DEFAULT 1,
                    approved BOOLEAN,
                    operator TEXT,
                    decision_at TEXT,
                    notes TEXT,
                    patch_json TEXT,
                    auto_approved BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (job_id) REFERENCES jobs (id)
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    meta_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs (id)
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    stage TEXT,
                    message TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs (id)
                )
            """
            )

            conn.commit()
            logger.info("Database initialized successfully")

    def create_job(self, job: Job) -> bool:
        """Create a new job in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO jobs (id, slug, intent, status, stage, cfg_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        job.id,
                        job.slug,
                        job.intent,
                        job.status.value,
                        job.stage.value,
                        job.cfg.json(),
                        job.created_at.isoformat(),
                        job.updated_at.isoformat(),
                    ),
                )

                # Insert gates
                for gate in job.gates:
                    conn.execute(
                        """
                        INSERT INTO gates (job_id, stage, required, approved, operator, decision_at, notes, patch_json, auto_approved)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            job.id,
                            gate.stage.value,
                            gate.required,
                            gate.approved,
                            gate.by,
                            gate.at.isoformat() if gate.at else None,
                            gate.notes,
                            json.dumps(gate.patch) if gate.patch else None,
                            gate.auto_approved,
                        ),
                    )

                # Insert artifacts
                for artifact in job.artifacts:
                    conn.execute(
                        """
                        INSERT INTO artifacts (job_id, stage, kind, path, meta_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            job.id,
                            artifact.stage.value,
                            artifact.kind,
                            artifact.path,
                            json.dumps(artifact.meta),
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )

                conn.commit()
                logger.info(f"Job {job.id} created successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to create job {job.id}: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
                job_row = cursor.fetchone()

                if not job_row:
                    return None

                # Get gates
                gates_cursor = conn.execute(
                    "SELECT * FROM gates WHERE job_id = ?", (job_id,)
                )
                gates = []
                for gate_row in gates_cursor.fetchall():
                    gate = Gate(
                        stage=Stage(gate_row["stage"]),
                        required=bool(gate_row["required"]),
                        approved=gate_row["approved"],
                        by=gate_row["operator"],
                        at=(
                            datetime.fromisoformat(gate_row["decision_at"])
                            if gate_row["decision_at"]
                            else None
                        ),
                        notes=gate_row["notes"],
                        patch=(
                            json.loads(gate_row["patch_json"])
                            if gate_row["patch_json"]
                            else None
                        ),
                        auto_approved=bool(gate_row["auto_approved"]),
                    )
                    gates.append(gate)

                # Get artifacts
                artifacts_cursor = conn.execute(
                    "SELECT * FROM artifacts WHERE job_id = ?", (job_id,)
                )
                artifacts = []
                for artifact_row in artifacts_cursor.fetchall():
                    artifact = Artifact(
                        stage=Stage(artifact_row["stage"]),
                        kind=artifact_row["kind"],
                        path=artifact_row["path"],
                        meta=json.loads(artifact_row["meta_json"]),
                    )
                    artifacts.append(artifact)

                # Reconstruct job
                cfg = json.loads(job_row["cfg_json"])
                job = Job(
                    id=job_row["id"],
                    slug=job_row["slug"],
                    intent=job_row["intent"],
                    status=JobStatus(job_row["status"]),
                    stage=Stage(job_row["stage"]),
                    cfg=cfg,
                    gates=gates,
                    artifacts=artifacts,
                    created_at=datetime.fromisoformat(job_row["created_at"]),
                    updated_at=datetime.fromisoformat(job_row["updated_at"]),
                )

                return job
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None

    def update_job_status(
        self, job_id: str, status: JobStatus, stage: Optional[Stage] = None
    ) -> bool:
        """Update job status and optionally stage"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if stage:
                    conn.execute(
                        """
                    UPDATE jobs SET status = ?, stage = ?, updated_at = ? WHERE id = ?
                """,
                        (
                            status.value,
                            stage.value,
                            datetime.now(timezone.utc).isoformat(),
                            job_id,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?
                    """,
                        (status.value, datetime.now(timezone.utc).isoformat(), job_id),
                    )

                conn.commit()
                logger.info(f"Job {job_id} status updated to {status.value}")
                return True
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            return False

    def add_event(self, job_id: str, event: Event) -> bool:
        """Add an event to the job's event log"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO events (job_id, timestamp, event_type, stage, message, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        job_id,
                        event.ts.isoformat(),
                        event.type,
                        event.stage.value if event.stage else None,
                        event.message,
                        json.dumps(event.payload),
                    ),
                )

                conn.commit()

                # Also append to events.jsonl file
                self._append_event_to_jsonl(job_id, event)

                return True
        except Exception as e:
            logger.error(f"Failed to add event for job {job_id}: {e}")
            return False

    def _append_event_to_jsonl(self, job_id: str, event: Event):
        """Append event to runs/<job_id>/events.jsonl file"""
        try:
            from pathlib import Path

            # Create runs directory if it doesn't exist
            runs_dir = Path("runs") / job_id
            runs_dir.mkdir(parents=True, exist_ok=True)

            # Append event to events.jsonl
            events_file = runs_dir / "events.jsonl"

            # Create event data in the required format
            event_data = {
                "ts": event.ts.isoformat(),
                "type": event.type,
                "stage": event.stage.value if event.stage else None,
                "status": event.status,
                "message": event.message,
                "payload": event.payload,
            }

            with open(events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_data) + "\n")

            logger.debug(f"Event appended to {events_file}")

        except Exception as e:
            logger.error(f"Failed to append event to JSONL file for job {job_id}: {e}")

    def get_job_events(
        self, job_id: str, limit: int = 100, since: Optional[str] = None
    ) -> List[Event]:
        """Get events for a specific job with optional since timestamp"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                if since:
                    # Get events since the specified timestamp
                    cursor = conn.execute(
                        """
                        SELECT * FROM events 
                        WHERE job_id = ? AND timestamp > ? 
                        ORDER BY timestamp ASC 
                        LIMIT ?
                    """,
                        (job_id, since, limit),
                    )
                else:
                    # Get recent events
                    cursor = conn.execute(
                        """
                        SELECT * FROM events 
                        WHERE job_id = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """,
                        (job_id, limit),
                    )

                events = []
                for row in cursor.fetchall():
                    event = Event(
                        ts=datetime.fromisoformat(row["timestamp"]),
                        type=row["event_type"],
                        stage=Stage(row["stage"]) if row["stage"] else None,
                        status=None,  # Not stored in DB, will be derived
                        message=row["message"],
                        payload=json.loads(row["metadata_json"]),
                    )
                    events.append(event)

                # If since parameter was used, return in chronological order
                if since:
                    return events
                else:
                    # Return in reverse chronological order for recent events
                    return list(reversed(events))

        except Exception as e:
            logger.error(f"Failed to get events for job {job_id}: {e}")
            return []

    def list_jobs(self, limit: int = 100) -> List[Job]:
        """List all jobs with optional limit"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?
                """,
                    (limit,),
                )

                jobs = []
                for job_row in cursor.fetchall():
                    # Get gates and artifacts for each job
                    job_id = job_row["id"]

                    # Get gates
                    gates_cursor = conn.execute(
                        "SELECT * FROM gates WHERE job_id = ?", (job_id,)
                    )
                    gates = []
                    for gate_row in gates_cursor.fetchall():
                        gate = Gate(
                            stage=Stage(gate_row["stage"]),
                            required=bool(gate_row["required"]),
                            approved=gate_row["approved"],
                            by=gate_row["operator"],
                            at=(
                                datetime.fromisoformat(gate_row["decision_at"])
                                if gate_row["decision_at"]
                                else None
                            ),
                            notes=gate_row["notes"],
                        )
                        gates.append(gate)

                    # Get artifacts
                    artifacts_cursor = conn.execute(
                        "SELECT * FROM artifacts WHERE job_id = ?", (job_id,)
                    )
                    artifacts = []
                    for artifact_row in artifacts_cursor.fetchall():
                        artifact = Artifact(
                            stage=Stage(artifact_row["stage"]),
                            kind=artifact_row["kind"],
                            path=artifact_row["path"],
                            meta=json.loads(artifact_row["meta_json"]),
                        )
                        artifacts.append(artifact)

                    # Reconstruct job
                    cfg = json.loads(job_row["cfg_json"])
                    job = Job(
                        id=job_row["id"],
                        slug=job_row["slug"],
                        intent=job_row["intent"],
                        status=JobStatus(job_row["status"]),
                        stage=Stage(job_row["stage"]),
                        cfg=cfg,
                        gates=gates,
                        artifacts=artifacts,
                        created_at=datetime.fromisoformat(job_row["created_at"]),
                        updated_at=datetime.fromisoformat(job_row["updated_at"]),
                    )
                    jobs.append(job)

                return jobs
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return []

    def create_or_update_gate(
        self,
        job_id: str,
        stage: Stage,
        approved: bool,
        operator: str,
        notes: Optional[str] = None,
        patch: Optional[Dict[str, Any]] = None,
        auto_approved: bool = False,
    ) -> bool:
        """Create or update gate decision for a specific stage"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # First check if gate exists
                cursor = conn.execute(
                    """
                    SELECT id FROM gates WHERE job_id = ? AND stage = ?
                """,
                    (job_id, stage.value),
                )

                if cursor.fetchone():
                    # Gate exists, update it
                    conn.execute(
                        """
                        UPDATE gates SET approved = ?, operator = ?, decision_at = ?, notes = ?, patch_json = ?, auto_approved = ?
                        WHERE job_id = ? AND stage = ?
                    """,
                        (
                            approved,
                            operator,
                            datetime.now(timezone.utc).isoformat(),
                            notes,
                            json.dumps(patch) if patch else None,
                            auto_approved,
                            job_id,
                            stage.value,
                        ),
                    )
                else:
                    # Gate doesn't exist, create it
                    conn.execute(
                        """
                        INSERT INTO gates (job_id, stage, required, approved, operator, decision_at, notes, patch_json, auto_approved)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            job_id,
                            stage.value,
                            True,  # Default to required
                            approved,
                            operator,
                            datetime.now(timezone.utc).isoformat(),
                            notes,
                            json.dumps(patch) if patch else None,
                            auto_approved,
                        ),
                    )

                conn.commit()
                approval_type = (
                    "auto-approved"
                    if auto_approved
                    else ("approved" if approved else "rejected")
                )
                logger.info(
                    f"Gate {stage.value} for job {job_id} {approval_type} by {operator}"
                )
                return True
        except Exception as e:
            logger.error(
                f"Failed to create/update gate decision for job {job_id} stage {stage}: {e}"
            )
            return False

    def update_gate_decision(
        self,
        job_id: str,
        stage: Stage,
        approved: bool,
        operator: str,
        notes: Optional[str] = None,
        patch: Optional[Dict[str, Any]] = None,
        auto_approved: bool = False,
    ) -> bool:
        """Update gate decision for a specific stage with optional patch and auto-approval flag"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE gates SET approved = ?, operator = ?, decision_at = ?, notes = ?, patch_json = ?, auto_approved = ?
                    WHERE job_id = ? AND stage = ?
                """,
                    (
                        approved,
                        operator,
                        datetime.now(timezone.utc).isoformat(),
                        notes,
                        json.dumps(patch) if patch else None,
                        auto_approved,
                        job_id,
                        stage.value,
                    ),
                )

                conn.commit()
                approval_type = (
                    "auto-approved"
                    if auto_approved
                    else ("approved" if approved else "rejected")
                )
                logger.info(
                    f"Gate {stage.value} for job {job_id} {approval_type} by {operator}"
                )
                return True
        except Exception as e:
            logger.error(
                f"Failed to update gate decision for job {job_id} stage {stage}: {e}"
            )
            return False

    def add_artifact(self, job_id: str, artifact: Artifact) -> bool:
        """Add an artifact to a job"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO artifacts (job_id, stage, kind, path, meta_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        job_id,
                        artifact.stage.value,
                        artifact.kind,
                        artifact.path,
                        json.dumps(artifact.meta),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

                conn.commit()
                logger.info(f"Artifact {artifact.kind} added to job {job_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to add artifact to job {job_id}: {e}")
            return False

    def get_job_artifacts(self, job_id: str) -> List[Artifact]:
        """Get all artifacts for a specific job"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM artifacts WHERE job_id = ? ORDER BY created_at ASC
                """,
                    (job_id,),
                )

                artifacts = []
                for row in cursor.fetchall():
                    artifact = Artifact(
                        stage=Stage(row["stage"]),
                        kind=row["kind"],
                        path=row["path"],
                        meta=json.loads(row["meta_json"]),
                    )
                    artifacts.append(artifact)

                return artifacts
        except Exception as e:
            logger.error(f"Failed to get artifacts for job {job_id}: {e}")
            return []

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and all associated data"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Delete in order due to foreign key constraints
                conn.execute("DELETE FROM events WHERE job_id = ?", (job_id,))
                conn.execute("DELETE FROM artifacts WHERE job_id = ?", (job_id,))
                conn.execute("DELETE FROM gates WHERE job_id = ?", (job_id,))
                conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

                conn.commit()
                logger.info(f"Job {job_id} deleted successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False

    def store_gate_decision_file(
        self, job_id: str, stage: Stage, decision_data: Dict[str, Any]
    ) -> bool:
        """Store gate decision to filesystem under runs/<id>/gates/<stage>.json"""
        try:
            from pathlib import Path

            # Create gates directory
            gates_dir = Path("runs") / job_id / "gates"
            gates_dir.mkdir(parents=True, exist_ok=True)

            # Write decision file
            decision_file = gates_dir / f"{stage.value}.json"
            with open(decision_file, "w", encoding="utf-8") as f:
                json.dump(decision_data, f, indent=2, default=str)

            logger.info(f"Gate decision stored to {decision_file}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to store gate decision file for job {job_id} stage {stage}: {e}"
            )
            return False

    def get_gate_decision_file(
        self, job_id: str, stage: Stage
    ) -> Optional[Dict[str, Any]]:
        """Retrieve gate decision from filesystem"""
        try:
            from pathlib import Path

            decision_file = Path("runs") / job_id / "gates" / f"{stage.value}.json"
            if decision_file.exists():
                with open(decision_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(
                f"Failed to get gate decision file for job {job_id} stage {stage}: {e}"
            )
            return None


# Global database instance
db = Database()
