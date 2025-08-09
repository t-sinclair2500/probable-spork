# AI Agent Handoff Plan: Complete Pipeline to Full Video

## Mission Statement
**OBJECTIVE**: Debug remaining issues and complete all TODO items until we have a full, viewable video from end-to-end pipeline execution.

**SUCCESS CRITERIA**: 
- Execute `make run-once` without errors
- Produce a complete MP4 video in `videos/` directory that is viewable and contains:
  - Professional TTS voiceover (already working)
  - Proper video assembly with assets
  - Correct timing and audio sync
  - Generated thumbnail
- All critical blockers in MASTER_TODO.md resolved

## Current State Assessment

### ✅ WHAT'S WORKING
- **TTS Pipeline**: Professional Coqui TTS generating 152s voiceovers
- **Asset Fetching**: 5+ assets downloaded with proper licensing
- **Configuration**: Cross-platform setup (Mac dev + Pi production)
- **Script Generation**: Outline → Script → Metadata working
- **Basic Infrastructure**: Logging, locking, guards all functional

### 🚨 CRITICAL BLOCKERS TO FIX

#### 1. YouTube API 404 Errors (A1 - CRITICAL)
**Location**: `bin/niche_trends.py`
**Error**: `404 Client Error: Not Found for url: https://www.googleapis.com/youtube/v3/videos?part=snippet&chart=mostPopular&regionCode=US&maxResults=25&videoCategoryId=27&key=AIzaSyAcGyvcDOJEQPGJLpnmRjT-P3JtCYqkDRg`

**Debug Steps**:
1. Check if YouTube API key is valid/active
2. Verify category ID 27 is correct (Education category)
3. Test with different category IDs or remove category filter
4. Check API quota limits and billing
5. Implement better error handling to continue with other sources

**Files to examine**: `bin/niche_trends.py`, `.env`, `conf/global.yaml`

#### 2. Video Assembly Interruption (C3)
**Issue**: `assemble_video.py` was interrupted during last `make run-once`
**Symptoms**: Process stopped during video assembly phase

**Debug Steps**:
1. Check if video assembly completed successfully
2. Verify all required inputs are present (assets, voiceover, script)
3. Test video assembly in isolation: `python bin/assemble_video.py`
4. Check for memory/resource constraints during assembly
5. Verify FFmpeg/MoviePy dependencies are working properly

**Files to examine**: `bin/assemble_video.py`, generated video files, logs in `jobs/state.jsonl`

## Execution Plan

### Phase 1: Diagnostic & Status Check (MANDATORY FIRST STEP)

```bash
# Navigate to project
cd /Users/tylersinclair/Documents/GitHub/probable-spork

# Check current state
ls -la videos/
ls -la voiceovers/
ls -la assets/
ls -la scripts/

# Check last pipeline run status
tail -20 jobs/state.jsonl

# Test individual components
python bin/niche_trends.py  # Check API issues
python bin/assemble_video.py  # Check video assembly
```

### Phase 2: Fix Critical Blockers

#### 2.1 YouTube API Repair
1. **Examine API configuration**:
   ```bash
   grep -r "youtube" conf/ .env* bin/niche_trends.py
   ```

2. **Test API key manually**:
   - Try different YouTube API endpoints
   - Check quotas in Google Cloud Console
   - Verify API key permissions and restrictions

3. **Implement fallback strategy**:
   - If YouTube API fails, ensure Reddit/Google Trends provide enough data
   - Modify script to continue with partial data
   - Add better error handling

#### 2.2 Complete Video Assembly
1. **Verify assembly inputs**:
   ```bash
   # Check all required files exist
   ls scripts/2025-08-09_ai-tools.*
   ls voiceovers/2025-08-09_ai-tools.*
   ls assets/2025-08-09_ai-tools/
   ```

2. **Test video assembly**:
   ```bash
   python bin/assemble_video.py
   ```

3. **Debug any MoviePy/FFmpeg issues**:
   - Check asset file formats are supported
   - Verify sufficient disk space and memory
   - Test with simpler assembly if needed

### Phase 3: End-to-End Pipeline Test

```bash
# Clean run from scratch
make run-once
```

**Expected outputs**:
- New topics in `data/topics_queue.json`
- New script files in `scripts/`
- Downloaded assets in `assets/`
- Generated voiceover in `voiceovers/`
- **FINAL VIDEO** in `videos/` (this is the success metric)

### Phase 4: Video Validation

```bash
# Check video properties
ffprobe videos/[latest].mp4

# Verify video is playable
open videos/[latest].mp4  # On Mac
```

**Quality checks**:
- Video duration matches expected length (~2.5 minutes)
- Audio is clear and synchronized
- Visual assets are properly integrated
- No corruption or encoding errors

## Fallback Strategies

### If YouTube API Cannot Be Fixed
1. **Temporary workaround**: Use existing topics from queue
2. **Alternative sources**: Rely more heavily on Reddit/Google Trends
3. **Manual seed**: Add topics manually to `data/topics_queue.json`

### If Video Assembly Fails
1. **Simplified assembly**: Create basic video with static images
2. **Audio-only**: Generate podcast-style content
3. **Debug components**: Test individual MoviePy operations

## Files Requiring Attention

### High Priority
- `bin/niche_trends.py` - Fix YouTube API errors
- `bin/assemble_video.py` - Complete video assembly
- `.env` - Verify API keys and configuration
- `jobs/state.jsonl` - Check for error patterns

### Medium Priority  
- `bin/blog_generate_post.py` - Complete blog functionality gaps
- `bin/blog_post_wp.py` - Finish WordPress integration
- `conf/global.yaml` - Verify all settings are correct

### Reference Documents
- `MASTER_TODO.md` - Single source of truth for remaining work
- `README.md` - Setup and configuration guide
- `Makefile` - Build and execution targets

## Success Metrics

### Immediate (required for handoff completion)
- [ ] `make run-once` completes without critical errors
- [ ] Video file exists in `videos/` directory
- [ ] Video is playable and contains expected content
- [ ] Pipeline logs show successful completion in `jobs/state.jsonl`

### Secondary (nice to have)
- [ ] YouTube API returning ≥50 rows/day
- [ ] Blog pipeline also working end-to-end
- [ ] All tests in `make test` passing

## Emergency Contacts & Resources

**Repository**: `/Users/tylersinclair/Documents/GitHub/probable-spork`
**Key Configuration**: `conf/global.yaml`, `.env`
**Logs**: `jobs/state.jsonl`
**Status Document**: `MASTER_TODO.md`

**If completely stuck**: Focus on getting ANY complete video output, even if it means simplifying the assembly process or using fallback data sources. The goal is demonstrable end-to-end functionality.

---

**AGENT INSTRUCTIONS**: Work through this plan systematically. Do not skip the diagnostic phase. Focus on the critical blockers first. Success is measured by a viewable video file, not perfect implementation of every feature.
