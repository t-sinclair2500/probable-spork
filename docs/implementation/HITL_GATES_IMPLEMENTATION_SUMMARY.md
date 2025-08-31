# HITL Gates Implementation Summary

## Overview
This document summarizes the implementation of Human-in-the-Loop (HITL) gates with decisions, timeouts, and patch hooks as specified in P6-5.

## Implemented Features

### 1. Enhanced Gate Models
- **Gate Model**: Added `patch` and `auto_approved` fields
- **GateAction Model**: Added `patch` field for JSON patches
- **Database Schema**: Updated to store patch data and auto-approval flags

### 2. Patch System
- **Script Patches**: Text replacement and section replacement
- **Storyboard Patches**: Duration adjustments for beats
- **Audio Patches**: Level adjustments in dB
- **Direct Patch Application**: Endpoint to apply patches without gate approval

### 3. Timeout-Based Auto-Approval
- **Configuration**: `auto_approve_after_s` field in `conf/operator.yaml`
- **Background Task**: Periodic checking for expired gates
- **Auto-Approval Logic**: Automatic approval after configured timeouts
- **Timer Attribution**: Gates marked as approved by "timer"

### 4. Gate Decision Storage
- **Filesystem Storage**: Decisions stored under `runs/<id>/gates/<stage>.json`
- **Database Integration**: Decisions also stored in SQLite for querying
- **Event Logging**: All decisions logged to job events

### 5. Enhanced Routes

#### Gate Management
- `POST /api/v1/jobs/{job_id}/approve` - Approve gate with optional patch
- `POST /api/v1/jobs/{job_id}/reject` - Reject gate with optional patch
- `POST /api/v1/jobs/{job_id}/resume` - Resume job with patch application
- `GET /api/v1/jobs/{job_id}/gates/status` - Get current gate statuses
- `GET /api/v1/jobs/{job_id}/gates/decisions` - List all gate decisions
- `GET /api/v1/jobs/{job_id}/gates/{stage}/decision` - Get specific gate decision

#### Patch Management
- `POST /api/v1/jobs/{job_id}/patches/{stage}/apply` - Apply patch directly
- `GET /api/v1/patches/types` - Get supported patch types and examples

### 6. Orchestrator Integration
- **Gate Creation**: Automatic gate creation when stages require approval
- **Timeout Checking**: Background task checking for expired gates
- **Auto-Approval**: Automatic gate approval and job resumption
- **Patch Application**: Integration with patch system for rejected gates

## Configuration

### Operator Configuration (`conf/operator.yaml`)
```yaml
gates:
  script:
    required: true
    auto_approve: false
    auto_approve_after_s: null  # null = no auto-approval
  
  storyboard:
    required: true
    auto_approve: false
    auto_approve_after_s: null
  
  assets:
    required: true
    auto_approve: false
    auto_approve_after_s: null
  
  audio:
    required: true
    auto_approve: false
    auto_approve_after_s: null
  
  # Optional gates with auto-approval
  outline:
    required: false
    auto_approve: true
    auto_approve_after_s: 1800  # 30 minutes
```

## Patch Examples

### Script Patch
```json
{
  "type": "text_replace",
  "replacements": [
    {"old": "old text", "new": "new text"}
  ]
}
```

### Storyboard Patch
```json
{
  "type": "duration_adjust",
  "beat_adjustments": [
    {"beat_id": "intro_beat", "duration": 15}
  ]
}
```

### Audio Patch
```json
{
  "type": "level_adjust",
  "level_change_db": 3
}
```

## Usage Flow

### 1. Job Execution
- Job runs through pipeline stages
- When a stage requiring approval completes, job pauses
- Gate is created and job status set to `NEEDS_APPROVAL`

### 2. Gate Decision
- Operator reviews artifacts and makes decision
- Can approve, reject, or reject with patch
- Decision stored to filesystem and database

### 3. Auto-Approval
- Background task checks for expired gates
- If timeout reached, gate auto-approved
- Job automatically resumes execution

### 4. Patch Application
- If gate rejected with patch, patch applied to artifacts
- Gate automatically approved after patch application
- Job resumes from the same stage

## Testing

### Test Script
Run `python test_hitl_gates.py` to verify:
- Gate creation and management
- Patch application
- Configuration loading
- Decision storage

### Manual Testing
1. Start FastAPI server: `make op-console`
2. Create a job that reaches a gate
3. Test approve/reject with patches
4. Verify auto-approval works
5. Check decision storage

## Success Criteria Met

✅ **Gate Decisions**: Routes accept `GateDecision` with approve/reject, notes, and patches  
✅ **Patch Targets**: Support for Script, Storyboard, and Audio modifications  
✅ **Timeouts**: Per-gate configuration with `auto_approve_after_s`  
✅ **Decision Storage**: All decisions stored under `runs/<id>/gates/<stage>.json`  
✅ **Reject Handling**: Reject pauses job safely, resume re-runs stage with patch  
✅ **Auto-Approval**: Works when configured, decision recorded with `by: "timer"`  

## Files Modified

- `fastapi_app/models.py` - Enhanced models with patch support
- `fastapi_app/db.py` - Updated schema and methods for patches
- `fastapi_app/routes.py` - New routes for gate management and patches
- `fastapi_app/orchestrator.py` - Timeout checking and auto-approval logic
- `fastapi_app/__init__.py` - Background task for timeout checking
- `conf/operator.yaml` - Updated configuration format
- `test_hitl_gates.py` - Test script for verification

## Next Steps

1. **Integration Testing**: Test with real pipeline stages
2. **UI Integration**: Connect to Gradio interface
3. **Advanced Patches**: Enhance patch types for more complex modifications
4. **Validation**: Add patch validation and error handling
5. **Monitoring**: Add metrics for gate performance and operator efficiency
