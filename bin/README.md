# Core Pipeline Executables

This directory contains the main pipeline executables that form the core content automation system.

## 📋 Contents

### Content Generation Pipeline
- **niche_trends.py** - Discovers trending topics and content opportunities
- **llm_cluster.py** - Clusters and prioritizes content topics
- **llm_outline.py** - Generates content outlines using local LLM
- **llm_script.py** - Creates full scripts from outlines
- **fact_check.py** - Validates content accuracy and sources
- **fact_guard.py** - Content safety and fact-checking system

### Asset Management
- **fetch_assets.py** - Downloads royalty-free media assets
- **asset_generator.py** - Generates custom visual assets
- **asset_librarian.py** - Manages asset library and metadata
- **asset_manifest.py** - Creates asset manifests for content
- **asset_quality.py** - Assesses and validates asset quality

### Media Processing
- **tts_generate.py** - Text-to-speech generation
- **generate_captions.py** - Creates captions and subtitles
- **assemble_video.py** - Assembles final video content
- **make_thumbnail.py** - Generates video thumbnails

### Content Management
- **blog_generate_post.py** - Generates blog post content
- **blog_post_wp.py** - WordPress publishing integration
- **blog_ping_search.py** - Search engine notification
- **blog_stage_local.py** - Local blog staging

### System & Utilities
- **core.py** - Core utility functions and configuration
- **llm_client.py** - LLM integration client
- **model_runner.py** - Model execution and management
- **health_server.py** - System health monitoring
- **backup_repo.sh** - Repository backup script

## 🎯 Purpose

These executables provide:
- Core content automation pipeline
- Asset management and processing
- Media generation and assembly
- Content publishing and distribution
- System monitoring and maintenance

## 🔗 Related Documentation

- For pipeline architecture, see [docs/architecture/](../docs/architecture/)
- For implementation details, see [docs/implementation/](../docs/implementation/)
- For operational guidance, see [docs/deployment/](../docs/deployment/)

## 📝 Usage

These are production-ready executables designed for:
- Automated content generation
- Scheduled pipeline execution
- Production deployment
- System administration

**Note**: These scripts are designed to be run in sequence as part of the content pipeline.
