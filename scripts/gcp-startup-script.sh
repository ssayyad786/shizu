#!/bin/bash
# GCP VM startup script — paste into GCP Console → VM → Edit → Automation → Startup script
# Or: gcloud compute instances create ... --metadata-from-file startup-script=scripts/gcp-startup-script.sh
#
# Clones shizu (if not present) and runs full setup. Set REPO_URL if using a private fork.

set -euo pipefail

REPO_URL="${SHIZU_REPO_URL:-https://github.com/ssayyad786/shizu.git}"
INSTALL_DIR="/opt/shizu-src"
LOG="/var/log/shizu-setup.log"

exec > >(tee -a "$LOG") 2>&1
echo "=== Shizu setup started at $(date) ==="

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  dnf install -y git 2>/dev/null || yum install -y git
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
git pull --ff-only || true
bash scripts/setup-gcp-instance.sh

echo "=== Shizu setup finished at $(date) ==="
