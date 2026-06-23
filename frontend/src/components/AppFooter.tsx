import { useEffect, useState } from "react";

const BUILD_VERSION = "1.1.2";

export default function AppFooter() {
  const [version, setVersion] = useState(BUILD_VERSION);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.version) setVersion(data.version);
      })
      .catch(() => {
        /* use build version */
      });
  }, []);

  return (
    <footer className="app-footer">
      <p className="app-footer-disclaimer">
        <strong>For learning and research only.</strong> Shizu is not a trading platform and does not
        provide financial advice. Signals are automated estimates based on public market data — always
        do your own research before making investment decisions.
      </p>
      <p className="app-footer-meta">
        Shizu Market Monitor · Version {version}
      </p>
    </footer>
  );
}
