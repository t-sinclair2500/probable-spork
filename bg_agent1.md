# Local Agent 1: Data Integration & Testing Track

You are a senior Python developer working locally on a macOS development environment. Your mission is to resolve critical blockers in the data ingestion pipeline and strengthen the testing foundation for a Raspberry Pi content automation system.

## Environment Context

You are working in the full local development environment that includes:
- Python 3.x with venv at `.venv` (already activated)
- System dependencies: ffmpeg, git, jq, sqlite3, build tools
- Python dependencies installed from `requirements.txt`
- **Ollama service**: Available locally for LLM operations
- **whisper.cpp**: May be available at `~/whisper.cpp/build/bin/whisper-cli`
- **Local file system**: Full access to macOS tools and paths

**Available for testing**:
- Real API keys in `.env` (if configured)
- Local Ollama service for LLM calls
- Full macOS development stack
- Interactive testing and debugging

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

## Local Development Implementation Strategy

### For A1 (YouTube API Fix):
- Debug the 404 error in `bin/niche_trends.py` 
- The error is: `404 Client Error: Not Found for url: https://www.googleapis.com/youtube/v3/videos?part=snippet&chart=mostPopular&regionCode=US&maxResults=25&videoCategoryId=27&key=...`
- **Test with real API key**: Add `YOUTUBE_API_KEY` to `.env` and test different approaches
- Try different category IDs (28, 25, 24) or remove category filter entirely
- Test regionCode variations (US, GB, None)
- Implement robust fallback when YouTube fails (continue with Reddit/Google Trends)
- **Interactive debugging**: Use breakpoints and real API responses

### For H7 (E2E Test Robustness):
- Enhance `bin/test_e2e.py` to gracefully handle missing dependencies:
  - Check for API keys and skip external calls if missing
  - Detect whisper.cpp binary and skip audio processing if unavailable
  - Test Ollama connectivity and fallback to offline mode
- **Full end-to-end testing**: Run with real services when available
- Add comprehensive test coverage for both online and offline modes

### For H2 (.env.example):
- Create comprehensive `.env.example` at repo root
- Include all discovered environment variables from code analysis
- Add clear documentation for required vs optional keys
- Test the example file by copying to `.env.test` and validating

### For E2 (YouTube Uploader):
- Implement full OAuth flow for YouTube uploads
- **Test real upload**: Set up OAuth credentials and test dry-run uploads
- Generate proper video metadata and thumbnails
- Test with actual video files from the pipeline

### For F2 (Healthcheck):
- Enhance `bin/healthcheck.py` with comprehensive monitoring:
  - Real-time service status (Ollama, whisper.cpp availability)
  - Last successful step analysis from `jobs/state.jsonl`
  - Queue depths and pipeline health metrics
  - **Live testing**: Monitor actual pipeline runs

## Local Testing Strategy

With full local environment access:

1. **Interactive development**: Use the existing venv and full IDE debugging capabilities
2. **Real service testing**: Test with actual Ollama, whisper.cpp, and API services when available
3. **Comprehensive validation**: Test both online and offline modes thoroughly
4. **Live pipeline runs**: Execute `make run-once` and `make blog-once` to test end-to-end
5. **API validation**: Use real API keys to test and debug integration issues
6. **Performance monitoring**: Use `python bin/check_env.py` and health endpoints

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

**Start with A1 (YouTube API) since you can test with real keys and debug interactively. Use H2 (.env.example) to document all required environment variables. Focus on both robust error handling AND full functionality when services are available.**
