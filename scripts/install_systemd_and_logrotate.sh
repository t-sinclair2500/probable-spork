#!/usr/bin/env bash
set -euo pipefail
# Install systemd units and logrotate config
sudo cp services/ollama.service /etc/systemd/system/ollama.service
sudo cp services/pipeline-health.service /etc/systemd/system/pipeline-health.service
sudo systemctl daemon-reload
sudo systemctl enable ollama.service
sudo systemctl enable pipeline-health.service
sudo systemctl start ollama.service
sudo systemctl start pipeline-health.service

# Install logrotate
sudo cp ops/logrotate.youtube_onepi /etc/logrotate.d/youtube_onepi
echo "Installed systemd units and logrotate config."
