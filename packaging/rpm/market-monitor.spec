%global appname market-monitor
%global appdir /opt/%{appname}
%global datadir /var/lib/market-monitor
%global debug_package %{nil}

Name:           %{appname}
Version:        1.6.0
Release:        1%{?dist}
Summary:        Stock market monitor with technical analysis and trade signals
License:        MIT
URL:            https://github.com/ssayyad786/shizu
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  nodejs
BuildRequires:  npm
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  make

Requires:       python3
Requires:       nginx
Requires:       shadow-utils
Requires:       systemd
Requires:       policycoreutils-python-utils

%description
Market Monitor watches your stock wishlist, runs multi-indicator technical
analysis, suggests short-term buy/sell levels, and tracks signal history.

Persistent data (wishlist, trade history) is stored in %{datadir}/market.db
and is preserved across all upgrades.

%prep
%autosetup -n %{name}-%{version}

%build
cd frontend
npm ci
npm run build

%install
rm -rf %{buildroot}

install -d %{buildroot}%{appdir}/backend
install -d %{buildroot}%{appdir}/frontend
install -d %{buildroot}%{appdir}/scripts
cp -a backend/. %{buildroot}%{appdir}/backend/
cp -a frontend/dist/. %{buildroot}%{appdir}/frontend/
install -m 755 scripts/backup-data.sh %{buildroot}%{appdir}/scripts/backup-data.sh

install -d %{buildroot}%{_sysconfdir}/market-monitor
install -m 644 packaging/rpm/market-monitor.sysconfig %{buildroot}%{_sysconfdir}/market-monitor/config

install -d %{buildroot}%{_libdir}/%{appname}
install -m 755 packaging/rpm/install-python-deps.sh %{buildroot}%{_libdir}/%{appname}/install-python-deps.sh

# Data directory (empty — database created at runtime, never shipped in RPM)
install -d %{buildroot}%{datadir}
install -d %{buildroot}%{datadir}/backups
install -m 644 packaging/rpm/var-lib-README.txt %{buildroot}%{datadir}/README

install -d %{buildroot}%{_unitdir}
install -m 644 packaging/rpm/market-monitor.service %{buildroot}%{_unitdir}/%{appname}.service

install -d %{buildroot}%{_sysconfdir}/nginx/conf.d
install -m 644 packaging/rpm/nginx-market-monitor.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/%{appname}.conf

%pre
getent group market-monitor >/dev/null || groupadd -r market-monitor
getent passwd market-monitor >/dev/null || \
  useradd -r -g market-monitor -d %{datadir} -s /sbin/nologin \
    -c "Market Monitor service user" market-monitor

# Upgrade: backup database before replacing application files ($1=2 upgrade, $1=1 install)
if [ "$1" = "2" ] && [ -f %{datadir}/market.db ]; then
  mkdir -p %{datadir}/backups
  cp -a %{datadir}/market.db %{datadir}/backups/market.db.pre-upgrade-$(date +%%Y%%m%%d-%%H%%M%%S)
  echo "Pre-upgrade backup saved in %{datadir}/backups/"
fi

%post
%{_libdir}/%{appname}/install-python-deps.sh

# Ensure data dir exists and is owned by service user — never delete existing files
mkdir -p %{datadir}/backups
if [ -f %{datadir}/market.db ]; then
  echo "Existing database preserved: %{datadir}/market.db"
fi
chown -R market-monitor:market-monitor %{datadir}
chmod 750 %{datadir}
chmod 750 %{datadir}/backups

semanage port -a -t http_port_t -p tcp 8000 2>/dev/null || semanage port -m -t http_port_t -p tcp 8000 2>/dev/null || true
setsebool -P httpd_can_network_connect 1 2>/dev/null || true

systemctl daemon-reload >/dev/null 2>&1 || :
systemctl enable %{appname}.service nginx >/dev/null 2>&1 || :
systemctl try-restart %{appname}.service nginx >/dev/null 2>&1 || :

%preun
if [ $1 -eq 0 ]; then
  systemctl stop %{appname}.service >/dev/null 2>&1 || :
  systemctl disable %{appname}.service >/dev/null 2>&1 || :
fi

%postun
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl try-restart nginx >/dev/null 2>&1 || :

%files
%defattr(-,root,root,-)
%config(noreplace) %{_sysconfdir}/market-monitor/config
%config(noreplace) %{_sysconfdir}/nginx/conf.d/%{appname}.conf
%{_unitdir}/%{appname}.service
%{_libdir}/%{appname}/install-python-deps.sh
%attr(750,market-monitor,market-monitor) %dir %{datadir}
%attr(750,market-monitor,market-monitor) %dir %{datadir}/backups
%config(noreplace) %attr(644,market-monitor,market-monitor) %{datadir}/README
%{appdir}/backend
%{appdir}/frontend
%{appdir}/scripts/backup-data.sh

%changelog
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.6.0-1
- Redesign intraday engine: ORB + VWAP playbook (15m range, volume, daily filter)
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.12-1
- Intraday history grouped by trade date with Today highlight
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.11-1
- Surgical profit filters from Jul 1 replay; loosen confluence/RVOL for more trades
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.10-1
- Remove train/test dataset export (use algo report + replay backtest instead)
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.9-1
- Intraday profitability filters: daily trend alignment, VWAP chase block, RVOL, RSI, 10AM start
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.8-1
- Intraday replay backtest: pick symbol + date, rerun current logic on historical bars
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.7-1
- Intraday: date-range train/test dataset export (JSON/CSV) for model tuning
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.6-1
- Intraday accuracy: stricter entry filters, wider stops, one trade/symbol/day, no late entries
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.5-1
- Intraday: prominent Download JSON/CSV buttons (top bar + header + history section)
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.4-1
- Intraday: download report (JSON/CSV) with trade history, factor analysis, and tuning insights
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.3-1
- Intraday: scans only during US market hours; countdown banner to close/open
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.5.2-1
- Intraday cards: collapsible rows — click symbol to expand trade details
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.5.1-1
- Intraday: per-trade Why this trade reasons; expanded Help technology section
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.5.0-1
- US Intraday tab: separate watchlist, VWAP/structure model, today trades on top, intraday history
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.4.1-1
- Fix API crash: restore get_cached_signals removed in 1.4.0; non-blocking startup scan
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.4.0-1
- My Holdings tab: sell/hold advice for owned stocks with avg cost and P&L
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.3.1-1
- Purge closed trade cards after 30 days; keep lifetime aggregate stats
* Mon Jun 23 2025 Shizu <admin@localhost> - 1.3.0-1
- History pagination (30/page), SQL stats, deduped quotes for open trades
* Mon Jun 23 2025 Shizu <admin@localhost> - 1.2.9-1
- History tab: silent background refresh (no loading flash), faster API
* Mon Jun 23 2025 Shizu <admin@localhost> - 1.2.8-1
- Fix history target detection: timezone-safe dates and live price before daily bars
* Mon Jun 23 2025 Shizu <admin@localhost> - 1.2.7-1
- Fix history target detection with live price; show company names on history cards
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.2.6-1
- Dynamic trading-day window (1-10); issue target only if achievable within 10 sessions
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.2.5-1
- Auto-fetch company names for wishlist symbols added without search pick
* Tue Jun 24 2026 Shizu <admin@localhost> - 1.2.4-1
- Market signal box shows why HOLD/BUY/SELL and upper/lower price targets
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.2.3-1
- Bulk import skips existing symbols and adds the rest without failing
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.2.2-1
- Unified wishlist input: paste comma-separated symbol lists in one field
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.2.1-1
- Fix mobile toolbar: always show US/India market switch and layout toggle
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.2.0-1
- Bulk wishlist import (comma-separated symbols) and mobile/desktop layout toggle
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.1.4-1
- Fix wishlist not showing due to cached API responses missing market field
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.1.3-1
- Fix India/US market tab switching and stock selection in dashboard
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.1.2-1
- Fix wishlist DB migration for dual US/IN markets (legacy unique index)
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.1.1-1
- Add scripts/upgrade.sh for safe one-command deploys and HTTPS restore
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.1.0-1
- Dual US/Indian wishlists, per-market history, version footer and disclaimer
* Mon Jun 23 2026 Shizu <admin@localhost> - 1.0.0-1
- Initial RPM release; persistent data in /var/lib/market-monitor
