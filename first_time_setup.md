# Shizu — First-Time Setup Guide

Complete steps to deploy Shizu on a **new GCP VM** from zero to a working app.  
Follow in order. Total time: ~30–45 minutes (mostly waiting for install).

---

## What you get

| Item | Value |
|------|--------|
| App URL | `http://YOUR_VM_IP/` (later `https://shizu.co.in`) |
| API | Proxied at `/api/` via nginx |
| Data (never lost on upgrade) | `/var/lib/market-monitor/market.db` |
| Backups | `/var/lib/market-monitor/backups/` |
| App code | `/opt/market-monitor/` |

---

## Part 1 — Create GCP VM (Console)

### 1.1 Machine configuration

| Setting | Choose |
|---------|--------|
| **Name** | e.g. `server-1` |
| **Region** | **us-central1** (Iowa) — required for **free tier** |
| **Zone** | Any, e.g. `us-central1-a` |
| **Machine type** | **e2-micro** (2 vCPU, 1 GB RAM) |
| **Series** | E2 |

> **Do not use** `asia-south1` (Mumbai) if you want **$0/month** Always Free. Mumbai works but costs ~$6–30/month.

### 1.2 OS and storage

| Setting | Choose |
|---------|--------|
| **OS** | **Rocky Linux 10** (or AlmaLinux 9/10) |
| **Boot disk type** | **Standard persistent disk** (not Balanced) |
| **Size** | 20–30 GB |
| **Hostname** | Leave **empty** |

> **Do not use Debian** if you want the one-command RPM install. Debian needs Docker instead.

### 1.3 Networking → Firewall

Check both:

- [x] **Allow HTTP traffic**
- [x] **Allow HTTPS traffic** (for SSL later)

Leave unchecked:

- [ ] Allow Load Balancer Health Checks
- [ ] IP forwarding
- [ ] Tier_1 networking

### 1.4 Monthly estimate

- May show **~$6** for e2-micro in the UI — **Always Free** is applied on the **bill** for eligible accounts.
- Disk should show **$0** for standard disk.

### 1.5 Create

Click **Create**. Wait until status is **Running**.

Note your **External IP** (VM details page), e.g. `34.173.172.237`.

---

## Part 2 — Connect via SSH

1. GCP Console → **Compute Engine** → **VM instances**
2. Click **SSH** next to your VM
3. You get a browser terminal (or use `gcloud compute ssh`)

---

## Part 3 — Prepare the VM (swap + tools)

Run as root (`sudo su -`) or with `sudo`.

```bash
# --- Swap (required on 1 GB RAM for npm/RPM build) ---
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
free -h
# Should show Swap: 2.0Gi
```

---

## Part 4 — Clone and install Shizu

```bash
cd ~
rm -rf shizu   # only if re-installing

git clone https://github.com/ssayyad786/shizu.git
cd shizu

# Rocky Linux 10 fix (skip if already in repo — grep checks for you)
grep -q 'debug_package' packaging/rpm/market-monitor.spec || \
  sed -i '/%global datadir/a %global debug_package %{nil}' packaging/rpm/market-monitor.spec

# Full install (10–20 min — do not close SSH)
sudo bash scripts/setup-gcp-instance.sh
```

### What the install script does

1. Installs `dnf` packages (nginx, python, node, rpm-build, git, …)
2. Opens firewall port 80
3. Builds frontend (`npm run build`)
4. Builds and installs RPM → `/opt/market-monitor/`
5. Creates Python venv + pip dependencies
6. Starts **nginx** + **market-monitor** systemd services

### Success message

You should see:

```
==============================================
  Shizu Market Monitor is installed!
==============================================
  Public:   http://YOUR_VM_IP/
```

---

## Part 5 — Verify

```bash
curl http://127.0.0.1/api/health
```

Expected:

```json
{"status":"ok","data_dir":"/var/lib/market-monitor","database":"/var/lib/market-monitor/market.db"}
```

```bash
systemctl status nginx market-monitor --no-pager
ls /opt/market-monitor/frontend/index.html
```

Open in browser: **http://YOUR_EXTERNAL_IP/**

---

## Part 6 — Use the app

1. Sidebar → type stock name (e.g. `Microsoft`) → pick **MSFT** → **Add**
2. Click **Scan now** (or wait 5 min auto-scan)
3. **Dashboard** — live signals and buy opportunities
4. **History** — saved trades with sell target / stop loss
5. **Help** — indicator guide

### Stock symbol examples

| Market | Examples |
|--------|----------|
| US | `AAPL`, `MSFT`, `TSLA` |
| India | `RELIANCE.NS`, `TCS.NS`, `INFY.NS` |

---

## Part 7 — Static IP + domain (shizu.space) + HTTPS

### Why static IP?

GCP gives your VM a **temporary (ephemeral) IP** by default. If you **Stop** then **Start** the VM, that IP **changes** and your domain breaks.

**Fix:** Reserve a **Static external IP** once — then stop/start works with no extra steps.

> Static IPs are **free while attached** to a running VM. If you reserve one but leave it unused, GCP may charge a small fee.

---

### 7.1 Reserve static IP (GCP Console) — do this first

1. **VPC network** → **IP addresses** → **RESERVE EXTERNAL STATIC IP**
2. **Name:** `shizu-static-ip`
3. **Network service tier:** Premium
4. **IP version:** IPv4
5. **Type:** Regional
6. **Region:** **us-central1** (same as your VM)
7. **Attached to:** select your VM `server-1`
8. Click **Reserve**

Note the IP (e.g. `34.173.172.237`) — this IP **never changes** on stop/start.

**Or attach to existing VM:**  
VM instances → `server-1` → **Edit** → **Network interfaces** → External IPv4 → **Static** → select `shizu-static-ip` → **Save**.

---

### 7.2 DNS at your registrar (GoDaddy / etc.)

For **shizu.space**:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| **A** | `@` | Your **static** IP | 600 (or default) |
| **A** | `www` | Same static IP | 600 |

Remove old A records pointing to a different IP.

Wait 5–30 minutes. Test:

```bash
ping shizu.space
# or
nslookup shizu.space
```

---

### 7.3 HTTPS on VM (free SSL)

SSH into server, then:

```bash
# Rocky Linux 10: certbot is in EPEL, not base repos
sudo dnf install -y epel-release
sudo dnf install -y certbot python3-certbot-nginx

sudo certbot --nginx -d shizu.space -d www.shizu.space
```

- Enter email when asked
- Agree to terms
- Choose redirect HTTP → HTTPS (recommended)

Test: **https://shizu.space/**

Auto-renewal is enabled. Check:

```bash
sudo certbot renew --dry-run
```

---

### 7.4 Stop / Start VM (no extra work)

After static IP is attached:

| Action | What happens |
|--------|----------------|
| **Stop** instance | VM shuts down, **IP stays** reserved |
| **Start** instance | Same IP, Shizu starts automatically (systemd) |
| **Reboot** | Same IP, services restart |

You do **not** need to change DNS or run certbot again on VM stop/start.

> **After `git pull` + RPM upgrade:** If HTTPS stops working but HTTP still works, the nginx SSL config was reset. Re-run certbot (section 7.3) — certificates are still on disk.

Verify after start:

```bash
sudo systemctl status nginx market-monitor
curl -s http://127.0.0.1/api/health
```

---

### 7.5 If domain still shows old IP

1. Confirm static IP on VM details page in GCP
2. Confirm DNS A record matches that IP
3. Clear browser cache or try incognito
4. DNS can take up to 48h (usually minutes)

---

## Part 8 — Useful commands

```bash
# Service status
sudo systemctl status nginx market-monitor

# Logs
sudo journalctl -u market-monitor -f
sudo journalctl -u nginx -f

# Restart
sudo systemctl restart market-monitor nginx

# Backup database
sudo /opt/market-monitor/scripts/backup-data.sh

# Upgrade after git pull
cd ~/shizu && git pull && sudo bash scripts/setup-gcp-instance.sh
```

---

## Part 9 — Troubleshooting

### Browser: "Connection timed out"

| Cause | Fix |
|-------|-----|
| App not installed | Run `sudo bash scripts/setup-gcp-instance.sh` |
| Services stopped | `sudo systemctl start nginx market-monitor` |
| HTTP not allowed in GCP | VM → Edit → Firewall → Allow HTTP traffic |

### `App not installed yet` / no `/opt/market-monitor/`

Install did not finish. Re-run:

```bash
cd ~/shizu
sudo bash scripts/setup-gcp-instance.sh
```

### RPM build failed: `Empty %files file debugsourcefiles.list`

Rocky Linux 10 only. Fix spec file:

```bash
sed -i '/%global datadir/a %global debug_package %{nil}' packaging/rpm/market-monitor.spec
```

Then re-run setup script. (Already in latest GitHub repo.)

### `market-monitor` not found after install

```bash
sudo /usr/lib64/market-monitor/install-python-deps.sh
sudo systemctl enable --now market-monitor nginx
```

### npm / out of memory during build

Ensure 2 GB swap is active: `free -h`

### nginx warning: `conflicting server name "_"`

Harmless. To remove warning:

```bash
sudo rm -f /etc/nginx/conf.d/default.conf 2>/dev/null
sudo nginx -t && sudo systemctl reload nginx
```

### API health check failed at end of install

Wait 10 seconds and run:

```bash
curl http://127.0.0.1/api/health
```

Often the API was still starting.

---

## Part 10 — VM diagnostic (paste to support)

If stuck, run and share output:

```bash
echo "=== SERVICES ==="
systemctl status nginx --no-pager 2>&1 | head -15
systemctl status market-monitor --no-pager 2>&1 | head -15
echo "=== PORTS ==="
ss -tlnp | grep -E ':80|:8000' || echo "Nothing on 80 or 8000"
echo "=== HEALTH ==="
curl -s http://127.0.0.1/api/health
echo "=== INSTALLED? ==="
ls -la /opt/market-monitor/frontend/index.html 2>&1
echo "=== EXTERNAL IP ==="
curl -s -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip
```

---

## Quick reference — one block (experienced users)

```bash
# On new Rocky 10 VM in us-central1, e2-micro, HTTP+HTTPS enabled:
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
git clone https://github.com/ssayyad786/shizu.git && cd shizu
grep -q debug_package packaging/rpm/market-monitor.spec || sed -i '/%global datadir/a %global debug_package %{nil}' packaging/rpm/market-monitor.spec
sudo bash scripts/setup-gcp-instance.sh
curl http://127.0.0.1/api/health
# Open http://YOUR_VM_IP/
```

---

## Cost summary

| Item | Cost |
|------|------|
| GCP e2-micro (us-central1) | **$0** (Always Free tier) |
| Standard disk ≤30 GB | **$0** |
| HTTPS (Let's Encrypt) | **$0** |
| Domain shizu.co.in | ~₹99 year 1, then renewal yearly |

---

## Related files

| File | Purpose |
|------|---------|
| [README.md](README.md) | App status, features, API |
| [packaging/rpm/DEPLOY.md](packaging/rpm/DEPLOY.md) | RPM / data paths |
| [scripts/setup-gcp-instance.sh](scripts/setup-gcp-instance.sh) | Automated install |
| [scripts/backup-data.sh](scripts/backup-data.sh) | Manual DB backup |

---

*Last updated: June 2026 — Rocky Linux 10.2, Shizu 1.0.0, GCP e2-micro us-central1, domain shizu.space.*
