#!/bin/bash
# Create Python venv and install backend dependencies (run on first install / upgrade).
# NOTE: Never modifies /var/lib/market-monitor/ — user data is kept separate from app code.
set -euo pipefail

VENV_DIR="/opt/market-monitor/venv"
REQ_FILE="/opt/market-monitor/backend/requirements.txt"

if [[ ! -f "$REQ_FILE" ]]; then
  echo "ERROR: $REQ_FILE not found" >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/pip" install --upgrade pip wheel
"$VENV_DIR/bin/pip" install -r "$REQ_FILE"

chown -R market-monitor:market-monitor /opt/market-monitor/venv
