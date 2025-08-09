# Red Team File Inventory — One-Pi Content Pipeline

## 📖 **Documentation Quick Reference**

| Document | Location | Contents | Relevance |
|----------|----------|----------|-----------|
| **RED_TEAM_BRIEFING.md** | Root | Investigation guide, key issues, test plan | **START HERE** - Your main reference |
| **PRODUCTION_READINESS_CHECKLIST.md** | Root | Complete task list from Phase 2, organized by execution order | Task completion status and gaps |
| **MONETIZATION_STRATEGY.md** | Root | Missing business strategy, revenue streams, integration needs | **CRITICAL GAP** - Business model void |
| **OPERATOR_RUNBOOK.md** | Root | Setup procedures, WordPress options, troubleshooting | Deployment reality check |
| **MASTER_TODO.md** | Root | Detailed implementation tracking with acceptance criteria | Technical completion verification |
| **README.md** | Root | Project overview, quick start, enhanced features | Entry point and feature scope |
| ⚠️ **PHASE2_CURSOR.md** | Root | Original task guide (SUPERSEDED) | Historical reference only |
| ⚠️ **TYLER_TODO.md** | Root | API key setup guide (SUPERSEDED) | Historical reference only |

---

## 🤖 **Pipeline Scripts (bin/) - Execution Order**

### **Phase 1: Data Ingestion**
| Script | Purpose | Inputs | Outputs | Dependencies |
|--------|---------|--------|---------|--------------|
| **niche_trends.py** | Fetch trending topics from YouTube/Reddit/Google Trends | API keys (.env) | trending_topics.db | YouTube/Reddit APIs |
| **llm_cluster.py** | Cluster trends into ranked topics using LLM | trending_topics.db | topics_queue.json | Ollama LLM |

### **Phase 2: Content Generation**
| Script | Purpose | Inputs | Outputs | Dependencies |
|--------|---------|--------|---------|--------------|
| **llm_outline.py** | Generate 6-section video outline | topics_queue.json | {slug}.outline.json | Ollama LLM |
| **llm_script.py** | Generate conversational script with B-ROLL markers | {slug}.outline.json | {slug}.txt | Ollama LLM |
| **fact_check.py** | Validate content claims, suggest citations | Script text | Validation results | Ollama LLM |

### **Phase 3: Asset Acquisition**
| Script | Purpose | Inputs | Outputs | Dependencies |
|--------|---------|--------|---------|--------------|
| **fetch_assets.py** | Download royalty-free media based on B-ROLL markers | Script B-ROLL tags | assets/{slug}/ directory | Pixabay/Pexels/Unsplash APIs |
| **asset_quality.py** | Analyze and rank asset quality/relevance | Asset files | Quality metrics | PIL, FFmpeg |

### **Phase 4: Media Production**
| Script | Purpose | Inputs | Outputs | Dependencies |
|--------|---------|--------|---------|--------------|
| **tts_generate.py** | Convert script to speech audio | Script text | voiceovers/{slug}.mp3 | Coqui TTS or OpenAI |
| **generate_captions.py** | Generate SRT captions from audio | Audio file | {slug}.srt | whisper.cpp or OpenAI |
| **assemble_video.py** | Compose final video with assets, audio, captions | All above + assets | videos/{slug}.mp4 | MoviePy, FFmpeg |
| **make_thumbnail.py** | Generate branded video thumbnail | Video metadata | {slug}.png | Pillow |

### **Phase 5: Publishing**
| Script | Purpose | Inputs | Outputs | Dependencies |
|--------|---------|--------|---------|--------------|
| **upload_stage.py** | Stage video for upload with metadata | Video + metadata | upload_queue.json | None |
| **youtube_upload.py** | Upload video to YouTube with OAuth | Staged video | YouTube video ID | Google OAuth |

### **Phase 6: Blog Lane**
| Script | Purpose | Inputs | Outputs | Dependencies |
|--------|---------|--------|---------|--------------|
| **blog_pick_topics.py** | Select topic for blog post | topics_queue.json | blog_topic.json | None |
| **blog_generate_post.py** | Convert script to blog post with validation | Script + topic | post.md + metadata | Ollama LLM |
| **blog_render_html.py** | Convert markdown to SEO-optimized HTML | post.md | post.html | SEO enhancer |
| **seo_lint.py** | Validate SEO compliance | HTML content | SEO metrics | None |
| **blog_post_wp.py** | Publish to WordPress via REST API | HTML + metadata | WordPress post | **WordPress setup** |
| **blog_ping_search.py** | Notify search engines of new content | Posted URL | Ping responses | Live WordPress |

---

## 🔧 **Support & Infrastructure Scripts**

### **Core Infrastructure**
| Script | Purpose | Function | Critical For |
|--------|---------|----------|-------------|
| **core.py** | Core utilities (config, logging, LLM calls, guards) | Foundation for all scripts | Everything |
| **util.py** | Helper functions (slugify, JSON parsing) | Common utilities | Everything |
| **check_env.py** | Validate environment and API keys | Startup verification | Deployment |

### **Enhanced Features (Bonus)**
| Script | Purpose | Function | Added Value |
|--------|---------|----------|------------|
| **analytics_collector.py** | Real-time pipeline metrics collection | Performance monitoring | Operations dashboard |
| **seo_enhancer.py** | Advanced SEO optimization (schema, meta tags) | Blog SEO boost | Content quality |
| **web_ui.py** | Flask dashboard for monitoring and control | Visual interface | Operations |

### **Operations & Monitoring**
| Script | Purpose | Function | Use Case |
|--------|---------|----------|---------|
| **healthcheck.py** | System health monitoring (CPU, disk, services) | Health assessment | Monitoring |
| **health_server.py** | HTTP health endpoint server | External monitoring | Production ops |
| **test_e2e.py** | End-to-end pipeline testing with dependency checks | Validation | Testing |

### **Legacy/Deprecated**
| Script | Purpose | Status | Notes |
|--------|---------|--------|-------|
| **download_assets.py** | Asset downloader | Replaced by fetch_assets.py | Legacy |
| **seo_lint_gate.py** | SEO validation gate | Integrated into blog_generate_post.py | Legacy |

---

## ⚙️ **Configuration Files**

| File | Purpose | Contents | Critical For |
|------|---------|----------|-------------|
| **conf/global.yaml** | Main pipeline configuration | Video settings, LLM config, asset providers | Everything |
| **conf/blog.yaml** | Blog-specific settings | WordPress credentials, content settings | Blog publishing |
| **conf/render.yaml** | Video rendering settings | Resolution, bitrate, effects | Video production |
| **.env.example** | Environment variables template | API keys, secrets, toggles | Security/APIs |

---

## 📝 **Prompt Templates**

| File | Purpose | Used By | Function |
|------|---------|---------|----------|
| **prompts/cluster_topics.txt** | Topic clustering prompt | llm_cluster.py | Trend analysis |
| **prompts/outline.txt** | Video outline generation | llm_outline.py | Content structure |
| **prompts/script_writer.txt** | Script writing prompt | llm_script.py | Content creation |
| **prompts/fact_check.txt** | Fact-checking validation | fact_check.py | Content quality |
| **prompts/beat_timing.txt** | Video timing and pacing | assemble_video.py | Video production |

---

## 🗃️ **Data & State Files**

| Directory/File | Purpose | Contents | Managed By |
|----------------|---------|----------|------------|
| **data/trending_topics.db** | Raw trend data | SQLite with title/source/tags | niche_trends.py |
| **data/topics_queue.json** | Ranked topics | Top 10 topics with scores | llm_cluster.py |
| **data/upload_queue.json** | Upload staging | Video metadata for publishing | upload_stage.py |
| **jobs/state.jsonl** | Pipeline state log | Timestamped step execution | All scripts |
| **scripts/{slug}.*** | Generated content | Outlines, scripts, metadata | Content generation |
| **assets/{slug}/** | Downloaded media | Images, videos, license info | fetch_assets.py |
| **videos/{slug}.mp4** | Final videos | Assembled video content | assemble_video.py |
| **voiceovers/{slug}.mp3** | Generated audio | TTS speech files | tts_generate.py |

---

## 🚨 **Critical Gap Analysis**

### **What Works (✅ Complete)**
- **Content Pipeline**: End-to-end video generation from trends to upload
- **Blog Generation**: Content creation with advanced validation and SEO
- **Quality Controls**: Fact-checking, asset quality, validation metrics
- **Operations**: Monitoring, testing, health checks, deployment automation

### **What's Missing (❌ Gaps)**
- **WordPress Setup**: No installation/deployment guidance despite sophisticated API integration
- **Monetization Infrastructure**: Zero revenue generation mechanisms
- **Public Access**: Local-only WordPress can't generate income
- **Business Documentation**: No guidance on making this profitable

### **Investigation Priority**
1. **High**: WordPress deployment reality - how hard is setup really?
2. **High**: Monetization integration scope - what would revenue tracking require?
3. **Medium**: Enhanced feature necessity - are bonus features essential or scope creep?
4. **Low**: Code optimization - performance and maintainability

---

## 🎯 **Red Team Focus Areas**

### **Technical Verification**
- Test the end-to-end pipeline: `make run-once && make blog-once`
- Verify enhanced features actually work as claimed
- Check for missing dependencies or broken integrations

### **Business Gap Assessment**
- Try to set up WordPress following provided docs
- Evaluate monetization integration complexity
- Assess public deployment requirements

### **Documentation Quality**
- Compare claimed completion vs actual functionality
- Identify missing setup steps or assumptions
- Test deployment procedures on fresh system

**The core question: Is this a production-ready content business or just an impressive technical demo?**
