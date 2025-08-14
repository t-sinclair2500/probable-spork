# FastAPI Operator Console

This is the FastAPI-based operator console for the Probable Spork video pipeline orchestrator.

## Features

- **Job Management**: Create, view, and manage pipeline jobs
- **HITL Gates**: Human-in-the-loop approval/rejection for key stages
- **Real-time Events**: Server-Sent Events (SSE) and polling endpoints
- **Secure API**: Bearer token authentication with configurable CORS
- **Configuration**: Loads settings from `conf/operator.yaml`

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the server**:
   ```bash
   make op-console
   # or directly:
   python3 run_server.py
   ```

3. **Access the API**:
   - API: http://127.0.0.1:8008/api/v1
   - Interactive docs: http://127.0.0.1:8008/docs
   - Health check: http://127.0.0.1:8008/api/v1/healthz

## Configuration

The server configuration is loaded from `conf/operator.yaml`:

```yaml
server:
  host: "127.0.0.1"
  port: 8008
  log_level: "info"

security:
  admin_token_env: "ADMIN_TOKEN"
  cors:
    enabled: false
    allow_origins: []

gates:
  script:
    required: true
    auto_approve: false
    timeout_minutes: 60
```

## API Endpoints

### Core Endpoints
- `GET /healthz` - Health check (no auth required)
- `GET /config/operator` - Get sanitized configuration
- `POST /config/validate` - Validate configuration

### Job Management
- `POST /jobs` - Create a new job
- `GET /jobs` - List all jobs
- `GET /jobs/{id}` - Get job details
- `POST /jobs/{id}/approve` - Approve a gate
- `POST /jobs/{id}/reject` - Reject a gate
- `POST /jobs/{id}/resume` - Resume a paused job
- `POST /jobs/{id}/cancel` - Cancel a job

### Events and Artifacts
- `GET /jobs/{id}/events` - Get job events (polling)
- `GET /jobs/{id}/events/stream` - Stream events via SSE
- `GET /jobs/{id}/artifacts` - Get job artifacts

## Authentication

All endpoints (except `/healthz`) require Bearer token authentication:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://127.0.0.1:8008/api/v1/jobs
```

Set the `ADMIN_TOKEN` environment variable or use the default from config.

## Testing

Run the test suite:

```bash
make test-api
# or directly:
python3 test_api.py
```

## Development

The console is built with:
- **FastAPI**: Modern, fast web framework
- **SQLite**: Lightweight database for job metadata
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server

## Architecture

- **Models** (`models.py`): Pydantic models for data validation
- **Database** (`db.py`): SQLite operations and job persistence
- **Routes** (`routes.py`): API endpoint definitions
- **Security** (`security.py`): Authentication and CORS handling
- **Config** (`config.py`): Configuration management

## Integration

The console integrates with the existing pipeline:
- Loads configuration from `bin/core.py` functions
- Respects existing pipeline structure and artifacts
- Provides HITL gates for operator oversight
- Maintains job state in SQLite + filesystem

## Security Notes

- **Default**: Local-only binding (127.0.0.1)
- **CORS**: Disabled by default for security
- **Authentication**: Required for all operations
- **Tokens**: Store securely in environment variables
