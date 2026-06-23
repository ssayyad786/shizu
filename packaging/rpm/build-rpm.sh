#!/bin/bash
# Build market-monitor RPM on a RHEL-family Linux VM (Rocky, Alma, RHEL, CentOS Stream).
#
# Usage:
#   cd /path/to/market
#   ./packaging/rpm/build-rpm.sh
#
# Output:
#   ~/rpmbuild/RPMS/x86_64/market-monitor-1.0.0-1.*.rpm

set -euo pipefail

NAME="market-monitor"
VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "==> Project root: $PROJECT_ROOT"

# Install build dependencies (Rocky/Alma/RHEL)
if command -v dnf &>/dev/null; then
  echo "==> Installing build dependencies..."
  sudo dnf install -y rpm-build rpmdevtools nodejs npm python3 python3-pip gcc gcc-c++ make \
    nginx policycoreutils-python-utils 2>/dev/null || true
fi

# RPM tree
mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

TARBALL="$HOME/rpmbuild/SOURCES/${NAME}-${VERSION}.tar.gz"
echo "==> Creating source tarball..."
tar -czf "$TARBALL" \
  --exclude='node_modules' \
  --exclude='frontend/node_modules' \
  --exclude='backend/venv' \
  --exclude='backend/__pycache__' \
  --exclude='backend/**/__pycache__' \
  --exclude='backend/*.db' \
  --exclude='.git' \
  --exclude='frontend/dist' \
  -C "$PROJECT_ROOT/.." \
  "$(basename "$PROJECT_ROOT")"

# Rename tarball root to match spec expectation (market-monitor-1.0.0/)
# The spec uses %autosetup -n market-monitor-1.0.0 but our folder may be named 'market'
TMPDIR=$(mktemp -d)
tar -xzf "$TARBALL" -C "$TMPDIR"
INNER=$(ls "$TMPDIR")
mv "$TMPDIR/$INNER" "$TMPDIR/${NAME}-${VERSION}"
tar -czf "$TARBALL" -C "$TMPDIR" "${NAME}-${VERSION}"
rm -rf "$TMPDIR"

cp "$SCRIPT_DIR/market-monitor.spec" ~/rpmbuild/SPECS/

echo "==> Building RPM..."
rpmbuild -ba ~/rpmbuild/SPECS/market-monitor.spec

echo ""
echo "==> Done! Install with:"
RPM_FILE=$(ls ~/rpmbuild/RPMS/*/${NAME}-${VERSION}*.rpm | head -1)
echo "    sudo dnf install -y $RPM_FILE"
echo ""
echo "    Then open: http://YOUR_VM_IP/"
