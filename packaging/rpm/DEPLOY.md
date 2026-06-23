# Deploy Shizu on GCP

## Easiest: one setup script

```bash
git clone https://github.com/ssayyad786/shizu.git
cd shizu
sudo bash scripts/setup-gcp-instance.sh
```

Done. Open `http://YOUR_VM_IP/`

## What the setup script does

1. Installs `dnf` packages (nginx, python3, nodejs, rpm-build, …)
2. Opens firewall port 80
3. Builds RPM from this repo
4. Installs RPM → `/opt/market-monitor/`
5. Enables `market-monitor` + `nginx` systemd services
6. Prints public URL (from GCP metadata when available)

## GCP firewall

Ensure port **80** is open:

- VM creation: check **Allow HTTP traffic**, or
- Firewall rule: `tcp:80` to VMs with tag `http-server`

```bash
gcloud compute firewall-rules create allow-http \
  --allow tcp:80 --target-tags=http-server
```

Data in `/var/lib/market-monitor/` is **never removed** on upgrade. A backup is taken automatically before each install.

## Data locations

| Path | Purpose |
|------|---------|
| `/var/lib/market-monitor/market.db` | Wishlist + trade signal history |
| `/var/lib/market-monitor/backups/` | Auto backups before upgrades |
| `/etc/market-monitor/config` | `MARKET_DATA_DIR` and settings |

```bash
# Verify paths
curl -s http://localhost/api/health | python3 -m json.tool

# Manual backup
sudo /opt/market-monitor/scripts/backup-data.sh
```

## Upgrade after `git pull`

```bash
cd shizu
sudo bash scripts/setup-gcp-instance.sh
```

Data in `/var/lib/market-monitor/` is preserved.

## Manual RPM only

```bash
./packaging/rpm/build-rpm.sh
sudo dnf install -y ~/rpmbuild/RPMS/x86_64/market-monitor-*.rpm
```

## Logs & config

```bash
sudo journalctl -u market-monitor -f
cat /etc/market-monitor/config
```

## Architecture

```
Browser → nginx:80 → /opt/market-monitor/frontend
                  └→ /api/* → 127.0.0.1:8000 (systemd)
                                    └→ /var/lib/market-monitor/market.db
```
