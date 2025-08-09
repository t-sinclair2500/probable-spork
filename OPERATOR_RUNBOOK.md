# Operator Runbook — One-Pi Shared Pipeline

## First-time bootstrap
```bash
make install
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
cp conf/global.example.yaml conf/global.yaml
cp conf/blog.example.yaml conf/blog.yaml
cp .env.example .env
make check
```

## Manual one-shot
```bash
source .venv/bin/activate
make run-once
make blog-once
```

## Cron install
```bash
crontab crontab.seed.txt
```

## Health server & systemd
```bash
sudo bash scripts/install_systemd_and_logrotate.sh
# Health at http://PI:8088/health
```

## Backups
```bash
make backup
```

## Restore (outline)
1) Reinstall packages & clone repo.
2) Restore WP DB + wp-content from backups.
3) Restore repo backups to `data/` and media dirs.
4) Recreate application passwords for WordPress poster.

## Troubleshooting
- Check `logs/pipeline.log` and `jobs/state.jsonl`.
- Ensure GPU split low and swap on SSD.
- If CPU temp > 75°C, pipeline defers heavy steps.
 - Missing API keys: copy `.env.example` → `.env` and fill provider keys (PIXABAY/PEXELS). `make check` reports missing keys. `conf/sources.yaml` is deprecated.
