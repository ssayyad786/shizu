#!/bin/bash
# Quick recovery when the site shows 502 Bad Gateway (nginx up, backend down).
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
log()  { echo -e "${GREEN}==>${NC} $*"; }
warn() { echo -e "${YELLOW}==> WARNING:${NC} $*"; }
die()  { echo -e "${RED}ERROR:${NC} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root: sudo bash scripts/fix-backend.sh"

DOMAIN="${1:-shizu.space}"

log "Checking services..."
systemctl status market-monitor --no-pager -l || true
echo ""
systemctl status nginx --no-pager -l || true
echo ""

if ! systemctl is-active --quiet market-monitor; then
  warn "Restarting market-monitor..."
  systemctl restart market-monitor
  sleep 2
fi

if ! systemctl is-active --quiet market-monitor; then
  warn "Last market-monitor logs:"
  journalctl -u market-monitor -n 50 --no-pager
  die "market-monitor still not running"
fi

if ! curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
  warn "Backend not responding on :8000"
  journalctl -u market-monitor -n 50 --no-pager
  die "Health check failed"
fi

log "Backend OK: $(curl -s http://127.0.0.1:8000/api/health)"

if ! ss -tln | grep -q ':443 '; then
  warn "HTTPS (443) not listening — restoring certbot nginx config..."
  certbot install --cert-name "$DOMAIN" --nginx --non-interactive 2>/dev/null \
    || certbot --nginx -d "$DOMAIN" -d "www.${DOMAIN}" --reinstall --non-interactive --redirect 2>/dev/null \
    || warn "certbot failed — run: sudo certbot --nginx -d ${DOMAIN}"
  nginx -t
  systemctl reload nginx
fi

if curl -sf http://127.0.0.1/api/health >/dev/null; then
  log "Site API via nginx: OK (http://127.0.0.1/api/health)"
else
  warn "nginx proxy to backend failed"
  nginx -t
  journalctl -u nginx -n 20 --no-pager || true
fi

log "Done. Hard-refresh the browser (Ctrl+Shift+R)."
