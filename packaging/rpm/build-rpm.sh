#!/bin/bash
# Build market-monitor RPM on a RHEL-family Linux VM (Rocky, Alma, RHEL, CentOS Stream).
#
# Usage:
#   cd /path/to/shizu
#   ./packaging/rpm/build-rpm.sh
#
# Output:
#   ~/rpmbuild/RPMS/x86_64/market-monitor-<version>-1.*.rpm

set -euo pipefail

NAME="market-monitor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION_FILE="$PROJECT_ROOT/backend/app/version.py"
SPEC_FILE="$SCRIPT_DIR/market-monitor.spec"

VERSION=$(awk -F'"' '/^__version__/ {print $2; exit}' "$VERSION_FILE")
SPEC_VERSION=$(awk '/^Version:/ {print $2; exit}' "$SPEC_FILE")

if [[ -z "$VERSION" ]]; then
  echo "ERROR: Could not read version from $VERSION_FILE" >&2
  exit 1
fi

if [[ "$VERSION" != "$SPEC_VERSION" ]]; then
  echo "ERROR: version.py ($VERSION) does not match market-monitor.spec ($SPEC_VERSION)" >&2
  echo "Update both files to the same version before building." >&2
  exit 1
fi

echo "==> Project root: $PROJECT_ROOT"
echo "==> Version: $VERSION"

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

# Rename tarball root to match spec expectation (market-monitor-<version>/)
TMPDIR=$(mktemp -d)
tar -xzf "$TARBALL" -C "$TMPDIR"
INNER=$(ls "$TMPDIR")
mv "$TMPDIR/$INNER" "$TMPDIR/${NAME}-${VERSION}"
tar -czf "$TARBALL" -C "$TMPDIR" "${NAME}-${VERSION}"
rm -rf "$TMPDIR"

cp "$SPEC_FILE" ~/rpmbuild/SPECS/

echo "==> Building RPM..."
rpmbuild -ba ~/rpmbuild/SPECS/market-monitor.spec

echo ""
echo "==> Done! Install with:"
RPM_FILE=$(ls ~/rpmbuild/RPMS/*/${NAME}-${VERSION}*.rpm | head -1)
echo "    sudo dnf install -y $RPM_FILE"
echo ""
echo "    Then open: http://YOUR_VM_IP/"
