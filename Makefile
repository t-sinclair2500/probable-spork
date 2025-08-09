SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
export PYTHONPATH := $(CURDIR)

install:
	python3 -m venv $(VENV)
	. $(VENV)/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

check:
	$(PY) bin/check_env.py

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

test:
	$(PY) -m unittest discover -s tests -p "test_*.py" -v
	$(PY) bin/test_e2e.py

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
