# P6-6 Events & Logs Streaming Implementation

This document describes the implementation of the Events & Logs Streaming (SSE + Polling Fallback) functionality as specified in P6-6.

## Overview

The implementation provides:
- **Server-Sent Events (SSE)** streaming for real-time event delivery
- **Polling fallback** for environments where SSE is blocked
- **Structured logging** that mirrors events to console with `[events]` tags
- **JSONL event storage** in `runs/<job_id>/events.jsonl` files
- **Heartbeat events** every 5 seconds while streaming

## Implementation Details

### 1. Event Model

The `Event` model has been updated to match P6-6 requirements:

```python
class Event(BaseModel):
    ts: datetime = Field(alias="timestamp")           # Event timestamp
    type: str = Field(alias="event_type")             # Event type
    stage: Optional[Stage] = None                     # Pipeline stage
    status: Optional[str] = None                      # Event status
    message: str = ""                                  # Human-readable message
    payload: Optional[Dict[str, Any]] = Field(alias="metadata")  # Event data
```

### 2. Event Logger

The `EventLogger` class provides structured logging with:
- Console output with `[events]` tags
- Database storage via SQLite
- JSONL file storage in `runs/<job_id>/events.jsonl`
- Real-time broadcasting to SSE clients

### 3. Event Streaming Manager

The `EventStreamManager` handles:
- Client subscriptions to job events
- Real-time event broadcasting
- Automatic cleanup of disconnected clients

### 4. API Endpoints

#### GET `/jobs/{id}/events`
**Polling endpoint** that returns recent events:
- `since=<ts>`: Get events since timestamp
- `limit=<n>`: Maximum number of events to return
- Returns events in chronological order when using `since`

#### GET `/jobs/{id}/events/stream`
**SSE endpoint** that streams events in real-time:
- Sends initial connection event
- Emits heartbeats every 5 seconds
- Streams events as they occur
- Proper SSE headers and formatting

## Testing the Implementation

### Prerequisites

1. **Start the FastAPI server**:
   ```bash
   cd fastapi_app
   python -m uvicorn __init__:app --host 127.0.0.1 --port 8008 --reload
   ```

2. **Install test dependencies**:
   ```bash
   pip install requests aiohttp
   ```

### Test Scripts

#### 1. Basic Functionality Test
```bash
python test_events_sse.py
```

This script tests:
- Job creation and event emission
- Polling endpoint with/without `since` parameter
- SSE endpoint accessibility
- Events JSONL file creation
- Structured logging to console

#### 2. SSE Streaming Test
```bash
python test_sse_client.py
```

This script tests:
- Real-time SSE event streaming
- Heartbeat delivery (every 5 seconds)
- Event format and structure
- Connection handling

### Manual Testing

#### Test Polling Endpoint
```bash
# Create a job first, then test events
curl -H "Authorization: Bearer default-admin-token-change-me" \
     "http://127.0.0.1:8008/api/v1/jobs/{job_id}/events"

# Test with since parameter
curl -H "Authorization: Bearer default-admin-token-change-me" \
     "http://127.0.0.1:8008/api/v1/jobs/{job_id}/events?since=2025-01-01T00:00:00Z"
```

#### Test SSE Streaming
```bash
curl -H "Authorization: Bearer default-admin-token-change-me" \
     "http://127.0.0.1:8008/api/v1/jobs/{job_id}/events/stream"
```

## Event Types

The system emits these event types:

- `job_created` - Job creation
- `job_started` - Job execution start
- `stage_started` - Pipeline stage start
- `stage_completed` - Pipeline stage completion
- `stage_failed` - Pipeline stage failure
- `gate_pause` - HITL gate pause
- `gate_approved` - Gate approval
- `gate_rejected` - Gate rejection
- `gate_auto_approved` - Auto-approval by timeout
- `job_completed` - Job completion
- `job_failed` - Job failure
- `job_canceled` - Job cancellation
- `job_resumed` - Job resume after gate
- `heartbeat` - Connection keep-alive

## File Structure

```
runs/
└── {job_id}/
    ├── events.jsonl          # Event stream (append-only)
    ├── state.json            # Current job state
    └── gates/                # Gate decision files
        ├── script.json
        ├── storyboard.json
        └── ...
```

## Configuration

The system uses the existing `conf/operator.yaml` configuration:

```yaml
storage:
  events_retention_days: 30
  max_events_per_job: 1000
```

## Success Criteria Verification

### ✅ UI can subscribe and show live progress
- SSE endpoint provides real-time event streaming
- Events include all required fields (ts, type, stage, status, message, payload)
- Heartbeats maintain connection

### ✅ Polling returns the same events
- `/jobs/{id}/events` endpoint returns events in same format
- `since` parameter provides incremental results
- Event structure matches SSE format

### ✅ Events appended to `runs/<id>/events.jsonl`
- Events are written to JSONL files
- Files are never overwritten (append-only)
- Each line contains a valid JSON event

### ✅ Structured logging with `[events]` tags
- Console output includes `[events]` tags
- Events are logged with proper formatting
- Log levels appropriate to event types

## Troubleshooting

### Common Issues

1. **SSE connection fails**
   - Check if server is running on correct port
   - Verify CORS settings if testing from browser
   - Check authentication token

2. **No events in JSONL file**
   - Verify job ID exists
   - Check database connection
   - Look for errors in server logs

3. **Heartbeats not received**
   - Check client connection handling
   - Verify SSE endpoint returns correct content type
   - Check for network timeouts

### Debug Mode

Enable debug logging by setting log level in `conf/operator.yaml`:
```yaml
server:
  log_level: "debug"
```

## Performance Considerations

- **Memory usage**: Events are stored in database and JSONL files
- **Network**: SSE maintains persistent connections
- **Storage**: JSONL files grow with job duration
- **Scalability**: Single-lane constraint limits concurrent jobs

## Future Enhancements

- Event filtering and search
- Event retention policies
- Webhook notifications
- Event replay functionality
- Performance metrics and monitoring
