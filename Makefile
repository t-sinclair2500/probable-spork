SHELL := /bin/bash
VENV := venv
PY := $(VENV)/bin/python
export PYTHONPATH := $(CURDIR)

.PHONY: install check docs run-once quick-run blog-once cron-install backup health test pi-deploy pi-run-once pi-blog-once pi-sync pull-artifacts pi-health music-setup music-import music-stats music-validate op-console clean-op-console test-orchestrator

install:
	@echo "Checking Python version..."
	@python3 --version | grep -E "(3\.9|3\.10|3\.11)" > /dev/null || (echo "❌ ERROR: Python 3.9, 3.10, or 3.11 required. Current version:" && python3 --version && echo "Use: python3.11 -m venv .venv" && exit 1)
	@echo "✅ Python version compatible"
	python3 -m venv $(VENV)
	. $(VENV)/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

check:
	$(PY) bin/check_env.py

docs:
	@echo "=========================================="
	@echo "📚 One-Pi Content Pipeline Documentation"
	@echo "=========================================="
	@echo ""
	@echo "🚀 QUICK START & SETUP:"
	@echo "  README.md               - Project overview and installation"
	@echo "  OPERATOR_RUNBOOK.md     - Complete operational guide"
	@echo "  .env.example           - Environment variables setup"
	@echo ""
	@echo "🔧 DEVELOPMENT & TASKS:"
	@echo "  MASTER_TODO.md         - Current development tasks and priorities"
	@echo "  PHASE2_CURSOR.md       - Implementation guide with status"
	@echo "  tests/                 - Test suite and validation"
	@echo ""
	@echo "📋 CONFIGURATION:"
	@echo "  conf/global.yaml       - Master pipeline configuration"
	@echo "  conf/blog.yaml         - Blog-specific settings"
	@echo "  .env                   - API keys and secrets (create from .env.example)"
	@echo ""
	@echo "📊 MONITORING & HEALTH:"
	@echo "  make health            - Start health monitoring server"
	@echo "  make web-ui            - Start real-time web dashboard (port 8099)"
	@echo "  make analytics         - Generate comprehensive analytics report"
	@echo "  jobs/state.jsonl       - Pipeline execution logs"
	@echo "  logs/                  - Detailed application logs"
	@echo ""
	@echo "🧪 TESTING & VALIDATION:"
	@echo "  make test              - Run full test suite"
	@echo "  make test-svg-ops      - Test SVG path operations"
	@echo "  make demo-svg-ops      - Demonstrate SVG path operations"
	@echo "  make check             - Validate environment setup"
	@echo "  make check-llm         - Check Ollama LLM integration"
	@echo "  make quick-run         - Test pipeline with short durations"
	@echo "  make fact-check FILE=  - Fact-check markdown content"
	@echo "  make asset-quality     - Analyze asset quality and relevance"
	@echo ""
	@echo "🎵 MUSIC LIBRARY MANAGEMENT:"
	@echo "  make music-setup       - Setup music library structure"
	@echo "  make music-import      - Import music from directory"
	@echo "  make music-stats       - View library statistics"
	@echo "  make music-validate    - Validate library integrity"
	@echo "  make music-test        - Test music selection system"
	@echo ""
	@echo "🎬 PIPELINE OPERATIONS:"
	@echo "  make run-once          - Full YouTube pipeline execution"
	@echo "  make blog-once         - Full blog pipeline execution"
	@echo "  make backup            - Backup WordPress and repository"
	@echo ""
	@echo "📱 RASPBERRY PI DEPLOYMENT:"
	@echo "  make pi-deploy         - Deploy to Raspberry Pi"
	@echo "  make pi-health         - Check Pi health status"
	@echo "  make pull-artifacts    - Retrieve generated content from Pi"
	@echo ""
	@echo "📚 ADDITIONAL RESOURCES:"
	@echo "  DOC_MAP.md             - Complete documentation index"
	@echo "  docs/archive/          - Historical documentation"
	@echo "  PURPOSE_SUMMARY.md     - Project goals and architecture"
	@echo ""
	@echo "For development tasks and current priorities, see: MASTER_TODO.md"

run-once:
	$(PY) bin/niche_trends.py
	$(PY) bin/llm_cluster.py
	$(PY) bin/llm_outline.py
	$(PY) bin/llm_script.py
	$(PY) bin/fetch_assets.py
	SHORT_RUN_SECS=0 $(PY) bin/tts_generate.py
	SHORT_RUN_SECS=0 $(PY) bin/generate_captions.py
	SHORT_RUN_SECS=0 $(PY) bin/assemble_video.py
	$(PY) bin/upload_stage.py

# Quick test run with capped durations (SHORT_RUN_SECS, default 25s)
quick-run:
	SHORT_RUN_SECS?=25; export SHORT_RUN_SECS; \
	$(PY) bin/niche_trends.py; \
	$(PY) bin/llm_cluster.py; \
	$(PY) bin/llm_outline.py; \
	$(PY) bin/llm_script.py; \
	$(PY) bin/fetch_assets.py; \
	$(PY) bin/tts_generate.py; \
	$(PY) bin/generate_captions.py; \
	$(PY) bin/assemble_video.py; \

# Trending topics intake
trending-intake:
	$(PY) bin/trending_intake.py --mode reuse --limit 10

trending-intake-live:
	$(PY) bin/trending_intake.py --mode live --providers reddit,youtube,google_trends --limit 20
	$(PY) bin/upload_stage.py

blog-once:
	$(PY) bin/blog_pick_topics.py
	$(PY) bin/blog_generate_post.py
	$(PY) bin/blog_render_html.py
	$(PY) bin/blog_post_wp.py
	$(PY) bin/blog_ping_search.py

# Music Library Management
music-setup:
	$(PY) bin/music_manager.py setup

music-import:
	@echo "Usage: make music-import SOURCE=/path/to/music LICENSE='license-type'"
	$(PY) bin/music_manager.py import --source $(SOURCE) --license $(LICENSE)

music-stats:
	$(PY) bin/music_manager.py stats

music-validate:
	$(PY) bin/music_manager.py validate

music-test:
	@echo "Usage: make music-test SCRIPT=/path/to/script TONE=tone DURATION=duration"
	$(PY) bin/music_manager.py test --script $(SCRIPT) --tone $(TONE) --duration $(DURATION)

cron-install:
	crontab ops/crontab.seed.txt

backup:
	bash bin/backup_wp.sh
	bash bin/backup_repo.sh

health:
	$(PY) bin/health_server.py

web-ui:
	$(PY) bin/web_ui.py

analytics:
	$(PY) bin/analytics_collector.py

fact-check:
	@echo "Usage: make fact-check FILE=path/to/content.md"
	@if [ -z "$(FILE)" ]; then echo "Please specify FILE=path/to/content.md"; exit 1; fi
	$(PY) bin/fact_check.py $(FILE)

asset-quality:
	@echo "Usage: make asset-quality FILE=path/to/asset QUERY='search query'"
	@if [ -z "$(FILE)" ]; then echo "Please specify FILE=path/to/asset"; exit 1; fi
	@if [ -z "$(QUERY)" ]; then echo "Please specify QUERY='search terms'"; exit 1; fi
	$(PY) bin/asset_quality.py $(FILE) --query "$(QUERY)"

test:
	@echo "Running REUSE mode tests (no network calls)..."
	TEST_ASSET_MODE=reuse $(PY) -m pytest tests/ -m "not liveapi" -v
	@echo "Running E2E test in reuse mode..."
	TEST_ASSET_MODE=reuse $(PY) bin/test_e2e.py

test-svg-ops:
	@echo "Testing SVG Path Operations..."
	$(PY) test_svg_path_ops.py

demo-svg-ops:
	@echo "Demonstrating SVG Path Operations..."
	$(PY) demo_svg_path_ops.py

check-llm:
	@echo "Checking Ollama LLM integration..."
	$(PY) bin/check_llm_integration.py $(ARGS)

test-live:
	@echo "Running LIVE mode tests (requires API keys)..."
	@echo "WARNING: This will make actual API calls and consume quota!"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	TEST_ASSET_MODE=live $(PY) -m pytest tests/ -m "liveapi" -v

test-all:
	@echo "Running ALL tests (reuse + live modes)..."
	$(MAKE) test
	$(MAKE) test-live

# Pipeline mode toggles
animatics-only:
	@echo "Setting pipeline to animatics-only mode..."
	@yq -yi '.video.animatics_only = true | .video.enable_legacy_stock = false' conf/global.yaml
	@echo "✅ Pipeline now in animatics-only mode (default)"

legacy-on:
	@echo "Enabling legacy stock asset pipeline..."
	@yq -yi '.video.animatics_only = false | .video.enable_legacy_stock = true' conf/global.yaml
	@echo "✅ Legacy stock asset pipeline enabled"

procedural-pipeline:
	@echo "Running procedural animatics pipeline..."
	$(PY) bin/run_pipeline.py --dry-run --topic "2-minute history of Ray & Charles Eames"

procedural-pipeline-live:
	@echo "Running procedural animatics pipeline (live mode)..."
	$(PY) bin/run_pipeline.py --topic "2-minute history of Ray & Charles Eames"

pipeline-status:
	@echo "Current pipeline configuration:"
	@yq '.video' conf/global.yaml

# -------- Research Pipeline Management --------
research-reuse:
	@echo "Usage: make research-reuse SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "Running research pipeline in REUSE mode for $(SLUG)..."
	$(PY) bin/trending_intake.py --mode reuse --slug $(SLUG)
	$(PY) bin/research_collect.py --slug $(SLUG) --mode reuse --max 50
	$(PY) bin/research_ground.py scripts/$(SLUG).txt --slug $(SLUG) --mode reuse
	$(PY) bin/fact_guard.py --slug $(SLUG) --mode reuse
	@echo "Research pipeline completed in REUSE mode for $(SLUG)"

research-live:
	@echo "Usage: make research-live SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "WARNING: This will make live API calls and consume quota!"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo "Running research pipeline in LIVE mode for $(SLUG)..."
	$(PY) bin/trending_intake.py --mode live --slug $(SLUG)
	$(PY) bin/research_collect.py --slug $(SLUG) --mode live --max 50
	$(PY) bin/research_ground.py scripts/$(SLUG).txt --slug $(SLUG) --mode live
	$(PY) bin/fact_guard.py --slug $(SLUG) --mode live
	@echo "Research pipeline completed in LIVE mode for $(SLUG)"

research-report:
	@echo "Usage: make research-report SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "Generating research report for $(SLUG)..."
	$(PY) bin/research_report.py --slug $(SLUG) --compact
	@echo "Research report completed for $(SLUG)"

# -------- Asset Loop Management --------
asset-rebuild:
	@echo "Rebuilding asset library manifest..."
	$(PY) bin/asset_manifest.py --rebuild

asset-plan:
	@echo "Usage: make asset-plan SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "Creating asset plan for $(SLUG)..."
	$(PY) bin/asset_librarian.py --slug $(SLUG)

asset-fill:
	@echo "Usage: make asset-fill SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "Filling asset gaps for $(SLUG)..."
	$(PY) bin/asset_generator.py --plan runs/$(SLUG)/asset_plan.json

asset-reflow:
	@echo "Usage: make asset-reflow SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "Reflowing assets for $(SLUG)..."
	$(PY) bin/reflow_assets.py --slug $(SLUG)

asset-loop:
	@echo "Usage: make asset-loop SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "Running complete asset loop for $(SLUG)..."
	$(MAKE) asset-rebuild
	$(MAKE) asset-plan SLUG=$(SLUG)
	$(MAKE) asset-fill SLUG=$(SLUG)
	$(MAKE) asset-reflow SLUG=$(SLUG)
	@echo "Asset loop completed for $(SLUG)"

# -------- Pacing KPI & Feedback Management --------
pacing-report:
	@echo "Usage: make pacing-report SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "Computing pacing KPIs for $(SLUG)..."
	$(PY) bin/pacing_kpi.py --slug $(SLUG)
	@echo "Pacing report completed for $(SLUG)"

pacing-tune:
	@echo "Usage: make pacing-tune SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "Running KPI computation and feedback adjustment for $(SLUG)..."
	$(MAKE) pacing-report SLUG=$(SLUG)
	$(PY) bin/pacing_feedback.py --slug $(SLUG) --apply
	@echo "Pacing tuning completed for $(SLUG)"

pacing-smoke:
	@echo "Usage: make pacing-smoke SLUG=<slug>"
	@if [ -z "$(SLUG)" ]; then echo "Please specify SLUG=<slug>"; exit 1; fi
	@echo "Running pacing smoke test for $(SLUG)..."
	$(MAKE) pacing-report SLUG=$(SLUG)
	$(PY) bin/pacing_feedback.py --slug $(SLUG) --dry-run
	@echo "Pacing smoke test completed for $(SLUG)"

# -------- Raspberry Pi Helpers --------
PI_HOST ?= onepi
PI_DIR ?= ~/youtube_onepi_pipeline
SSH := ssh $(PI_HOST)
RSYNC := rsync -az --delete
RSYNC_EXCLUDES := \
	--exclude '.git' \
	--exclude '.venv' \
	--exclude 'logs/' \
	--exclude 'data/cache/' \
	--exclude 'assets/' \
	--exclude 'videos/' \
	--exclude 'voiceovers/'

pi-deploy:
	@$(SSH) "set -e; cd $(PI_DIR) && git fetch --all && git reset --hard origin/main && python3 -m venv .venv && . .venv/bin/activate && pip -q install --upgrade pip && pip -q install -r requirements.txt && python bin/check_env.py"

pi-run-once:
	@$(SSH) "set -e; cd $(PI_DIR) && . .venv/bin/activate && make run-once"

pi-blog-once:
	@$(SSH) "set -e; cd $(PI_DIR) && . .venv/bin/activate && make blog-once"

pi-sync:
	@$(RSYNC) $(RSYNC_EXCLUDES) ./ $(PI_HOST):$(PI_DIR)/
	@$(SSH) "set -e; cd $(PI_DIR) && python3 -m venv .venv && . .venv/bin/activate && pip -q install --upgrade pip && pip -q install -r requirements.txt && python bin/check_env.py"

pull-artifacts:
	@mkdir -p videos voiceovers
	@$(RSYNC) $(PI_HOST):$(PI_DIR)/videos/ ./videos/ || true
	@$(RSYNC) $(PI_HOST):$(PI_DIR)/voiceovers/ ./voiceovers/ || true

pi-health:
	@curl -s http://$(PI_HOST):8088/health | python -m json.tool || true

# =============================================================================
# OPERATOR CONSOLE TARGETS
# =============================================================================

op-console:
	@echo "Starting FastAPI Operator Console..."
	@echo "Server will be available at: http://127.0.0.1:8008"
	@echo "API docs: http://127.0.0.1:8008/docs"
	@echo "Admin token: default-admin-token-change-me (set ADMIN_TOKEN env var to override)"
	@echo ""
	$(PY) run_server.py

clean-op-console:
	@echo "Cleaning operator console artifacts..."
	@rm -f jobs.db
	@rm -rf __pycache__
	@rm -rf fastapi_app/__pycache__
	@echo "✅ Operator console cleaned"

test-api:
	@echo "Testing FastAPI endpoints..."
	$(PY) test_api.py

test-orchestrator:
	@echo "Testing orchestrator state machine..."
	$(PY) test_orchestrator.py

test-orchestrator-simple:
	@echo "Testing orchestrator state machine (simple mode)..."
	$(PY) test_orchestrator_simple.py

test-orchestrator-basic:
	@echo "Testing basic orchestrator functionality..."
	$(PY) test_orchestrator_basic.py
