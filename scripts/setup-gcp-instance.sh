#!/bin/bash
# =============================================================================
# Shizu (Market Monitor) — full GCP VM setup
#
# Run on a fresh Rocky Linux / AlmaLinux / RHEL 9 VM after cloning the repo:
#
#   git clone https://github.com/ssayyad786/shizu.git
#   cd shizu
#   sudo bash scripts/setup-gcp-instance.sh
#
# This script:
#   1. Installs OS packages (nginx, python, node, rpm-build, etc.)
#   2. Opens firewall port 80
#   3. Builds the RPM from this repo
#   4. Installs the RPM (app + systemd + nginx)
#   5. Starts services and prints the URL
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}==>${NC} $*"; }
warn() { echo -e "${YELLOW}==> WARNING:${NC} $*"; }
die()  { echo -e "${RED}ERROR:${NC} $*" >&2; exit 1; }

if [[ $EUID -ne 0 ]]; then
  die "Run as root: sudo bash scripts/setup-gcp-instance.sh"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"
log "Repo root: $REPO_ROOT"

# --- OS check ---
if [[ -f /etc/os-release ]]; then
  # shellcheck source=/dev/null
  source /etc/os-release
  log "OS: ${PRETTY_NAME:-unknown}"
  case "${ID:-}" in
    rocky|almalinux|rhel|centos|fedora)
      PKG_MGR="dnf"
      ;;
    *)
      die "Unsupported OS '${ID}'. Use Rocky Linux 9, AlmaLinux 9, or RHEL 9."
      ;;
  esac
else
  die "Cannot detect OS."
fi

# --- Install dependencies ---
log "Installing system packages..."
$PKG_MGR install -y \
  rpm-build rpmdevtools \
  python3 python3-pip python3-devel \
  nodejs npm \
  nginx \
  gcc gcc-c++ make \
  git curl \
  policycoreutils-python-utils \
  firewalld \
  2>/dev/null || $PKG_MGR install -y \
  rpm-build rpmdevtools \
  python3 python3-pip python3-devel \
  nodejs npm \
  nginx \
  gcc gcc-c++ make \
  git curl \
  firewalld

# node on RHEL sometimes needs alternatives
if ! command -v npm &>/dev/null; then
  die "npm not found after install. Enable EPEL or install Node.js manually."
fi

# --- Firewall ---
log "Configuring firewall (port 80)..."
systemctl enable --now firewalld 2>/dev/null || true
if systemctl is-active firewalld &>/dev/null; then
  firewall-cmd --permanent --add-service=http 2>/dev/null || firewall-cmd --permanent --add-port=80/tcp
  firewall-cmd --reload
  log "Firewall: HTTP (port 80) allowed"
else
  warn "firewalld not running — ensure GCP VPC firewall allows tcp:80"
fi

# --- Build RPM ---
log "Building RPM..."
chmod +x packaging/rpm/build-rpm.sh packaging/rpm/install-python-deps.sh
bash packaging/rpm/build-rpm.sh

RPM_FILE=$(ls ~/rpmbuild/RPMS/*/*.rpm 2>/dev/null | grep market-monitor | sort -V | tail -1)
[[ -n "$RPM_FILE" ]] || die "RPM build failed — no .rpm file found"

log "Installing: $RPM_FILE"

# Backup database before upgrade (RPM %pre also backs up, this is an extra safety net)
DATA_DIR="/var/lib/market-monitor"
if [[ -f "$DATA_DIR/market.db" ]]; then
  log "Backing up database before install/upgrade..."
  bash "$REPO_ROOT/scripts/backup-data.sh" || true
fi

$PKG_MGR install -y "$RPM_FILE"

# --- Verify services ---
log "Starting services..."
systemctl enable market-monitor nginx
systemctl restart market-monitor nginx

sleep 2

if systemctl is-active market-monitor &>/dev/null && systemctl is-active nginx &>/dev/null; then
  log "Services running"
else
  warn "A service may not be running. Check:"
  echo "  sudo systemctl status market-monitor nginx"
  echo "  sudo journalctl -u market-monitor -n 50"
fi

# Health check
if curl -sf http://127.0.0.1/api/health >/dev/null; then
  log "API health check: OK"
  curl -s http://127.0.0.1/api/health | python3 -m json.tool 2>/dev/null || true
else
  warn "API health check failed — wait a few seconds and run: curl http://127.0.0.1/api/health"
fi

# --- External IP (GCP metadata) ---
EXTERNAL_IP=""
if curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip" \
  -o /tmp/shizu-ip 2>/dev/null; then
  EXTERNAL_IP=$(cat /tmp/shizu-ip)
  rm -f /tmp/shizu-ip
fi

echo ""
echo "=============================================="
echo -e "  ${GREEN}Shizu Market Monitor is installed!${NC}"
echo "=============================================="
echo ""
echo "  Local:    http://127.0.0.1/"
if [[ -n "$EXTERNAL_IP" && "$EXTERNAL_IP" != "null" && -n "${EXTERNAL_IP// }" ]]; then
  echo "  Public:   http://${EXTERNAL_IP}/"
else
  echo "  Public:   http://<YOUR_VM_EXTERNAL_IP>/"
  echo ""
  echo "  If the page does not load, open port 80 in GCP:"
  echo "    VPC network → Firewall → allow tcp:80 to this VM"
fi
echo ""
echo "  Data:     /var/lib/market-monitor/market.db  (wishlist + history)"
echo "  Backups:  /var/lib/market-monitor/backups/"
echo "  Backup:   sudo /opt/market-monitor/scripts/backup-data.sh"
echo ""
echo "  Upgrades replace /opt/market-monitor/ only — your data is never deleted."
echo ""
echo "  Logs:     sudo journalctl -u market-monitor -f"
echo "  Upgrade:  cd ~/shizu && sudo bash scripts/upgrade.sh"
echo ""
