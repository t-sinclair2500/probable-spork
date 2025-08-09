#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date +%Y%m%d_%H%M%S)
SRC="/home/pi/youtube_onepi_pipeline"
BKDIR="${1:-/home/pi/repo_backups}"
mkdir -p "$BKDIR"
tar czf "$BKDIR/youtube_onepi_${STAMP}.tgz" -C "$SRC" data scripts assets voiceovers videos jobs conf
echo "Repo backup written to $BKDIR"
