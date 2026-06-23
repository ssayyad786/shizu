#!/bin/bash
# Backup Shizu / Market Monitor database (wishlist + trade history).
#
# Data is always stored at: /var/lib/market-monitor/market.db
# Backups go to:           /var/lib/market-monitor/backups/
#
# Usage:
#   sudo bash scripts/backup-data.sh

set -euo pipefail

DATA_DIR="${MARKET_DATA_DIR:-/var/lib/market-monitor}"
DB_FILE="$DATA_DIR/market.db"
BACKUP_DIR="$DATA_DIR/backups"
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/market.db.$STAMP"

if [[ ! -f "$DB_FILE" ]]; then
  echo "No database yet at $DB_FILE (nothing to backup)"
  exit 0
fi

mkdir -p "$BACKUP_DIR"
cp -a "$DB_FILE" "$BACKUP_FILE"
chown market-monitor:market-monitor "$BACKUP_FILE" 2>/dev/null || true

# Keep last 10 backups
ls -1t "$BACKUP_DIR"/market.db.* 2>/dev/null | tail -n +11 | xargs -r rm -f

echo "Backup saved: $BACKUP_FILE"
echo "Data directory: $DATA_DIR"
