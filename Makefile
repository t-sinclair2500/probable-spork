# Probable Spork — Makefile (Mac-first, local-only)
SHELL := /bin/bash

PY ?= python
SLUG ?= demo-001
MODE ?= reuse
SEED ?= 1337
VIRAL ?= 1
SHORTS ?= 1
SEO ?= 1
YT_ONLY ?= 0
FROM ?=

OS := $(shell uname -s)

# Colors
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[1;34m
RED := \033[0;31m
NC := \033[0m

.DEFAULT_GOAL := help

.PHONY: help install setup ensure-models smoke run viral shorts seo qa ui audit-wiring audit-consistency quality quality-fix clean clean-artifacts

define HEADER
@echo -e "$(BLUE)==>$(NC) $(1)"
endef

help: ## Show this help
	@echo "Probable Spork — targets"
	@grep -E '^[a-zA-Z0-9_\-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*?## /: /' | sort

install: ## Install Python dependencies
	$(call HEADER,Installing dependencies)
	@if [ ! -d ".venv" ]; then \
		echo -e "$(YELLOW)Creating virtual environment...$(NC)"; \
		python3.11 -m venv .venv; \
	fi
	@echo -e "$(GREEN)Activating virtual environment and installing packages...$(NC)"
	@source .venv/bin/activate && pip install --upgrade pip
	@source .venv/bin/activate && pip install -r requirements.txt
	@echo -e "$(GREEN)Dependencies installed successfully!$(NC)"
	@echo -e "$(BLUE)To activate: source .venv/bin/activate$(NC)"

setup: ## Complete setup: install dependencies and ensure models
	$(call HEADER,Complete setup)
	@$(MAKE) install
	@$(MAKE) ensure-models
	@echo -e "$(GREEN)Setup complete! Ready to run: make smoke SLUG=eames$(NC)"

ensure-models: ## Ensure local LLM models for Viral (ollama)
	$(call HEADER,Ensuring models)
	@if command -v ollama >/dev/null 2>&1; then \
		echo "Using ollama"; \
		ollama list || true; \
		ollama pull llama3.2:3b || true; \
	else \
		echo -e "$(YELLOW)ollama not found — Viral will use heuristics-only fallback$(NC)"; \
	fi

smoke: ## Minimal e2e on $(SLUG)
	$(call HEADER,Smoke run $(SLUG))
	$(PY) bin/run_pipeline.py --slug $(SLUG) --seed $(SEED) --enable-viral --enable-shorts --enable-seo

run: ## Full pipeline (honors toggles VIRAL/SHORTS/SEO/YT_ONLY/FROM)
	$(call HEADER,Full pipeline $(SLUG))
	$(PY) bin/run_pipeline.py --slug $(SLUG) --seed $(SEED) $(if $(YT_ONLY),--yt-only,) \
	$(if $(FROM),--from-step $(FROM),) \
	$(if $(filter 1,$(VIRAL)),--enable-viral,--no-viral) \
	$(if $(filter 1,$(SHORTS)),--enable-shorts,--no-shorts) \
	$(if $(filter 1,$(SEO)),--enable-seo,--no-seo)

viral: ## Run Viral Lab (variants only)
	$(call HEADER,Viral lab $(SLUG))
	$(PY) bin/viral/run.py --slug $(SLUG) || true

shorts: ## Generate Shorts/Cutdowns
	$(call HEADER,Shorts $(SLUG))
	$(PY) bin/viral/shorts.py --slug $(SLUG)

seo: ## SEO packaging + end screens
	$(call HEADER,SEO packaging $(SLUG))
	$(PY) bin/packaging/seo_packager.py --slug $(SLUG)
	$(PY) bin/packaging/end_screens.py --slug $(SLUG) || true

qa: ## Run QA gates for $(SLUG)
	$(call HEADER,QA $(SLUG))
	$(PY) bin/qa/run_gates.py --slug $(SLUG) || true

ui: ## Launch Gradio Operator Console
	$(call HEADER,Launching UI)
	$(PY) bin/ui/app.py

audit-wiring: ## Viral wiring auditor
	$(call HEADER,Wiring auditor)
	$(PY) bin/audit/viral_wiring_auditor.py --slug $(SLUG) || true

audit-consistency: ## General implementation auditor
	$(call HEADER,Consistency auditor)
	$(PY) bin/audit/consistency_auditor.py || true

quality: ## Run code quality suite (no fixes)
	$(call HEADER,Quality report)
	$(PY) bin/quality/run_code_quality.py || true
	@echo -e "$(GREEN)Report: CODE_QUALITY_REPORT.md$(NC)"

quality-fix: ## Apply safe autofixes, then re-run analyses
	$(call HEADER,Quality autofix + report)
	$(PY) bin/quality/run_code_quality.py --apply-fixes || true
	@echo -e "$(GREEN)Report: CODE_QUALITY_REPORT.md$(NC)"

clean: ## Remove caches and temporary files
	$(call HEADER,Clean caches)
	find . -type d -name "__pycache__" -prune -exec rm -rf {} \; || true
	find . -type f -name "*.pyc" -delete || true

clean-artifacts: ## Danger: remove generated videos and assets (set CONFIRM=1)
	@if [ "$(CONFIRM)" != "1" ]; then echo -e "$(RED)Refusing to delete artifacts. Re-run with CONFIRM=1$(NC)"; exit 1; fi
	$(call HEADER,Removing artifacts)
	rm -rf videos/* assets/generated/* || true
