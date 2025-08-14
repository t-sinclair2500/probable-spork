# Orchestrator State Machine Implementation

This document describes the implementation of the orchestrator state machine for Phase 6 of the Probable Spork project.

## Overview

The orchestrator implements a deterministic state machine that advances through pipeline stages with HITL (Human-in-the-Loop) gates. It uses in-process background tasks with ThreadPoolExecutor to maintain the single-lane constraint.

## Architecture

### Core Components

1. **Orchestrator Class** (`fastapi_app/orchestrator.py`)
   - Manages job lifecycle and state transitions
   - Coordinates stage execution and gate management
   - Handles job cancellation and resumption

2. **StageRunner Class**
   - Executes individual pipeline stages
   - Provides fallbacks for missing pipeline modules
   - Generates placeholder artifacts for testing

3. **Database Layer** (`fastapi_app/db.py`)
   - SQLite-based job persistence
   - Event logging and artifact tracking
   - Gate decision storage

### State Machine Flow

```
outline → research → script → storyboard → assets → animatics → audio → assemble → acceptance
   ↓         ↓         ↓         ↓         ↓         ↓         ↓         ↓         ↓
  auto     auto    [GATE]   [GATE]    [GATE]     auto    [GATE]     auto      auto
```

**Required Gates (require operator approval):**
- Script generation
- Storyboard creation  
- Asset generation
- Audio generation

**Auto-approval Stages:**
- Outline generation
- Research collection
- Animatics generation
- Video assembly
- Acceptance testing

## Key Features

### 1. Single-Lane Execution
- Uses `ThreadPoolExecutor(max_workers=1)` to enforce single-lane constraint
- Prevents parallel heavy tasks from violating system constraints

### 2. HITL Gates
- Jobs pause at required gates with status `needs_approval`
- Operators can approve/reject with notes
- Rejected jobs pause with status `paused` and can be resumed

### 3. Deterministic Execution
- Re-entrant safe with proper state tracking
- Resume functionality re-runs from current stage
- Artifact deduplication prevents duplicate work

### 4. Fallback Support
- Graceful handling of missing pipeline modules
- Placeholder artifacts for testing without full pipeline
- Import error handling with informative fallbacks

## Usage

### Starting a Job

```python
from fastapi_app.orchestrator import orchestrator
from fastapi_app.models import Job, JobStatus, Stage

# Create job
job = Job(
    id="unique-job-id",
    slug="my-video",
    intent="Create a video about AI tools",
    status=JobStatus.QUEUED,
    stage=Stage.OUTLINE,
    cfg=config_snapshot
)

# Start execution
await orchestrator.start_job(job)
```

### Gate Management

```python
# Approve a gate
await orchestrator.approve_gate(job_id, Stage.SCRIPT, "operator", "Looks good!")

# Reject a gate  
await orchestrator.reject_gate(job_id, Stage.SCRIPT, "operator", "Needs more detail")

# Resume paused job
await orchestrator.advance(job_id)
```

### Job Control

```python
# Cancel job
await orchestrator.cancel_job(job_id)

# Get status
job_status = await orchestrator.get_job_status(job_id)

# List active jobs
active_jobs = await orchestrator.list_active_jobs()
```

## Testing

### Run Orchestrator Test

```bash
make test-orchestrator
```

This will:
1. Create a test job
2. Execute through pipeline stages
3. Pause at required gates
4. Demonstrate approve/reject flow
5. Show artifact generation
6. Verify event logging

### Test Output

The test script provides real-time feedback on:
- Stage transitions
- Gate pauses
- Artifact creation
- Event logging
- Final job status

## Configuration

### Gate Configuration

Gates are configured in `conf/operator.yaml`:

```yaml
gates:
  script:
    required: true
    auto_approve: false
    timeout_minutes: 60
  
  storyboard:
    required: true
    auto_approve: false
    timeout_minutes: 120
```

### Stage Timeouts

Each stage has configurable timeouts:

```yaml
pipeline:
  stage_timeouts:
    outline: 30
    research: 45
    script: 60
    storyboard: 120
    assets: 180
    animatics: 90
    audio: 60
    assemble: 120
    acceptance: 30
```

## Artifacts

### Run Directory Structure

```
runs/<job_id>/
├── state.json              # Current job state
├── outline.txt             # Generated outline
├── research.json           # Research data
├── script.txt              # Generated script
├── storyboard.json         # Storyboard data
├── asset_plan.json         # Asset generation plan
├── animatics/              # Generated animatics
│   ├── scene_000.mp4
│   └── scene_001.mp4
├── voiceover.mp3           # Generated voiceover
├── captions.srt            # Generated captions
├── video.mp4               # Final assembled video
└── acceptance_results.json  # Acceptance test results
```

### Artifact Metadata

Each artifact includes:
- Stage of generation
- File path and type
- Metadata (word count, scene count, etc.)
- Creation timestamp

## Events

### Event Types

- `job_started` - Job execution begins
- `stage_started` - Stage execution begins
- `stage_completed` - Stage execution completes
- `stage_failed` - Stage execution fails
- `gate_pause` - Job pauses at gate
- `gate_approved` - Gate approval
- `gate_rejected` - Gate rejection
- `job_resumed` - Job resumes execution
- `job_completed` - Job completes successfully
- `job_failed` - Job execution fails
- `job_canceled` - Job cancelled by operator

### Event Storage

Events are stored in:
- SQLite database for persistence
- `runs/<job_id>/events.jsonl` for file-based access
- `jobs/state.jsonl` at repo root for integration

## Integration

### With Existing Pipeline

The orchestrator integrates with existing pipeline modules:
- Loads configuration via `bin.core.load_config()`
- Calls existing stage functions when available
- Falls back to placeholder implementations for testing
- Maintains existing artifact structure

### With FastAPI

The orchestrator provides:
- REST API endpoints for job management
- SSE streaming for real-time events
- Authentication and authorization
- CORS configuration

## Security

### Default Settings

- Local-only binding (127.0.0.1)
- Bearer token authentication required
- CORS disabled by default
- Admin token via environment variable

### Production Considerations

- Change default admin token
- Enable CORS only for trusted origins
- Use HTTPS in production
- Implement rate limiting
- Add audit logging

## Monitoring

### Health Checks

- `/api/v1/healthz` - Basic health status
- Job execution metrics
- Stage completion rates
- Gate approval/rejection ratios

### Logging

- Structured logging with JSON format
- Log tags: `[orchestrator]`, `[stage]`, `[gate]`
- Event correlation via job IDs
- Error tracking and reporting

## Future Enhancements

### Planned Features

1. **Redis Queue Integration**
   - Optional distributed job execution
   - Multi-node support
   - Job prioritization

2. **Advanced Gates**
   - Conditional gate requirements
   - Gate dependencies
   - Automated gate evaluation

3. **Job Templates**
   - Reusable job configurations
   - Batch job creation
   - Job scheduling

4. **Performance Optimization**
   - Stage parallelization where safe
   - Resource monitoring
   - Adaptive timeouts

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Check pipeline module availability
   - Verify Python path configuration
   - Use fallback implementations for testing

2. **Database Errors**
   - Verify SQLite permissions
   - Check database schema
   - Reinitialize database if needed

3. **Job Stuck in Gate**
   - Check operator approval status
   - Verify gate configuration
   - Use advance endpoint to resume

4. **Missing Artifacts**
   - Check run directory permissions
   - Verify stage execution success
   - Review event logs for errors

## Conclusion

The orchestrator provides a robust foundation for pipeline execution with human oversight. It maintains the single-lane constraint while enabling operator control at key decision points. The fallback system ensures testing can proceed even without full pipeline implementation.
