# Shizu — Stock Market Monitor

> **Disclaimer:** Educational and monitoring use only. Not financial advice.

---

## Application status (read this first)

| Item | Status |
|------|--------|
| **Version** | 1.1.1 |
| **Purpose** | Short-term stock monitoring, buy signals, sell targets, outcome tracking |
| **UI** | Light theme · React + Vite |
| **Backend** | FastAPI · Python 3.11+ · SQLite |
| **Market data** | Yahoo Finance (`yfinance`) — free, no API key |
| **Auto-scan** | Every 5 minutes (both US + Indian wishlists) |
| **Hold period** | 1–10 trading days (estimated); no target if not achievable in 10 sessions |
| **Production deploy** | GCP VM → `sudo bash scripts/setup-gcp-instance.sh` |
| **Package name (RPM)** | `market-monitor` |
| **Repo** | https://github.com/ssayyad786/shizu |

### UI tabs

| Tab | What it does |
|-----|----------------|
| **Dashboard** | Live signals, buy opportunities (with entry/target/stop), stock table, click stock → charts |
| **Wishlists** | Separate **US** and **Indian** lists (`.NS` / `.BO` for India) |
| **Hold window** | **1–10 trading days** (estimated per signal); target only if achievable in window |
| **Help** | Indicator guide, trade plan explanation, signal meanings |

### Sidebar

- Add stocks by **name or symbol** (autocomplete, e.g. "Microsoft" → MSFT)
- Wishlist — click any stock for detail view
- US stocks: `AAPL`, `TSLA` · India: `RELIANCE.NS`, `TCS.NS`

### What happens on a BUY signal

1. Score ≥ 0.20 → **BUY** or **STRONG BUY** shown on dashboard  
2. Trade plan calculated (ATR-based): **buy price**, **sell target**, **stop loss**  
3. Signal **saved to History** only if target is achievable within estimated trading days (max 10 weekdays)  
4. **Success** only if sell target is hit on a bar **before that expiry time** (day-by-day check)  
4. Outcomes tracked: `target_hit` · `stop_hit` · `expired_win` · `expired_loss` · `open`

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, lightweight-charts |
| Backend | FastAPI, SQLAlchemy, APScheduler |
| Indicators | `ta` library (RSI, MACD, EMA, Bollinger, Stochastic, ADX, ATR) |
| Database | SQLite |
| Server (prod) | nginx (port 80) + systemd (`market-monitor.service`) |
| Packaging | RPM for Rocky/Alma/RHEL 9 |

---

## Algorithm

Seven indicators combined into a weighted score (−1 to +1):

| Indicator | Weight | Role |
|-----------|--------|------|
| MACD | 18% | Momentum crossovers |
| EMA 9/21 | 18% | Short-term trend (golden/death cross) |
| RSI (14) | 14% | Overbought / oversold |
| Stochastic | 14% | Short-term momentum |
| Bollinger Bands | 12% | Mean reversion at bands |
| Volume | 12% | Confirms price moves |
| ADX | 12% | Trend strength filter |

| Score | Signal | Action |
|-------|--------|--------|
| ≥ 0.45 | STRONG BUY | Target = entry + **2× ATR** |
| ≥ 0.20 | BUY | Target = entry + **1.5× ATR** · saved to History |
| −0.20 to 0.20 | HOLD | No trade |
| ≤ −0.20 | SELL | Bearish caution |
| ≤ −0.45 | STRONG SELL | Strong bearish |

**Stop loss:** entry − **1× ATR** for all buy signals.

### Charts (stock detail)

| Panel | Shows |
|-------|--------|
| Price | Candlesticks, EMA 9/21, Bollinger Bands + legend |
| RSI | Orange line, 30/70 zones |
| MACD | Blue/orange lines + histogram |
| Volume | Green/red bars |

---

## Data persistence (safe upgrades)

| What | Server path | Local dev |
|------|-------------|-----------|
| Database | `/var/lib/market-monitor/market.db` | `./backend/market.db` |
| Backups | `/var/lib/market-monitor/backups/` | — |
| Config | `/etc/market-monitor/config` | env `MARKET_DATA_DIR` |
| App code | `/opt/market-monitor/` | repo folder |

- **Upgrades never delete data** — only `/opt/market-monitor/` is replaced  
- Auto-backup before each RPM upgrade  
- Verify: `curl -s http://localhost/api/health`

```bash
# Manual backup (server)
sudo /opt/market-monitor/scripts/backup-data.sh
```

---

## Deploy on GCP

**First time?** Follow **[first_time_setup.md](first_time_setup.md)** — full step-by-step (VM, clone, install, HTTPS, troubleshooting).

### Option A — Always Free (e2-micro, $0/month)

GCP only gives a **free VM in US regions**, not Mumbai. Change these settings in the Create Instance screen:

| Setting | Your screenshot (paid) | Free tier (change to) |
|---------|------------------------|------------------------|
| **Region** | asia-south1 (Mumbai) | **us-central1** (Iowa) or us-west1 / us-east1 |
| **Zone** | asia-south1-b | any zone in that region (e.g. us-central1-a) |
| **Machine type** | e2-medium (2 vCPU, 4 GB) | **e2-micro** (2 vCPU, 1 GB RAM) |
| **Boot disk** | 10 GB balanced | **30 GB Standard persistent disk** (pd-standard) |
| **Preemptible** | Off | **Off** (must stay off) |

**OS:** Rocky Linux 9 or AlmaLinux 9 (for RPM setup script). Debian also works with Docker.

**Networking:** check **Allow HTTP traffic** (opens port 80).

**Monthly estimate** should show **$0.00** (or only tiny egress if you exceed 1 GB/month).

> **Trade-off:** Mumbai = lower latency to India but **not free**. US region = **free forever** but slightly higher latency for Indian market data (usually fine).

**1 GB RAM tip:** add swap before install (RPM build needs memory):

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Then install Shizu:

```bash
git clone https://github.com/ssayyad786/shizu.git
cd shizu
sudo bash scripts/setup-gcp-instance.sh
```

**Alternative:** use **$300 free trial** (90 days) to run e2-medium in Mumbai — paid after trial ends unless you resize/move to e2-micro US.

---

### Option B — Standard deploy (paid, any region)

**OS:** Rocky Linux 9 or AlmaLinux 9 · **Machine:** e2-small or e2-medium · **Region:** asia-south1 OK

```bash
git clone https://github.com/ssayyad786/shizu.git
cd shizu
sudo bash scripts/setup-gcp-instance.sh
```

Opens port 80, builds RPM, installs, starts nginx + API.  
→ **http://YOUR_VM_EXTERNAL_IP/**

| Script | Purpose |
|--------|---------|
| **[first_time_setup.md](first_time_setup.md)** | **Complete first-time guide (start here)** |
| `scripts/setup-gcp-instance.sh` | First-time install on VM |
| `scripts/upgrade.sh` | **Recommended** — pull, build, install, restore HTTPS |
| `scripts/gcp-startup-script.sh` | GCP VM startup automation (optional) |
| `scripts/backup-data.sh` | Manual database backup |
| `packaging/rpm/build-rpm.sh` | Build RPM only |

**Upgrade:** `git pull && sudo bash scripts/setup-gcp-instance.sh`

Details: [packaging/rpm/DEPLOY.md](packaging/rpm/DEPLOY.md)

---

## Local development (Windows)

```powershell
# Terminal 1 — Backend (port 8001)
cd backend
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001

# Terminal 2 — Frontend (port 5173)
cd frontend
npm install
npm run dev
```

→ **http://localhost:5173** (proxies `/api` → port 8001)

Or run `start.bat`.

**Note:** PowerShell may block `venv\Scripts\activate` — use `.\venv\Scripts\python.exe` directly.

---

## Docker (alternative)

```bash
docker compose up -d --build
```

- UI: http://localhost:3000  
- API: http://localhost:8000/api/health

---

## Operations (production server)

```bash
# Service status
sudo systemctl status market-monitor nginx

# Logs
sudo journalctl -u market-monitor -f

# Restart
sudo systemctl restart market-monitor nginx

# Health + data paths
curl -s http://localhost/api/health | python3 -m json.tool
```

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Status + `data_dir` + `database` path |
| GET | `/api/wishlist?market=US\|IN` | List wishlist (optional market filter) |
| POST | `/api/wishlist` | Add symbol `{ "symbol": "AAPL", "market": "US", "name": "..." }` |
| DELETE | `/api/wishlist/{symbol}?market=US` | Remove from wishlist |
| GET | `/api/history?market=US\|IN` | Trade history + stats per market |
| GET | `/api/search?q=` | Stock name/symbol autocomplete |
| GET | `/api/signals` | Cached signals + buy opportunities |
| POST | `/api/scan` | Scan wishlist now |
| GET | `/api/history` | Saved trades + stats + outcomes |
| POST | `/api/history/refresh` | Re-check open trade outcomes |
| GET | `/api/stocks/{symbol}` | Quote, signal, trade plan, candles, indicators |
| GET | `/api/stocks/{symbol}/quote` | Quick quote |
| POST | `/api/stocks/{symbol}/scan` | Scan single symbol |

---

## Project structure

```
shizu/
├── backend/
│   ├── main.py                 # FastAPI entry, scheduler (5 min scan)
│   ├── requirements.txt
│   └── app/
│       ├── database.py         # SQLite path (MARKET_DATA_DIR)
│       ├── models.py             # WishlistItem, SignalHistory
│       ├── routes/               # wishlist, stocks, history
│       └── services/
│           ├── signals.py        # 7-indicator engine + ATR trade plan
│           ├── history.py        # Save signals, track outcomes
│           ├── monitor.py        # Wishlist scanner
│           ├── market_data.py    # yfinance fetch
│           └── search.py         # Yahoo symbol search
├── frontend/
│   └── src/
│       ├── App.tsx               # Dashboard / History / Help tabs
│       └── components/           # Charts, search, panels
├── packaging/rpm/                # RPM spec, nginx, systemd
├── scripts/
│   ├── setup-gcp-instance.sh     # One-command GCP deploy
│   ├── backup-data.sh
│   └── gcp-startup-script.sh
├── docker-compose.yml
├── start.bat                     # Windows local launcher
└── README.md                     # ← this file (keep updated)
```

---

## Maintainer notes

**Update this README whenever you change:**

- New UI tab or feature → **Application status** + **Project structure**
- New indicator or scoring rule → **Algorithm**
- New API route → **API reference**
- New deploy or setup step → **first_time_setup.md** + **Deploy on GCP**
- Version bump → **Application status** table + `packaging/rpm/market-monitor.spec`

---

## License

MIT
