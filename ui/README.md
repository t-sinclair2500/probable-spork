# Gradio UI for Operator Console

This directory contains the Gradio-based web interface for the Probable Spork Operator Console.

## Overview

The Gradio UI provides a user-friendly web interface for:
- **Config & Launch Page**: View and validate configuration, create new jobs
- **Job Console Page**: Monitor job progress, manage HITL gates, view artifacts

## Features

### Authentication
- Bearer token authentication via `ADMIN_TOKEN` environment variable
- Default token: `default-admin-token-change-me` (change in production)

### Config & Launch Page
- Load and display current pipeline configuration
- Validate configuration via API
- Create new jobs with customizable parameters:
  - Topic slug and intent
  - Target length and tone
  - Testing mode (reuse vs live)
  - Optional notes

### Job Console Page
- List and select jobs
- Real-time stage progress monitoring
- HITL gate management (approve/reject/resume)
- Artifact viewing and download
- Live event streaming with polling fallback

## Usage

### Prerequisites
1. FastAPI backend must be running (`make op-console`)
2. Gradio dependency installed (`pip install gradio`)

### Launch Options

#### Option 1: Launch Gradio UI only
```bash
make gradio-ui
```
- UI available at: http://127.0.0.1:7860
- Requires FastAPI backend to be running separately

#### Option 2: Launch both FastAPI + Gradio UI
```bash
make op-console-full
```
- FastAPI: http://127.0.0.1:8008
- Gradio UI: http://127.0.0.1:7860
- Automatically starts both services

### Testing
```bash
make test-gradio-ui
```
Tests basic UI components and dependencies.

## Architecture

### Components
- **APIClient**: HTTP client for FastAPI backend communication
- **EventStreamer**: Real-time event streaming with polling fallback
- **Config & Launch Page**: Job creation and configuration management
- **Job Console Page**: Job monitoring and gate management

### State Management
- Global API client instance managed via module-level variables
- Authentication state controls UI visibility
- Job context maintained in Gradio State components

### Event Handling
- Real-time updates via polling (2-second intervals)
- Fallback to manual refresh for reliability
- Event display in dedicated panel

## Configuration

### Environment Variables
- `ADMIN_TOKEN`: Authentication token (defaults to `default-admin-token-change-me`)
- `API_BASE_URL`: FastAPI backend URL (defaults to `http://127.0.0.1:8008/api/v1`)

### API Endpoints Used
- `GET /config/operator` - Load configuration
- `POST /config/validate` - Validate configuration
- `GET /jobs` - List jobs
- `GET /jobs/{id}` - Get job details
- `POST /jobs` - Create job
- `POST /jobs/{id}/approve` - Approve gate
- `POST /jobs/{id}/reject` - Reject gate
- `POST /jobs/{id}/resume` - Resume job
- `GET /jobs/{id}/events` - Get job events

## Security

- Local-only binding by default (127.0.0.1)
- Bearer token authentication required
- CORS disabled by default
- No persistent session storage

## Troubleshooting

### Common Issues

1. **"Please initialize API client first"**
   - Ensure FastAPI backend is running
   - Check admin token is correct
   - Verify network connectivity

2. **UI not responding**
   - Check browser console for errors
   - Verify Gradio server is running
   - Check port 7860 is available

3. **API calls failing**
   - Verify FastAPI backend is running on port 8008
   - Check authentication token
   - Review backend logs for errors

### Debug Mode
Launch with debug enabled:
```python
from ui.gradio_app import launch_ui
launch_ui(debug=True)
```

## Development

### Adding New Features
1. Update the appropriate page function (`create_config_launch_page` or `create_job_console_page`)
2. Add new API endpoints to `APIClient` class
3. Update event handling if needed
4. Test with `make test-gradio-ui`

### Styling
- Uses Gradio's built-in components and themes
- Custom styling via Gradio's CSS classes
- Responsive layout with proper scaling

### Testing
- Unit tests for individual components
- Integration tests for API communication
- UI behavior testing via manual interaction
