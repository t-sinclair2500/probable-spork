# Probable Spork - ChatGPT-Friendly Export

This is a clean export of the Probable Spork codebase, designed to be ChatGPT-friendly by including all key source files while excluding large artifacts, caches, and model data.

## What's Included

### Core Application Code
- **`bin/`** - All Python scripts and modules
- **`conf/`** - Configuration files (YAML, JSON)
- **`schema/`** - Data schemas and validation
- **`tests/`** - Test suite and test data
- **`docs/`** - Documentation and architecture guides

### Key Features
- **Storyboard Asset Loop** - Procedural asset generation system
- **Texture Engine** - Paper feel and texture overlays
- **SVG Path Operations** - Procedural SVG generation
- **Music Bed Policy** - Intelligent music selection and ducking
- **Pipeline Orchestration** - Centralized execution management

### Configuration
- **`conf/pipeline.yaml`** - Central pipeline configuration
- **`conf/global.yaml`** - Global application settings
- **`conf/modules.yaml`** - Module-specific configurations
- **`conf/models.yaml`** - AI model configurations

### Design Assets
- **`assets/brand/`** - Brand style guides and assets
- **`assets/design/`** - Design system and templates
- **`assets/generated/`** - Procedurally generated assets

### Content Examples
- **`scenescripts/`** - SceneScript examples and templates
- **`scripts/`** - Generated content scripts
- **`prompts/`** - AI prompt templates
- **`pipeline_enhancements_prompts/`** - Feature integration prompts

### Documentation
- **`docs/`** - Comprehensive documentation
- **`*.md`** - README and architecture files
- **`ARCHITECTURE.md`** - System architecture overview
- **`INTEGRATION_SUMMARY.md`** - Feature integration summary

## What's Excluded

### Large Files
- Video files (`.mp4`, `.avi`, etc.)
- Audio files (`.mp3`, `.wav`, etc.)
- Large image files (`.png`, `.jpg`, etc.)
- Model files (`.onnx`, `.bin`, etc.)

### Caches and Temporary Files
- `render_cache/`
- `voice_cache/`
- `venv/`
- `.pytest_cache/`
- `__pycache__/`

### Generated Artifacts
- Large video outputs
- Temporary render files
- Log files
- Database files

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

3. **Run Integration Tests**
   ```bash
   python bin/test_integration_full_pipeline.py
   ```

4. **Run E2E Tests**
   ```bash
   python bin/test_e2e.py
   ```

## Key Components

### Pipeline Orchestrator
- **`bin/run_pipeline.py`** - Main pipeline orchestrator
- **`conf/pipeline.yaml`** - Execution order and dependencies
- **Feature integration** - All new features centrally configured

### Asset Generation
- **`bin/cutout/asset_loop.py`** - Storyboard asset loop
- **`bin/cutout/texture_engine.py`** - Texture and paper feel
- **`bin/cutout/svg_path_ops.py`** - SVG path operations
- **`bin/cutout/motif_generators.py`** - Procedural asset generation

### Content Generation
- **`bin/storyboard_plan.py`** - SceneScript generation
- **`bin/animatics_generate.py`** - Procedural animatics
- **`bin/assemble_video.py`** - Video assembly with music
- **`bin/llm_*.py`** - AI-powered content generation

## Architecture

The system follows a **single-lane, lock-aware** architecture designed for Raspberry Pi 5:

- **Sequential execution** - Heavy tasks run one at a time
- **Asset reuse** - Generated assets are cached and reused
- **Procedural generation** - Missing assets created on-demand
- **Quality gates** - Validation at each pipeline stage

## Configuration

### Pipeline Modes
- **Animatics-Only** (default) - Procedural asset generation
- **Legacy Stock** (fallback) - Traditional stock asset downloads

### Feature Flags
- **Asset Loop**: `enabled: true`
- **Textures**: `enabled: true`
- **SVG Ops**: `enabled: true`
- **Music Bed**: `enabled: true`

## Testing

### Integration Tests
```bash
python bin/test_integration_full_pipeline.py
```

### E2E Tests
```bash
python bin/test_e2e.py
```

### Asset Loop Tests
```bash
python bin/test_asset_loop.py
```

## Dependencies

### Core Requirements
- Python 3.9+
- FFmpeg
- MoviePy
- Pydantic
- PyYAML

### AI Models
- Ollama (local LLM)
- Whisper.cpp (speech recognition)
- Coqui TTS (text-to-speech)

### External APIs
- Pixabay (stock assets)
- Pexels (stock assets)
- YouTube Data API
- Reddit API

## License

This project includes various licenses for different components. See individual files for specific license terms.

## Support

For questions about this export or the codebase, refer to the documentation in the `docs/` directory or the main README files.
