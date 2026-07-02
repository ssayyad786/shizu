#!/bin/bash
# =============================================================================
# Shizu — one-command server upgrade
#
# Pulls latest code, builds RPM, installs, restarts services, restores HTTPS.
#
# Usage (from repo clone on the VM):
#   cd ~/shizu
#   sudo bash scripts/upgrade.sh
#
# Optional custom domain (default: shizu.space):
#   sudo bash scripts/upgrade.sh shizu.space
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DOMAIN="${1:-shizu.space}"
DATA_DIR="/var/lib/market-monitor"

log()  { echo -e "${GREEN}==>${NC} $*"; }
warn() { echo -e "${YELLOW}==> WARNING:${NC} $*"; }
die()  { echo -e "${RED}ERROR:${NC} $*" >&2; exit 1; }

if [[ $EUID -ne 0 ]]; then
  die "Run as root: sudo bash scripts/upgrade.sh"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

log "Shizu upgrade — repo: $REPO_ROOT"

# --- OS / package manager ---
if [[ -f /etc/os-release ]]; then
  # shellcheck source=/dev/null
  source /etc/os-release
  case "${ID:-}" in
    rocky|almalinux|rhel|centos|fedora) PKG_MGR="dnf" ;;
    *) die "Unsupported OS '${ID:-unknown}'" ;;
  esac
else
  die "Cannot detect OS"
fi

read_version() {
  awk -F'"' '/^__version__/ {print $2; exit}' "$REPO_ROOT/backend/app/version.py"
}

OLD_VERSION=""
if [[ -f /opt/market-monitor/backend/app/version.py ]]; then
  OLD_VERSION=$(awk -F'"' '/^__version__/ {print $2; exit}' /opt/market-monitor/backend/app/version.py 2>/dev/null || true)
fi

# --- Git pull (as repo owner when run via sudo) ---
git_pull() {
  local git_cmd=(git -C "$REPO_ROOT")
  local repo_owner
  repo_owner=$(stat -c '%U' "$REPO_ROOT")

  if [[ "$repo_owner" != "root" && -n "$repo_owner" ]]; then
    sudo -u "$repo_owner" "${git_cmd[@]}" config --global --add safe.directory "$REPO_ROOT" 2>/dev/null || true
    log "Pulling latest code (as $repo_owner)..."
    if ! sudo -u "$repo_owner" "${git_cmd[@]}" pull --ff-only; then
      warn "git pull blocked — discarding local edits to packaging/rpm/build-rpm.sh and retrying"
      sudo -u "$repo_owner" "${git_cmd[@]}" checkout -- packaging/rpm/build-rpm.sh 2>/dev/null || true
      sudo -u "$repo_owner" "${git_cmd[@]}" pull --ff-only
    fi
  else
    git config --global --add safe.directory "$REPO_ROOT" 2>/dev/null || true
    log "Pulling latest code..."
    if ! "${git_cmd[@]}" pull --ff-only; then
      warn "git pull blocked — discarding local edits to packaging/rpm/build-rpm.sh and retrying"
      "${git_cmd[@]}" checkout -- packaging/rpm/build-rpm.sh 2>/dev/null || true
      "${git_cmd[@]}" pull --ff-only
    fi
  fi
}

git_pull
NEW_VERSION=$(read_version)
log "Target version: ${NEW_VERSION}${OLD_VERSION:+ (was ${OLD_VERSION})}"

# --- Dependencies ---
log "Installing build dependencies..."
$PKG_MGR install -y epel-release 2>/dev/null || true
$PKG_MGR install -y \
  rpm-build rpmdevtools \
  python3 python3-pip python3-devel \
  nodejs npm \
  nginx \
  gcc gcc-c++ make \
  git curl \
  policycoreutils-python-utils \
  firewalld \
  certbot python3-certbot-nginx \
  2>/dev/null || true

# --- Firewall HTTP + HTTPS ---
systemctl enable --now firewalld 2>/dev/null || true
if systemctl is-active firewalld &>/dev/null; then
  firewall-cmd --permanent --add-service=http 2>/dev/null || firewall-cmd --permanent --add-port=80/tcp
  firewall-cmd --permanent --add-service=https 2>/dev/null || firewall-cmd --permanent --add-port=443/tcp
  firewall-cmd --reload
  log "Firewall: HTTP and HTTPS allowed"
fi

# --- Backup database ---
if [[ -f "$DATA_DIR/market.db" ]]; then
  log "Backing up database..."
  bash "$REPO_ROOT/scripts/backup-data.sh" || warn "Backup script failed (continuing)"
fi

# --- Build & install RPM ---
log "Building RPM..."
chmod +x packaging/rpm/build-rpm.sh packaging/rpm/install-python-deps.sh
bash packaging/rpm/build-rpm.sh

RPM_FILE=$(ls ~/rpmbuild/RPMS/*/*.rpm 2>/dev/null | grep market-monitor | sort -V | tail -1)
[[ -n "$RPM_FILE" ]] || die "RPM build failed — no .rpm file found"

log "Installing: $RPM_FILE"
$PKG_MGR install -y "$RPM_FILE"

# --- Nginx config (RPM %config(noreplace) may skip updates) ---
NGINX_CONF="/etc/nginx/conf.d/market-monitor.conf"
if [[ -f "$REPO_ROOT/packaging/rpm/nginx-market-monitor.conf" ]]; then
  log "Updating nginx config..."
  cp "$REPO_ROOT/packaging/rpm/nginx-market-monitor.conf" "$NGINX_CONF"
  nginx -t
fi

# --- Services ---
log "Restarting services..."
systemctl daemon-reload
systemctl enable market-monitor nginx certbot-renew.timer 2>/dev/null || true
systemctl start certbot-renew.timer 2>/dev/null || true
systemctl restart market-monitor nginx
sleep 2

# --- Restore HTTPS if certificate exists but 443 is down ---
restore_https() {
  local cert_dir="/etc/letsencrypt/live/${DOMAIN}"
  local renewal="/etc/letsencrypt/renewal/${DOMAIN}.conf"

  if [[ ! -d "$cert_dir" && ! -f "$renewal" ]]; then
    warn "No SSL cert for ${DOMAIN} — HTTP only. Run certbot when ready."
    return 0
  fi

  if ss -tln | grep -q ':443 '; then
    log "HTTPS already listening on port 443"
    return 0
  fi

  log "SSL cert found but port 443 not open — reinstalling nginx SSL config..."
  if certbot install --cert-name "$DOMAIN" --nginx --non-interactive 2>/dev/null; then
    log "certbot install: OK"
  elif certbot --nginx -d "$DOMAIN" -d "www.${DOMAIN}" --reinstall --non-interactive --redirect 2>/dev/null; then
    log "certbot reinstall: OK"
  else
    warn "Automatic SSL restore failed. Run manually:"
    echo "  sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
    echo "  Choose: 1) Reinstall existing certificate"
    return 1
  fi

  nginx -t
  systemctl reload nginx
}

restore_https || true

# --- Health checks ---
echo ""
log "Health checks"
HTTP_OK=0
HTTPS_OK=0

if curl -sf http://127.0.0.1/api/health >/dev/null; then
  HTTP_OK=1
  log "HTTP:  OK — $(curl -s http://127.0.0.1/api/health)"
else
  warn "HTTP health check failed"
  echo "  sudo journalctl -u market-monitor -n 30"
  echo "  sudo systemctl status nginx market-monitor"
fi

if ss -tln | grep -q ':443 '; then
  if curl -sfk "https://${DOMAIN}/api/health" >/dev/null 2>&1 || \
     curl -sf "https://127.0.0.1/api/health" --resolve "${DOMAIN}:443:127.0.0.1" >/dev/null 2>&1; then
    HTTPS_OK=1
    log "HTTPS: OK — https://${DOMAIN}/"
  else
    warn "Port 443 open but HTTPS health check failed — try: sudo certbot install --cert-name ${DOMAIN}"
  fi
else
  warn "HTTPS not listening on 443"
fi

EXTERNAL_IP=""
if curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip" \
  -o /tmp/shizu-upgrade-ip 2>/dev/null; then
  EXTERNAL_IP=$(cat /tmp/shizu-upgrade-ip)
  rm -f /tmp/shizu-upgrade-ip
fi

echo ""
echo "=============================================="
if [[ "$HTTP_OK" -eq 1 ]]; then
  echo -e "  ${GREEN}Upgrade complete — v${NEW_VERSION}${NC}"
else
  echo -e "  ${YELLOW}Upgrade finished with warnings${NC}"
fi
echo "=============================================="
echo ""
echo "  HTTP:   http://127.0.0.1/"
[[ -n "$EXTERNAL_IP" && "$EXTERNAL_IP" != "null" ]] && echo "  Public: http://${EXTERNAL_IP}/"
[[ "$HTTPS_OK" -eq 1 ]] && echo "  HTTPS:  https://${DOMAIN}/"
echo ""
echo "  Data:   ${DATA_DIR}/market.db (unchanged)"
echo "  Logs:   sudo journalctl -u market-monitor -f"
echo ""
