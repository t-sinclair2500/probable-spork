# One-Pi Content Automation Pipeline

Single Raspberry Pi 5 (64-bit) pipeline that discovers topics, generates scripts with a local LLM (Ollama), performs TTS, fetches royalty-free assets, assembles videos (MoviePy + FFmpeg), and stages for upload. Includes local ASR via `whisper.cpp` and dual-lane content production (YouTube + WordPress blog). Features real-time monitoring, asset quality assessment, fact-checking, and enhanced SEO optimization. Optional cloud fallbacks for TTS/ASR are wired but OFF by default.

## Quick Start

1) **Install system deps**
```bash
sudo apt update && sudo apt install -y python3-full python3-venv python3-pip ffmpeg git jq sqlite3 rclone build-essential cmake
```

2) **Create venv and install Python deps**
```bash
cd ~/youtube_onepi_pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

3) **Install & run Ollama (LLM)**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull phi3:mini
# (Optional) ollama pull llama3.2:3b-instruct
```

4) **Build whisper.cpp (optional for captions)**
```bash
git clone https://github.com/ggerganov/whisper.cpp.git ~/whisper.cpp
cd ~/whisper.cpp && cmake -B build && cmake --build build -j --config Release
bash models/download-ggml-model.sh base.en
```

5) **Copy config and set values**
```bash
cp conf/global.example.yaml conf/global.yaml
cp .env.example .env
# Edit conf/global.yaml to set niches, tone, video length, etc.
# Edit .env (from .env.example) for API keys (assets providers, ingestion, optional fallbacks).
# Note: Paths auto-detect based on your environment (Mac dev vs Pi production)
```

**Environment Setup Note**: `.env` files are excluded from version control for security. The comprehensive `.env.example` file documents all available environment variables with examples and setup instructions. Copy it to `.env` and configure your actual API keys and credentials.

6) **Seed cron (optional)**
See `crontab.seed.txt`. Apply with:
```bash
crontab crontab.seed.txt
```

7) **Run a full cycle manually (first time)**
```bash
source .venv/bin/activate
python bin/niche_trends.py
python bin/llm_cluster.py
python bin/llm_outline.py
python bin/llm_script.py
python bin/fetch_assets.py
python bin/tts_generate.py
python bin/assemble_video.py
python bin/upload_stage.py
```

## Storage Notes

- Use a USB SSD (recommended). Update paths in `conf/global.yaml` if needed.
- This repo uses a single-lane, lock-aware flow to avoid overloading the Pi.

## Safety & Licensing

- Asset fetcher records license info per asset directory. You must respect each source’s license terms.
- Cloud services are optional and OFF by default; enabling them may incur costs.

## Enhanced Features

### 🎯 Asset Quality Assessment
- **Intelligent Asset Selection**: Quality-based ranking with resolution, compression, and relevance scoring
- **Provider Performance Tracking**: Analytics on asset provider quality and success rates
- **Semantic Matching**: Keyword expansion and relevance scoring against B-roll queries
- **Quality Metrics**: Comprehensive analysis including brightness, contrast, sharpness for images; duration, bitrate for videos

### 📊 Real-Time Analytics Dashboard
- **Live Monitoring**: WebSocket-based real-time updates with graceful fallback to polling
- **Performance Metrics**: CPU, memory, disk usage with 24-hour trending charts
- **Pipeline Analytics**: Success rates, error tracking, and bottleneck identification per step
- **Alert System**: Configurable thresholds with severity-based notifications
- **Asset Analytics**: Provider performance, quality trends, and usage optimization

### 🔍 Fact-Checking Integration
- **Automated Validation**: LLM-powered fact-checking with configurable severity levels
- **Content Gating**: Optional blocking/warning modes for content with fact-check issues
- **Citation Suggestions**: Automated recommendations for claims requiring sources
- **Quality Metrics**: Integrated scoring in blog validation pipeline

### 🚀 Enhanced SEO & Metadata
- **Comprehensive Meta Tags**: Auto-generated Open Graph, Twitter Cards, and schema.org markup
- **Smart Descriptions**: Automated meta description generation from content
- **Reading Time**: Calculation and display of estimated reading time
- **Keyword Extraction**: Automated keyword analysis with stop-word filtering
- **Featured Images**: Intelligent image selection from assets with proper alt text
- **Breadcrumbs**: Automatic navigation structure generation

### 🌐 Web Interface
- **Real-Time Dashboard**: Live pipeline monitoring at `http://localhost:8099`
- **Analytics View**: Advanced metrics and performance analysis at `http://localhost:8099/analytics`
- **WebSocket Support**: Instant updates without page refresh, automatic fallback to polling
- **Multi-Client Support**: Connection management for multiple simultaneous users

### 📈 Quality & Performance
- **Asset Deduplication**: SHA1-based duplicate detection with quality-based selection
- **Content Validation**: Multi-layered validation including structure, readability, and fact-checking
- **Provider Reliability**: Automated tracking and optimization recommendations
- **Real-Time Monitoring**: Background file watching with intelligent change detection

## Monetization Strategy

⚠️ **Important**: This pipeline generates high-quality content but **does not include monetization mechanisms**. See `MONETIZATION_STRATEGY.md` for:
- YouTube Partner Program setup
- WordPress advertising integration  
- Affiliate marketing automation
- Revenue tracking and optimization
- Domain setup for public WordPress access

## 📋 Red Team Review

**🔍 For Red Team**: See `RED_TEAM_BRIEFING.md` for investigation focus areas and `PRODUCTION_READINESS_CHECKLIST.md` for complete task status.

**Key Issues Identified**:
- WordPress setup gap (technical integration complete, deployment missing)
- Monetization void (no revenue generation strategy)
- Documentation fragmentation (now consolidated)

## Support

This scaffold includes production-ready enhancements for content quality, SEO optimization, and real-time monitoring. See consolidated documentation for current project status.


---

## Blog Lane (Shared Repo)

This repo also includes a **blog lane** that reuses shared artifacts (topics, scripts, assets) to publish posts to WordPress via REST.

### Prerequisites: WordPress Setup Required

**⚠️ You need a WordPress site before using the blog pipeline.** Options:

1. **Cloud hosting** (Easiest): Bluehost, SiteGround, WP Engine (~$3-20/month)
2. **Local Pi installation**: Full LAMP stack setup (see OPERATOR_RUNBOOK.md)
3. **Docker on Pi**: Containerized WordPress (see OPERATOR_RUNBOOK.md)
4. **WordPress.com**: Limited API access on free plans

### Setup
1) **Set up WordPress** using one of the options above
2) Copy the blog config:
```bash
cp conf/blog.example.yaml conf/blog.yaml
```
3) Edit `conf/blog.yaml` with your WordPress URL and credentials
4) Create a **non-admin** poster user in WordPress with an **Application Password**

### Manual run (first time)
```bash
source .venv/bin/activate
python bin/blog_pick_topics.py
python bin/blog_generate_post.py  # Includes fact-checking and quality validation
python bin/blog_render_html.py    # Enhanced with SEO metadata and schema.org
python bin/blog_post_wp.py
python bin/blog_ping_search.py
```

### Enhanced Blog Features
- **Fact-Checking**: Automated validation with configurable gating modes (off/warn/block)
- **SEO Optimization**: Comprehensive meta tags, Open Graph, Twitter Cards, and schema.org markup
- **Content Analysis**: Reading time calculation, keyword extraction, and quality scoring
- **Asset Integration**: Intelligent featured image selection from quality-assessed assets
- **Structured Data**: Enhanced breadcrumbs and article markup for better search visibility

## Publishing Control

All publishing operations use **centralized flag governance** with clear precedence:

1. **CLI flags** (highest): `--dry-run` forces dry-run mode
2. **Environment variables**: `BLOG_DRY_RUN`, `YOUTUBE_UPLOAD_DRY_RUN` 
3. **Config files**: `wordpress.publish_enabled` in `conf/blog.yaml`
4. **Safe defaults** (lowest): dry-run enabled, publishing disabled

**Quick toggles:**
- Blog: Set `wordpress.publish_enabled: true` in `conf/blog.yaml` + `BLOG_DRY_RUN=false` in `.env`
- YouTube: Set `YOUTUBE_UPLOAD_DRY_RUN=false` in `.env`
- Global dry-run: Use `--dry-run` flag with any script or orchestrator

> **Security**: Defaults are safe (dry-run enabled). Production requires explicit configuration.


## Cron (Unified Seed)

A unified crontab is provided in `crontab.seed.txt` that schedules shared ingestion, the YouTube lane, the Blog lane, and health checks. Apply it with:

```bash
crontab crontab.seed.txt
```

Each script is lock-aware and exits if another heavy step is in progress.


## Makefile commands
- `make install` — create venv and install deps
- `make check` — validate config and env
- `make run-once` — full YouTube lane once (placeholders where noted)
- `make blog-once` — full Blog lane once (dry-run by default)
- `make cron-install` — install unified cron
- `make backup` — dump WP DB & repo artifacts
- `make health` — start local health server

## Health server
## Configuration reference

- `.env` (copy from `.env.example`)
  - PIXABAY_API_KEY, PEXELS_API_KEY (assets)
  - Optional: UNSPLASH_ACCESS_KEY (only if enabled later)
  - Optional ingestion: YOUTUBE_API_KEY or GOOGLE_API_KEY; REDDIT_CLIENT_ID/SECRET/USER_AGENT
  - Optional fallbacks: OPENAI_API_KEY
  - BLOG_DRY_RUN=true|false (controlled by centralized flags)
  - YOUTUBE_UPLOAD_DRY_RUN=true|false (controlled by centralized flags)

- `conf/global.yaml`
  - `limits.max_retries` controls API backoff retries for providers.
  - `assets.providers` currently supports `pixabay`, `pexels`.
  - To add Unsplash, enable in config and add key to `.env` (code support TBD).

- `conf/sources.yaml` has been archived; use `.env` for keys.
After running `scripts/install_systemd_and_logrotate.sh`, visit:
```
http://<pi-lan-ip>:8088/health
```
