#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date +%Y%m%d_%H%M%S)
BKDIR="${1:-/home/pi/wp_backups}"
mkdir -p "$BKDIR"
mysqldump wpblog > "$BKDIR/wpblog_${STAMP}.sql"
tar czf "$BKDIR/wpfiles_${STAMP}.tgz" /var/www/wordpress/wp-content
echo "Backups written to $BKDIR"
