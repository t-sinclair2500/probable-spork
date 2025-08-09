# Background Agent 1: Data Integration & Testing Track

You are a senior Python developer working in an Ubuntu-based Cursor background agent environment. Your mission is to resolve critical blockers in the data ingestion pipeline and strengthen the testing foundation for a Raspberry Pi content automation system.

## Environment Context

You are working in a clean Ubuntu VM that has been set up with:
- Python 3.x with venv created at `.venv`
- System dependencies: ffmpeg, git, jq, sqlite3, build-essential, cmake
- Python dependencies installed from `requirements.txt`

**Important**: You do NOT have access to:
- Ollama service (will not be running)
- whisper.cpp binary (not built in this environment) 
- YouTube/Reddit/OpenAI API keys (will cause some tests to fail)
- macOS-specific tools or paths

## Your Assigned Work Track

You are responsible for **Track A: Data Integration & Testing** from the Status Board in `MASTER_TODO.md`. Your parallel work track includes:

**P0 (Critical - Ship v1):**
- **A1**: Fix YouTube ingestion (resolve 404s; graceful fallbacks)
- **H7**: E2E test robustness (skip when deps missing)  
- **H2**: Create .env.example file at repo root

**P1 (Polish):**
- **E2**: YouTube uploader dry-run + auth flow
- **F2**: Healthcheck enhancements (last successful step + queue depths)

## Key Files to Review

Start by reading these files to understand the current state:

1. **`MASTER_TODO.md`** - Your canonical task list with detailed acceptance criteria
2. **`PURPOSE_SUMMARY.md`** - High-level system overview
3. **`bin/niche_trends.py`** - Current ingestion script with YouTube API 404 issues
4. **`bin/test_e2e.py`** - E2E test that needs robustness improvements
5. **`bin/healthcheck.py`** - Health monitoring that needs queue depth reporting
6. **`bin/youtube_upload.py`** - YouTube uploader needing dry-run flow
7. **`AGENT_HANDOFF_PLAN.md`** - Contains specific YouTube API debugging context (lines 26-37)

## Environment-Aware Implementation Strategy

### For A1 (YouTube API Fix):
- Debug the 404 error in `bin/niche_trends.py` 
- The error is: `404 Client Error: Not Found for url: https://www.googleapis.com/youtube/v3/videos?part=snippet&chart=mostPopular&regionCode=US&maxResults=25&videoCategoryId=27&key=...`
- Test with different category IDs (28, 25, 24) or remove category filter entirely
- Implement graceful fallback when YouTube fails (continue with Reddit/Google Trends)
- **Note**: You won't have real API keys, so focus on error handling and fallback logic

### For H7 (E2E Test Robustness):
- Modify `bin/test_e2e.py` to gracefully skip when:
  - No API keys present in environment
  - whisper.cpp binary not found
  - Ollama service not running
- Still validate the core flow with placeholder data
- Use environment variable checks and try/except blocks

### For H2 (.env.example):
- Create `.env.example` at repo root with all required environment variables
- Include clear comments about which are required vs optional
- Reference existing patterns in `README.md` and `TYLER_TODO.md`

### For E2 (YouTube Uploader):
- Focus on the dry-run functionality and OAuth setup documentation
- Test upload payload generation without actual upload
- **Note**: Real YouTube upload won't work without OAuth tokens

### For F2 (Healthcheck):
- Enhance `bin/healthcheck.py` to report:
  - Last successful step from `jobs/state.jsonl`
  - Queue depths from various JSON files
  - Service status (but account for missing services in your environment)

## Testing Strategy

Since you're in a constrained environment:

1. **Use the existing venv**: `. .venv/bin/activate` before running Python scripts
2. **Test with placeholders**: Focus on code paths that work without external services
3. **Validate error handling**: Ensure graceful degradation when services unavailable
4. **Check file outputs**: Verify scripts create expected JSON/log files
5. **Use `python bin/check_env.py`** to validate your changes don't break basic checks

## Acceptance Criteria

- **A1**: YouTube API errors handled gracefully; fallback to other sources works
- **H7**: `python bin/test_e2e.py` passes even without API keys/whisper.cpp
- **H2**: Complete .env.example with all documented variables
- **E2**: Dry-run mode works; OAuth flow documented  
- **F2**: Health endpoint returns meaningful status even with missing services

## Implementation Priority

1. **H2** (.env.example) - Quick win, enables other testing
2. **H7** (E2E robustness) - Critical for CI/testing in constrained environments
3. **A1** (YouTube API) - Core data ingestion fix
4. **F2** (Healthcheck) - Monitoring improvements
5. **E2** (YouTube uploader) - Upload capability

## Success Evidence

For each completed task, provide:
- Working command examples
- Sample outputs/logs
- Test results showing graceful degradation
- Documentation of any assumptions or limitations in the Ubuntu environment

**Begin with H2 (.env.example) as it will help with subsequent testing. Focus on making the system resilient to missing external dependencies while maintaining core functionality.**
