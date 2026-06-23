import { useEffect, useState } from "react";
import { api, HistoryRecord, HistoryStats } from "../api";

function statusLabel(status: string): { text: string; className: string } {
  switch (status) {
    case "target_hit":
      return { text: "Target achieved", className: "status-win" };
    case "stop_hit":
      return { text: "Stop loss hit", className: "status-loss" };
    case "expired_win":
      return { text: "Expired — profit", className: "status-win" };
    case "expired_loss":
      return { text: "Expired — loss", className: "status-loss" };
    default:
      return { text: "In progress", className: "status-open" };
  }
}

function fmtPrice(n: number) {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function HistoryPanel() {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.getHistory();
      setRecords(data.signals);
      setStats(data.stats);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return <p style={{ color: "var(--muted)" }}>Loading trade history…</p>;
  }

  return (
    <div className="history-panel">
      <section className="help-section">
        <h2>Short-term trade history</h2>
        <p>
          Every <strong>BUY</strong> or <strong>STRONG BUY</strong> signal is saved here with a clear entry price,
          sell target, and stop loss. We track whether the target was hit within {records[0]?.hold_days ?? 10} days.
        </p>
      </section>

      {stats && (
        <div className="stats-row">
          <div className="stat-card">
            <div className="stat-value">{stats.total_signals}</div>
            <div className="stat-label">Total signals</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.open}</div>
            <div className="stat-label">Open trades</div>
          </div>
          <div className="stat-card stat-win">
            <div className="stat-value">{stats.win_rate}%</div>
            <div className="stat-label">Win rate ({stats.wins}W / {stats.losses}L)</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.avg_result_pct > 0 ? "+" : ""}{stats.avg_result_pct}%</div>
            <div className="stat-label">Avg result (closed)</div>
          </div>
        </div>
      )}

      {records.length === 0 ? (
        <div className="empty-state">
          <h2>No saved signals yet</h2>
          <p>Add stocks to your wishlist. When a BUY signal fires, it will appear here with entry, target, and stop.</p>
        </div>
      ) : (
        <div className="history-list">
          {records.map((r) => {
            const st = statusLabel(r.status);
            const isOpen = r.status === "open";
            return (
              <article key={r.id} className={`history-card ${st.className}`}>
                <div className="history-card-top">
                  <div>
                    <span className="history-symbol">{r.symbol}</span>
                    <span className={`action-pill ${r.action}`}>{r.action.replace("_", " ")}</span>
                    <span className={`history-status ${st.className}`}>{st.text}</span>
                  </div>
                  <time className="scan-info">{new Date(r.created_at).toLocaleString()}</time>
                </div>

                <div className="trade-levels">
                  <div className="trade-level buy-level">
                    <span className="level-label">Buy at</span>
                    <span className="level-price">{fmtPrice(r.entry_price)}</span>
                  </div>
                  <div className="trade-level target-level">
                    <span className="level-label">Sell target</span>
                    <span className="level-price">{fmtPrice(r.sell_target)}</span>
                    <span className="level-pct">+{r.target_pct}%</span>
                  </div>
                  <div className="trade-level stop-level">
                    <span className="level-label">Stop loss</span>
                    <span className="level-price">{fmtPrice(r.stop_loss)}</span>
                    <span className="level-pct">−{r.stop_pct}%</span>
                  </div>
                </div>

                {isOpen && (
                  <div className="history-progress">
                    <span>
                      Current: {r.current_price ? fmtPrice(r.current_price) : "—"}
                      {r.progress_pct != null && (
                        <span className={r.progress_pct >= 0 ? "up" : "down"}>
                          {" "}({r.progress_pct >= 0 ? "+" : ""}{r.progress_pct}%)
                        </span>
                      )}
                    </span>
                    <span className="scan-info">
                      High since: {r.highest_since ? fmtPrice(r.highest_since) : "—"} ·
                      Low since: {r.lowest_since ? fmtPrice(r.lowest_since) : "—"}
                    </span>
                    <span className="scan-info">Expires: {new Date(r.expires_at).toLocaleDateString()}</span>
                  </div>
                )}

                {!isOpen && r.result_pct != null && (
                  <div className={`history-result ${r.result_pct >= 0 ? "up" : "down"}`}>
                    Closed at {r.exit_price ? fmtPrice(r.exit_price) : "—"} →{" "}
                    <strong>{r.result_pct >= 0 ? "+" : ""}{r.result_pct}%</strong>
                    {r.status === "target_hit" && " — we were right, target achieved!"}
                    {r.status === "stop_hit" && " — stop loss triggered."}
                  </div>
                )}

                <p className="history-summary">{r.summary}</p>
              </article>
            );
          })}
        </div>
      )}

      <button className="btn btn-ghost" onClick={load} style={{ marginTop: 16 }}>
        Refresh outcomes
      </button>
    </div>
  );
}
