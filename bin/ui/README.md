# Probable Spork Operator Console

A clean, deterministic Gradio UI for the full pipeline that exposes the flags & knobs we actually tweak on each run.

## Features

- **Single-screen operator console** with all controls visible
- **Real-time log streaming** from pipeline execution
- **Deterministic runs** with seed control for reproducible outputs
- **Health checks** for ffmpeg, ffprobe, and macOS VideoToolbox
- **Artifact discovery** - thumbnails, shorts, QA reports, metadata
- **Brief editor** with YAML syntax highlighting and save functionality
- **No hidden magic** - UI only composes CLI args and calls existing pipeline

## Usage

### Start the UI
```bash
# Activate virtual environment
source .venv/bin/activate

# Launch UI (default port 7860)
python bin/ui/app.py

# Or specify port
python bin/ui/app.py --port 7861

# Or expose on LAN (use with caution)
python bin/ui/app.py --share
```

### Typical Workflow
1. **Pick or enter Slug** - Use dropdown for existing or type new slug
2. **Optional Brief** - Paste/edit YAML brief → Save Brief
3. **Configure Run** - Choose Mode, toggles (Viral/Shorts/SEO), Seed, From-step
4. **Run Pipeline** - Click "Run Full Pipeline" → watch Live Logs stream
5. **View Results** - Click "Refresh Artifacts" → load thumbs/shorts/QA

### Controls

**Inputs:**
- **Slug** - Identifier for the content piece
- **Brief YAML** - Optional workstream configuration
- **Mode** - `reuse` (default) or `live`
- **YouTube Only** - Skip ingestion, run assembly/publish only
- **Viral Lab** - Enable viral optimization steps
- **Shorts** - Enable shorts generation
- **SEO Packaging** - Enable SEO optimization
- **Seed** - For deterministic viral selection (default: 1337)
- **From Step** - Resume from specific pipeline step

**Actions:**
- **Run Full Pipeline** - Execute complete pipeline with current settings
- **Run QA Only** - Execute quality gates for current slug
- **Ensure Models** - Check/pull required Ollama models
- **Refresh Slugs** - Update dropdown with latest content
- **Refresh Artifacts** - Load latest outputs for current slug

**Observability:**
- **Live Logs** - Real-time stdout/stderr from pipeline
- **Health Panel** - System tool availability (ffmpeg, ffprobe, VideoToolbox)
- **QA Summary** - PASS/WARN/FAIL status per gate
- **Thumbnails Gallery** - Generated thumbnail images
- **Shorts Files** - Generated short-form videos
- **Download Links** - metadata.json and qa_report.json

## Configuration

Default settings in `conf/ui.yaml`:
```yaml
server:
  port: 7860
  share: false
defaults:
  mode: "reuse"
  yt_only: false
  enable_viral: true
  enable_shorts: true
  enable_seo: true
  seed: 1337
  from_step: ""
paths:
  briefs_dir: "conf/briefs"
ui:
  max_log_lines: 2000
```

## Architecture

- **`bin/ui/app.py`** - Main Gradio Blocks application
- **`bin/ui/run_helpers.py`** - Process streaming, discovery, health checks
- **`bin/ui/components.py`** - UI component utilities (QA formatting)
- **`bin/ui/state.py`** - Session state management
- **`conf/ui.yaml`** - UI configuration defaults
- **`tests/test_ui_helpers.py`** - Unit tests for helpers

## Determinism

The UI exposes the **Seed** parameter which controls:
- Viral hook selection consistency
- Title generation reproducibility
- Output consistency across runs

Setting the same seed yields identical viral selections and consistent outputs.

## Health Checks

The UI automatically detects:
- **ffmpeg** - Video processing capability
- **ffprobe** - Media analysis capability  
- **VideoToolbox** - macOS hardware acceleration

Missing tools show warnings but don't block operation (fallbacks are used).

## Error Handling

- **Missing assets** - UI creates placeholders and emits warnings
- **QA gates** - Catch quality issues and report status
- **Graceful degradation** - Pipeline continues with available tools
- **No crashes** - UI handles missing configs/assets gracefully



