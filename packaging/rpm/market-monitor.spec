%global appname market-monitor
%global appdir /opt/%{appname}
%global datadir /var/lib/market-monitor
%global debug_package %{nil}

Name:           %{appname}
Version:        1.1.3
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
