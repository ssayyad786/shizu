# Shizu / Market Monitor — persistent data
#
# This directory is NEVER removed on app or RPM upgrades.
# Only application code in /opt/market-monitor/ is replaced.
#
# Files:
#   market.db     — SQLite database (wishlist, signal history, trade outcomes)
#   backups/      — automatic backups before each upgrade
#
# Config: /etc/market-monitor/config (MARKET_DATA_DIR)
#
# Manual backup:
#   sudo bash /opt/market-monitor/scripts/backup-data.sh
#   — or from a git checkout: sudo bash scripts/backup-data.sh
