# Development Setup - Probable Spork

This document describes the cross-platform development setup for macOS and Windows.

## Quick Start

### 1. Setup Environment
```bash
# Create virtual environment and install dependencies
make setup
```

### 2. Start Development
```bash
# Start the development environment
make start
```

That's it! The system will automatically detect your project type and start the appropriate services.

## Available Commands

### Core Development
- `make setup` - Create virtual environment and install dependencies
- `make start` - Start the development environment
- `make check` - Validate environment and configuration
- `make clean` - Remove virtual environment and caches
- `make test` - Run test suite

### Service Management
- `make serve-api` - Start FastAPI server only (Python-based)
- `make serve-ui` - Start Gradio UI only (Python-based)
- `make smoke-test` - Run API smoke tests (Python-based)
- `make backup-repo` - Create repository backup
- `make backup-wp` - Create WordPress backup

### Legacy Pipeline (Still Available)
- `make run-once` - Run full YouTube pipeline
- `make blog-once` - Run blog pipeline
- `make health` - Start health server

## What Happens When You Run `make start`

1. **Bootstrap** (`scripts/bootstrap.py`):
   - Validates Python version compatibility
   - Checks for `.env` configuration
   - Creates required local directories
   - Validates virtual environment

2. **Start** (`scripts/start.py`):
   - Detects project type automatically
   - Starts appropriate services:
     - **FastAPI + Gradio** (current setup): FastAPI on port 8008, Gradio on port 7860
     - **Streamlit**: Streamlit development server
     - **Node.js**: npm/yarn/pnpm dev server
     - **Python app**: Direct execution

## Project Structure

```
probable-spork/
├── .venv/                    # Virtual environment (created by make setup)
├── scripts/
│   ├── bootstrap.py         # Environment validation and setup
│   ├── start.py             # Service detection and startup
│   ├── serve_api.py         # FastAPI server starter (cross-platform)
│   ├── serve_ui.py          # Gradio UI starter (cross-platform)
│   ├── smoke_op_console.py  # API smoke testing (cross-platform)
│   ├── backup_repo.py       # Repository backup (cross-platform)
│   ├── backup_wp.py         # WordPress backup (cross-platform)
│   ├── serve_api.sh         # Legacy Unix FastAPI starter
│   ├── serve_api.ps1        # Legacy Windows FastAPI starter
│   ├── serve_ui.sh          # Legacy Unix Gradio starter
│   ├── serve_ui.ps1         # Legacy Windows Gradio starter
│   ├── smoke_op_console.sh  # Legacy Unix smoke test
│   └── smoke_op_console.ps1 # Legacy Windows smoke test
├── fastapi_app/              # FastAPI application
├── ui/                       # Gradio interface
├── bin/                      # Pipeline scripts
├── conf/                     # Configuration files
├── Makefile                  # Cross-platform build system
├── .gitattributes           # Line ending normalization
├── .editorconfig            # Editor configuration
└── .vscode/tasks.json       # VS Code integration
```

## Cross-Platform Support

### Windows
- Uses Python scripts (`.py`) for service management (primary)
- PowerShell scripts (`.ps1`) available for legacy support
- Virtual environment: `.venv\Scripts\python.exe`
- Line endings: CRLF for PowerShell, LF for everything else

### macOS/Linux
- Uses Python scripts (`.py`) for service management (primary)
- Bash scripts (`.sh`) available for legacy support
- Virtual environment: `.venv/bin/python`
- Line endings: LF for all files

### Automatic Detection
The Makefile automatically detects your OS and uses appropriate commands:
```makefile
ifeq ($(OS),Windows_NT)
    # Windows commands
    PY := .venv\Scripts\python.exe
else
    # Unix commands
    PY := .venv/bin/python
endif
```

## Environment Configuration

### Required Files
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (copy from `.env.example`)

### Environment Variables
```bash
# API Keys (required)
PIXABAY_API_KEY=your_key_here
PEXELS_API_KEY=your_key_here

# Pipeline Control (optional)
BLOG_DRY_RUN=true
YOUTUBE_UPLOAD_DRY_RUN=true

# Server Configuration (optional)
PORT=8008
HOST=127.0.0.1
```

## Troubleshooting

### Virtual Environment Issues
```bash
# Clean and recreate
make clean
make setup
```

### Permission Issues (Windows)
```bash
# Run PowerShell as Administrator and set execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Port Conflicts
```bash
# Check what's using the ports
netstat -ano | findstr :8008  # Windows
lsof -i :8008                  # macOS/Linux
```

### Python Version Issues
This project requires Python 3.9, 3.10, or 3.11. Python 3.12+ is not supported due to MoviePy compatibility.

## VS Code Integration

The `.vscode/tasks.json` file provides VS Code tasks for common operations:
- **Make: setup** - Create environment
- **Make: start** - Start development
- **Make: check** - Validate setup
- **Python: Bootstrap** - Run bootstrap directly
- **Python: Start** - Run start script directly
- **Python: Serve API** - Start FastAPI server directly
- **Python: Serve UI** - Start Gradio UI directly
- **Python: Smoke Test** - Run API smoke tests directly
- **Python: Backup Repo** - Create repository backup directly
- **Python: Backup WordPress** - Create WordPress backup directly

## Next Steps

1. **Configure API Keys**: Copy `.env.example` to `.env` and add your keys
2. **Customize Configuration**: Edit `conf/global.yaml` for pipeline settings
3. **Run Tests**: Use `make test` to validate your setup
4. **Start Development**: Use `make start` to begin development

## Support

For issues specific to the development setup:
1. Check the troubleshooting section above
2. Run `make check` to validate your environment
3. Check the logs in the `logs/` directory
4. Review the main README.md for project-specific information
