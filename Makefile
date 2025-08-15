# Cross-platform Makefile for Probable Spork
# Supports both Windows and Unix-like systems

# OS detection
ifeq ($(OS),Windows_NT)
    # Windows
    SHELL := cmd
    PY := .venv\Scripts\python.exe
    VENV := .venv
    RM := rmdir /s /q
    MKDIR := mkdir
    RMDIR := rmdir /s /q
    CP := copy
    PYTHON := python
    VENV_CMD := python -m venv
    ACTIVATE := .venv\Scripts\activate
else
    # Unix-like (macOS, Linux)
    SHELL := /bin/bash
    PY := .venv/bin/python
    VENV := .venv
    RM := rm -rf
    MKDIR := mkdir -p
    RMDIR := rm -rf
    CP := cp
    PYTHON := python3
    VENV_CMD := python3 -m venv
    ACTIVATE := source .venv/bin/activate
endif

# Default target
.DEFAULT_GOAL := help

.PHONY: help setup start check clean test install-deps

help: ## Show this help message
	@echo "Probable Spork - Cross-Platform Development"
	@echo "=========================================="
	@echo ""
	@echo "Available targets:"
ifeq ($(OS),Windows_NT)
	@echo "  setup         # Create virtual environment and install dependencies"
	@echo "  start         # Start the development environment"
	@echo "  check         # Validate environment and configuration"
	@echo "  clean         # Remove virtual environment and caches"
	@echo "  test          # Run test suite"
	@echo "  format        # Format Python code with Black and isort"
	@echo "  lint          # Lint Python code"
	@echo "  format-check  # Check if code needs formatting"
	@echo "  optimize      # Optimize for current hardware"
	@echo "  serve-api     # Start FastAPI server"
	@echo "  serve-ui      # Start Gradio UI"
	@echo "  smoke-test    # Run API smoke tests"
	@echo "  backup-repo   # Create repository backup"
	@echo "  backup-wp     # Create WordPress backup"
	@echo "  research-live # Run research collection in live mode (requires SLUG=)"
	@echo "  research-reuse # Run research collection in reuse mode (requires SLUG=)"
	@echo "  fact-guard    # Run fact-guard analysis (requires SLUG=)"
else
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
endif
	@echo ""
	@echo "Quick start:"
	@echo "  make setup    # Create virtual environment and install dependencies"
	@echo "  make start    # Start the development environment"
	@echo "  make check    # Validate environment and configuration"
	@echo ""
	@echo "Research commands (require SLUG parameter):"
	@echo "  make research-live SLUG=eames-history    # Collect research in live mode"
	@echo "  make research-reuse SLUG=eames-history   # Use cached research only"
	@echo "  make fact-guard SLUG=eames-history       # Run fact-guard analysis"

setup: ## Create virtual environment and install dependencies
	@echo "Setting up development environment..."
	@if not exist $(VENV) ( \
		echo "Creating virtual environment..." && \
		$(VENV_CMD) $(VENV) \
	) else ( \
		echo "Virtual environment already exists" \
	)
	@echo "Installing Python dependencies..."
	@$(PY) -m pip install --upgrade pip
	@if exist requirements-basic.txt ( \
		echo "Installing basic requirements..." && \
		$(PY) -m pip install -r requirements-basic.txt \
	) else if exist requirements.txt ( \
		echo "Installing full requirements..." && \
		$(PY) -m pip install -r requirements.txt \
	) else ( \
		echo "No requirements file found" \
	)
	@echo "✅ Setup complete! Run 'make start' to begin development."

start: ## Start the development environment
	@echo "Starting development environment..."
	@$(PY) scripts/bootstrap.py
	@$(PY) scripts/start.py

check: ## Validate environment and configuration
	@echo "Checking development environment..."
	@if exist $(PY) ( \
		echo "✅ Virtual environment found" && \
		$(PY) --version && \
		$(PY) -c "import sys; print(f'Python path: {sys.executable}')" \
	) else ( \
		echo "❌ Virtual environment not found. Run 'make setup' first." && \
		exit 1 \
	)
	@if exist requirements.txt ( \
		echo "✅ Requirements file found" \
	) else ( \
		echo "⚠️  No requirements.txt found" \
	)
	@if exist .env ( \
		echo "✅ Environment file found" \
	) else if exist .env.example ( \
		echo "⚠️  .env file missing. Copy .env.example to .env and configure." \
	) else ( \
		echo "⚠️  No .env or .env.example found" \
	)
	@echo "✅ Environment check complete"

format: ## Format Python code with Black and isort
	@echo "🎨 Formatting Python code..."
	@$(PY) -m pip install --quiet black isort
	@$(PY) -m isort .
	@$(PY) -m black .
	@echo "✅ Code formatting complete"

lint: ## Lint Python code
	@echo "🔍 Linting Python code..."
	@$(PY) -m pip install --quiet flake8
	@$(PY) -m flake8 --max-line-length=88 --extend-ignore=E203,W503 .
	@echo "✅ Code linting complete"

format-check: ## Check if code needs formatting
	@echo "🔍 Checking code formatting..."
	@$(PY) -m pip install --quiet black isort
	@$(PY) -m isort --check-only .
	@$(PY) -m black --check .
	@echo "✅ Code formatting is correct"

optimize: ## Optimize configuration for current hardware
	@echo "🚀 Optimizing configuration for your hardware..."
	@$(PY) scripts/optimize_hardware.py

clean: ## Remove virtual environment and caches
	@echo "Cleaning up development environment..."
	@if exist $(VENV) ( \
		echo "Removing virtual environment..." && \
		$(RMDIR) $(VENV) \
	) else ( \
		echo "No virtual environment to remove" \
	)
	@if exist __pycache__ ( \
		echo "Removing Python cache..." && \
		$(RMDIR) __pycache__ \
	)
	@if exist .pytest_cache ( \
		echo "Removing pytest cache..." && \
		$(RMDIR) .pytest_cache \
	)
	@if exist .mypy_cache ( \
		echo "Removing mypy cache..." && \
		$(RMDIR) .mypy_cache \
	)
	@echo "✅ Cleanup complete"

test: ## Run tests
	@echo "Running tests..."
	@$(PY) -m pytest tests/ -v

install-deps: ## Install additional dependencies (alias for setup)
	@$(MAKE) setup

# Research commands
research-live: ## Run research collection in live mode (requires SLUG=)
	@if not defined SLUG ( \
		echo "❌ SLUG parameter required. Usage: make research-live SLUG=eames-history" && \
		exit 1 \
	)
	@echo "🔍 Running research collection in LIVE mode for slug: $(SLUG)"
	@$(PY) bin/research_collect.py --slug $(SLUG) --mode live

research-reuse: ## Run research collection in reuse mode (requires SLUG=)
	@if not defined SLUG ( \
		echo "❌ SLUG parameter required. Usage: make research-reuse SLUG=eames-history" && \
		exit 1 \
	)
	@echo "🔍 Running research collection in REUSE mode for slug: $(SLUG)"
	@$(PY) bin/research_collect.py --slug $(SLUG) --mode reuse

fact-guard: ## Run fact-guard analysis (requires SLUG=)
	@if not defined SLUG ( \
		echo "❌ SLUG parameter required. Usage: make fact-guard SLUG=eames-history" && \
		exit 1 \
	)
	@echo "🛡️ Running fact-guard analysis for slug: $(SLUG)"
	@$(PY) bin/fact_guard.py --slug $(SLUG) --strictness balanced

# Legacy targets for backward compatibility
run-once: ## Run full pipeline once (legacy)
	@echo "Running full pipeline..."
	@$(PY) bin/niche_trends.py
	@$(PY) bin/llm_cluster.py
	@$(PY) bin/llm_outline.py
	@$(PY) bin/llm_script.py
	@$(PY) bin/fetch_assets.py
	@$(PY) bin/tts_generate.py
	@$(PY) bin/assemble_video.py
	@$(PY) bin/upload_stage.py

# Cross-platform script execution (Python-based)
serve-api: ## Start FastAPI server
	@echo "Starting FastAPI server..."
	@$(PY) scripts/serve_api.py

serve-ui: ## Start Gradio UI
	@echo "Starting Gradio UI..."
	@$(PY) scripts/serve_ui.py

smoke-test: ## Run smoke test
	@echo "Running smoke test..."
	@$(PY) scripts/smoke_op_console.py

# Operator Console targets
op-console-api: ## Start operator console API server
	@echo "Starting operator console API server..."
	@$(PY) scripts/serve_api.py

op-console-ui: ## Start operator console UI
	@echo "Starting operator console UI..."
	@$(PY) scripts/serve_ui.py

op-console: ## Start both API and UI for operator console
	@echo "Starting operator console (API + UI)..."
	@echo "Starting API server in background..."
	@$(PY) scripts/serve_api.py &
	@echo "Waiting for API to start..."
	@sleep 3
	@echo "Starting UI..."
	@$(PY) scripts/serve_ui.py

op-console-smoke: ## Run operator console smoke test
	@echo "Running operator console smoke test..."
	@$(PY) scripts/smoke_op_console.py

# Backup operations
backup-repo: ## Create repository backup
	@echo "Creating repository backup..."
	@$(PY) scripts/backup_repo.py

backup-wp: ## Create WordPress backup
	@echo "Creating WordPress backup..."
	@$(PY) scripts/backup_wp.py

# Legacy shell script support (for backward compatibility)
ifeq ($(OS),Windows_NT)
serve-api-shell: ## Start FastAPI server (PowerShell)
	@echo "Starting FastAPI server (PowerShell)..."
	@powershell -ExecutionPolicy Bypass -File scripts/serve_api.ps1

serve-ui-shell: ## Start Gradio UI (PowerShell)
	@echo "Starting Gradio UI (PowerShell)..."
	@powershell -ExecutionPolicy Bypass -File scripts/serve_ui.ps1

smoke-test-shell: ## Run smoke test (PowerShell)
	@echo "Running smoke test (PowerShell)..."
	@powershell -ExecutionPolicy Bypass -File scripts/smoke_op_console.ps1
else
serve-api-shell: ## Start FastAPI server (Bash)
	@echo "Starting FastAPI server (Bash)..."
	@bash scripts/serve_api.sh

serve-ui-shell: ## Start Gradio UI (Bash)
	@echo "Starting Gradio UI (Bash)..."
	@bash scripts/serve_ui.sh

smoke-test-shell: ## Run smoke test (Bash)
	@echo "Running smoke test (Bash)..."
	@bash scripts/smoke_op_console.sh
endif

blog-once: ## Run blog pipeline once (legacy)
	@echo "Running blog pipeline..."
	@$(PY) bin/blog_pick_topics.py
	@$(PY) bin/blog_generate_post.py
	@$(PY) bin/blog_render_html.py
	@$(PY) bin/blog_post_wp.py
	@$(PY) bin/blog_ping_search.py

health: ## Start health server (legacy)
	@echo "Starting health server..."
	@$(PY) bin/health_server.py

web-ui: ## Start web UI (legacy)
	@echo "Starting web UI..."
	@$(PY) bin/web_ui.py
