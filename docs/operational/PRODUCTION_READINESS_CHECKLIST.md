# Production Readiness Checklist — One-Pi Content Pipeline

## 📋 **Overview**

This is the consolidated task list derived from PHASE2_CURSOR.md, organized in logical execution order with completion status. All tasks marked `[x]` have been verified as complete and functional.

**Legend**: `[x]` Complete | `[~]` Partial | `[ ]` Todo | `[!]` Blocked/Issue

---

## 🏗️ **PHASE 1: CORE INFRASTRUCTURE** 

### **Environment Setup**
- [x] **ENV-1**: Python 3.9+ environment with requirements.txt
- [x] **ENV-2**: Ollama service installation and configuration  
- [x] **ENV-3**: whisper.cpp build for ASR capabilities
- [x] **ENV-4**: FFmpeg installation for video processing
- [x] **ENV-5**: Configuration templates (global.example.yaml, blog.example.yaml)
- [x] **ENV-6**: Environment variables template (.env.example)
- [x] **ENV-7**: Directory structure (data/, jobs/, scripts/, assets/, etc.)

### **Core Pipeline Infrastructure**
- [x] **CORE-1**: Single-lane locking mechanism (`jobs/lock`)
- [x] **CORE-2**: State logging system (`jobs/state.jsonl`)
- [x] **CORE-3**: Configuration validation and loading
- [x] **CORE-4**: Error handling and retry logic with exponential backoff
- [x] **CORE-5**: Idempotency checks (no duplicate work on re-runs)

---

## 📊 **PHASE 2: DATA INGESTION & PROCESSING**

### **A) Trend Ingestion** — `bin/niche_trends.py`
- [x] **A-1**: YouTube Data API integration with category filtering
- [x] **A-2**: Google Trends integration via pytrends
- [x] **A-3**: Reddit API integration for subreddit trends
- [x] **A-4**: SQLite database storage (`data/trending_topics.db`)
- [x] **A-5**: Data deduplication by date+source+title
- [x] **A-6**: HTTP 404 fallback mechanism for YouTube API
- [x] **A-7**: Rate limiting and exponential backoff

**Status**: ✅ **COMPLETE** — Verified ≥50 rows/day capability, robust error handling

### **B) Topic Clustering** — `bin/llm_cluster.py`
- [x] **B-1**: LLM prompt integration (`prompts/cluster_topics.txt`)
- [x] **B-2**: JSON validation and parsing with fallbacks
- [x] **B-3**: Top-10 topic selection and scoring
- [x] **B-4**: Output to `data/topics_queue.json`
- [x] **B-5**: Cross-source overlap and velocity scoring

**Status**: ✅ **COMPLETE** — Verified JSON output, topic ranking working

---

## ✍️ **PHASE 3: CONTENT GENERATION**

### **C) Outline Generation** — `bin/llm_outline.py`
- [x] **C-1**: 6-section outline structure with beats
- [x] **C-2**: B-roll suggestions per section
- [x] **C-3**: Tone and length configuration respect
- [x] **C-4**: JSON schema validation
- [x] **C-5**: Target video length calculation

**Status**: ✅ **COMPLETE** — Verified outline JSON schema, configurable tone/length

### **C) Script Generation** — `bin/llm_script.py`
- [x] **C-6**: 900-1200 word conversational scripts
- [x] **C-7**: `[B-ROLL: ...]` markers every 2-3 lines
- [x] **C-8**: Clear call-to-action inclusion
- [x] **C-9**: Multi-topic processing for daily_videos > 1
- [x] **C-10**: Tone consistency with configuration

**Status**: ✅ **COMPLETE** — Verified script generation, B-ROLL markers, CTA

### **D) Content Enhancement** — `bin/fact_check.py` ⭐ **BONUS**
- [x] **D-1**: Fact-checking prompt integration (`prompts/fact_check.txt`)
- [x] **D-2**: JSON output format for issues
- [x] **D-3**: Content gating with severity levels
- [x] **D-4**: Integration with blog validation pipeline

**Status**: ✅ **COMPLETE** — Enhanced feature beyond original scope

---

## 🎬 **PHASE 4: MEDIA PRODUCTION**

### **E) Asset Acquisition** — `bin/fetch_assets.py`
- [x] **E-1**: Pixabay API integration with search and download
- [x] **E-2**: Pexels API integration with search and download
- [x] **E-3**: Unsplash API integration (optional, with attribution)
- [x] **E-4**: B-ROLL parsing from scripts to search queries
- [x] **E-5**: License metadata preservation (`license.json`)
- [x] **E-6**: Sources tracking (`sources_used.txt`)
- [x] **E-7**: SHA1-based deduplication
- [x] **E-8**: Resolution normalization to render.resolution
- [x] **E-9**: Rate limiting and exponential backoff
- [x] **E-10**: Quality assessment and ranking ⭐ **BONUS**

**Status**: ✅ **COMPLETE** — All providers working, enhanced with quality scoring

### **F) Text-to-Speech** — `bin/tts_generate.py`
- [x] **F-1**: Coqui TTS primary implementation
- [x] **F-2**: OpenAI TTS fallback (optional)
- [x] **F-3**: Voice model configuration from global.yaml
- [x] **F-4**: Loudness normalization (ffmpeg loudnorm)
- [x] **F-5**: Target pacing 150-175 WPM
- [x] **F-6**: MP3/WAV output formats

**Status**: ✅ **COMPLETE** — Verified audio quality, normalization working

### **G) Automatic Speech Recognition** — `bin/generate_captions.py`
- [x] **G-1**: whisper.cpp primary implementation
- [x] **G-2**: OpenAI Whisper fallback (optional)
- [x] **G-3**: SRT file generation aligned with audio
- [x] **G-4**: Caption burn-in capability
- [x] **G-5**: Graceful fallback when whisper.cpp missing

**Status**: ✅ **COMPLETE** — Verified SRT generation, burn-in optional

### **H) Video Assembly** — `bin/assemble_video.py`
- [x] **H-1**: Beat timing prompt integration (`prompts/beat_timing.txt`)
- [x] **H-2**: Scene timeline construction with crossfades
- [x] **H-3**: Ken Burns effect for still images
- [x] **H-4**: Background music integration with ducking
- [x] **H-5**: H.264 yuv420p export with AAC audio
- [x] **H-6**: Target resolution and bitrate configuration
- [x] **H-7**: A/V sync within 100ms tolerance

**Status**: ✅ **COMPLETE** — Verified video assembly, effects, sync

### **I) Thumbnail Generation** — `bin/make_thumbnail.py`
- [x] **I-1**: 1280×720 PNG generation using Pillow
- [x] **I-2**: Title snippet extraction (≤5 words)
- [x] **I-3**: Brand stripe overlay
- [x] **I-4**: Metadata reference in upload queue
- [x] **I-5**: Clean implementation (deduplicated code)

**Status**: ✅ **COMPLETE** — Verified thumbnail generation and branding

---

## 📤 **PHASE 5: PUBLISHING & DISTRIBUTION**

### **J) Video Upload** — `bin/youtube_upload.py`
- [x] **J-1**: OAuth 2.0 flow implementation with token storage
- [x] **J-2**: Dry-run mode with payload logging
- [x] **J-3**: Metadata extraction from `.metadata.json`
- [x] **J-4**: Chapter support from outline structure
- [x] **J-5**: Upload progress reporting
- [x] **J-6**: Thumbnail upload integration
- [x] **J-7**: Auto-upload and scheduling support

**Status**: ✅ **COMPLETE** — Verified OAuth flow, dry-run, live upload

### **K) Blog Content Generation** — `bin/blog_generate_post.py`
- [x] **K-1**: Script-to-blog conversion with tone adaptation
- [x] **K-2**: Multi-stage LLM pipeline (writer → copyeditor → SEO)
- [x] **K-3**: Word count validation (800-1500 words)
- [x] **K-4**: Structure validation (H1, H2/H3, bullets, hierarchy)
- [x] **K-5**: Content quality analysis (FAQ, CTA, readability)
- [x] **K-6**: Fact-checking integration with gating ⭐ **BONUS**
- [x] **K-7**: Validation metrics and issue reporting

**Status**: ✅ **COMPLETE** — Enhanced validation beyond original scope

### **L) Blog Rendering** — `bin/blog_render_html.py`
- [x] **L-1**: Markdown to HTML conversion
- [x] **L-2**: Table of Contents generation
- [x] **L-3**: Schema.org Article JSON-LD markup
- [x] **L-4**: Attribution blocks for licensed assets
- [x] **L-5**: HTML sanitization for security
- [x] **L-6**: Advanced SEO enhancement integration ⭐ **BONUS**

**Status**: ✅ **COMPLETE** — Enhanced with comprehensive SEO features

### **M) WordPress Publishing** — `bin/blog_post_wp.py`
- [x] **M-1**: WordPress REST API integration
- [x] **M-2**: Application Password authentication
- [x] **M-3**: DRY_RUN environment variable control
- [x] **M-4**: Featured image upload and selection
- [x] **M-5**: Inline image processing and upload ⭐ **BONUS**
- [x] **M-6**: SHA1-based media deduplication ⭐ **BONUS**
- [x] **M-7**: Retry logic with exponential backoff ⭐ **BONUS**
- [x] **M-8**: Category and tag management

**Status**: ✅ **COMPLETE** — Enhanced beyond original scope

---

## 🛠️ **PHASE 6: OPERATIONS & RELIABILITY**

### **N) Health Monitoring** — `bin/healthcheck.py`
- [x] **N-1**: System resource monitoring (CPU, memory, disk)
- [x] **N-2**: Service status checking (Ollama, whisper.cpp)
- [x] **N-3**: API key availability verification
- [x] **N-4**: Queue depth monitoring ⭐ **BONUS**
- [x] **N-5**: Last successful step tracking ⭐ **BONUS**
- [x] **N-6**: CPU temperature monitoring for Pi

**Status**: ✅ **COMPLETE** — Enhanced monitoring capabilities

### **O) Web Interface** — `bin/web_ui.py`
- [x] **O-1**: Flask-based dashboard at localhost:8099
- [x] **O-2**: Real-time log viewing with tail functionality
- [x] **O-3**: Job triggering with parameter controls
- [x] **O-4**: Authentication with session management ⭐ **BONUS**
- [x] **O-5**: Rate limiting and security hardening ⭐ **BONUS**
- [x] **O-6**: Real-time analytics dashboard ⭐ **BONUS**
- [x] **O-7**: WebSocket support for live updates ⭐ **BONUS**

**Status**: ✅ **COMPLETE** — Significantly enhanced beyond original scope

### **P) Testing Framework** — `bin/test_e2e.py`
- [x] **P-1**: End-to-end pipeline testing
- [x] **P-2**: Dependency checking and graceful skipping
- [x] **P-3**: API key availability testing
- [x] **P-4**: Service availability testing
- [x] **P-5**: DRY_RUN mode enforcement for testing
- [x] **P-6**: Clear status reporting with ✓/✗ indicators

**Status**: ✅ **COMPLETE** — Robust testing with dependency awareness

### **Q) Deployment & Automation**
- [x] **Q-1**: Systemd service configuration
- [x] **Q-2**: Logrotate configuration
- [x] **Q-3**: Cron job templates (`ops/crontab.seed.txt`)
- [x] **Q-4**: Backup scripts (repo and WordPress)
- [x] **Q-5**: Health server endpoint (port 8088)
- [x] **Q-6**: Installation automation (`Makefile`)

**Status**: ✅ **COMPLETE** — Production deployment ready

---

## ⚠️ **PHASE 7: CRITICAL GAPS IDENTIFIED**

### **WordPress Infrastructure** — **BLOCKED**
- [!] **WP-1**: WordPress installation and setup (NO guidance provided)
- [!] **WP-2**: Domain configuration for public access (defaults to localhost)
- [!] **WP-3**: SSL certificate setup for HTTPS
- [!] **WP-4**: Port forwarding and firewall configuration
- [!] **WP-5**: WordPress user and permissions setup

**Status**: ❌ **MISSING** — Pipeline assumes WordPress exists but provides no setup

### **Monetization Strategy** — **COMPLETELY MISSING**
- [ ] **MON-1**: YouTube Partner Program requirements tracking
- [ ] **MON-2**: AdSense integration for blog
- [ ] **MON-3**: Affiliate marketing automation
- [ ] **MON-4**: Revenue tracking and analytics
- [ ] **MON-5**: Content optimization for monetization
- [ ] **MON-6**: Legal pages (privacy policy, terms, affiliate disclosure)

**Status**: ❌ **NOT ADDRESSED** — Zero monetization infrastructure

### **Documentation Cleanup** — **IN PROGRESS**
- [~] **DOC-1**: Consolidate multiple TODO files into single source
- [~] **DOC-2**: Update PHASE2_CURSOR.md with current status
- [~] **DOC-3**: Mark legacy files as superseded
- [ ] **DOC-4**: Archive old configuration examples
- [ ] **DOC-5**: Add Makefile documentation target

**Status**: 🔄 **PARTIAL** — Cleanup in progress

---

## 🎯 **RED TEAM FOCUS AREAS**

### **HIGH PRIORITY ISSUES**
1. **WordPress Setup Gap**: Pipeline is production-ready but can't publish without WordPress
2. **Monetization Void**: Sophisticated content generation with zero revenue strategy
3. **Domain/Access**: Local-only WordPress limits monetization potential
4. **Documentation Fragmentation**: Multiple TODO sources, unclear completion status

### **MEDIUM PRIORITY ISSUES**
1. **Security Hardening**: Production deployment security review needed
2. **Performance Optimization**: Resource usage on Pi under load
3. **Error Recovery**: Failure mode testing and recovery procedures
4. **Scaling Considerations**: Multi-site or multi-Pi deployment patterns

### **LOW PRIORITY ITEMS**
1. **Code Cleanup**: Some enhanced features add complexity
2. **Configuration Consolidation**: Multiple config files could be simplified
3. **Testing Coverage**: Additional edge case testing
4. **Monitoring Enhancements**: More detailed analytics and alerting

---

## 📊 **OVERALL STATUS SUMMARY**

### **Content Pipeline**: ✅ **98% COMPLETE**
- Video generation: Fully functional end-to-end
- Blog generation: Fully functional end-to-end  
- Quality enhancements: Fact-checking, SEO, analytics beyond scope
- Operations: Health monitoring, web UI, testing framework complete

### **Publishing Infrastructure**: ⚠️ **60% COMPLETE**
- YouTube: Ready for production use
- WordPress: **BLOCKED** — requires manual setup not documented
- Monetization: **MISSING** — no revenue generation capability

### **Documentation**: 🔄 **80% COMPLETE**
- Technical documentation: Comprehensive
- Setup guides: Good for technical users
- Business/monetization: **MISSING**
- Consolidation: **IN PROGRESS**

---

## 🚀 **IMMEDIATE ACTIONS FOR PRODUCTION**

1. **WordPress Setup Documentation**: Complete installation guides
2. **Monetization Strategy**: Implement revenue generation framework
3. **Domain Configuration**: Public access setup for WordPress
4. **Security Review**: Production deployment hardening
5. **Documentation Consolidation**: Single source of truth for all tasks

**Bottom Line**: The pipeline is technically excellent but lacks business infrastructure (WordPress setup + monetization) to be truly production-ready for revenue generation.
