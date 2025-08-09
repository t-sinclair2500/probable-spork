SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
export PYTHONPATH := $(CURDIR)

.PHONY: install check docs run-once quick-run blog-once cron-install backup health test pi-deploy pi-run-once pi-blog-once pi-sync pull-artifacts pi-health

install:
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
	@echo "  make check             - Validate environment setup"
	@echo "  make quick-run         - Test pipeline with short durations"
	@echo "  make fact-check FILE=  - Fact-check markdown content"
	@echo "  make asset-quality     - Analyze asset quality and relevance"
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
	$(PY) bin/upload_stage.py

blog-once:
	$(PY) bin/blog_pick_topics.py
	$(PY) bin/blog_generate_post.py
	$(PY) bin/blog_render_html.py
	$(PY) bin/blog_post_wp.py
	$(PY) bin/blog_ping_search.py

cron-install:
	crontab crontab.seed.txt

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

test-live:
	@echo "Running LIVE mode tests (requires API keys)..."
	@echo "WARNING: This will make actual API calls and consume quota!"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	TEST_ASSET_MODE=live $(PY) -m pytest tests/ -m "liveapi" -v

test-all:
	@echo "Running ALL tests (reuse + live modes)..."
	$(MAKE) test
	$(MAKE) test-live

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
