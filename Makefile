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
	$(PY) bin/tts_generate.py
	$(PY) bin/generate_captions.py
	$(PY) bin/assemble_video.py
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
