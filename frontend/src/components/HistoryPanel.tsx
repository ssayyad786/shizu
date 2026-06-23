import { useEffect, useState } from "react";
import { api, currencyForMarket, HistoryRecord, HistoryStats, Market } from "../api";

const MARKETS: { id: Market; label: string }[] = [
  { id: "US", label: "US market" },
  { id: "IN", label: "Indian market" },
];

function statusLabel(record: HistoryRecord): { text: string; className: string } {
  switch (record.status) {
    case "target_hit":
      return { text: "Success — target hit in window", className: "status-win" };
    case "stop_hit":
      return { text: "Stop loss hit", className: "status-loss" };
    case "expired_win":
      return { text: "Window ended — profitable, no target", className: "status-neutral" };
    case "expired_loss":
      return { text: "Window ended — loss", className: "status-loss" };
    default:
      if (record.status === "open" && record.window_open === false) {
        return { text: "Window ended — finalizing", className: "status-neutral" };
      }
      return { text: "In progress", className: "status-open" };
  }
}

function fmtPrice(n: number, market: Market) {
  const sym = currencyForMarket(market);
  return `${sym}${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function HistoryPanel() {
  const [market, setMarket] = useState<Market>("US");
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async (m: Market = market) => {
    setLoading(true);
    try {
      const data = await api.getHistory(m);
      setRecords(data.signals);
      setStats(data.stats);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(market);
  }, [market]);

  const holdDays = records[0]?.hold_days ?? 10;

  return (
    <div className="history-panel">
      <section className="help-section">
        <h2>Short-term trade history</h2>
        <p>
          Every <strong>BUY</strong> or <strong>STRONG BUY</strong> is saved per market with entry,
          sell target, and stop loss. <strong>Success</strong> means the sell target was hit within{" "}
          <strong>{holdDays} calendar days</strong> (shown as window end on each card). Checks start
          from the <strong>next trading day</strong> after the signal.
        </p>
      </section>

      <div className="market-tabs">
        {MARKETS.map((m) => (
          <button
            key={m.id}
            className={`market-tab ${market === m.id ? "active" : ""}`}
            onClick={() => setMarket(m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p style={{ color: "var(--muted)" }}>Loading trade history…</p>
      ) : (
        <>
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
                <div className="stat-label">Target hit rate ({stats.target_hits ?? stats.wins} hits)</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.stop_hits ?? 0}</div>
                <div className="stat-label">Stop losses</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.expired ?? 0}</div>
                <div className="stat-label">Expired (no target)</div>
              </div>
            </div>
          )}

          {records.length === 0 ? (
            <div className="empty-state">
              <h2>No saved signals yet</h2>
              <p>
                Add stocks to your {market === "US" ? "US" : "Indian"} wishlist. When a BUY signal fires,
                it will appear here with entry, target, and stop.
              </p>
            </div>
          ) : (
            <div className="history-list">
              {records.map((r) => {
                const st = statusLabel(r);
                const isOpen = r.status === "open";
                return (
                  <article key={r.id} className={`history-card ${st.className}`}>
                    <div className="history-card-top">
                      <div>
                        <span className="history-symbol">{r.symbol}</span>
                        <span className={`market-pill market-${r.market}`}>{r.market}</span>
                        <span className={`action-pill ${r.action}`}>{r.action.replace("_", " ")}</span>
                        <span className={`history-status ${st.className}`}>{st.text}</span>
                      </div>
                      <time className="scan-info">{new Date(r.created_at).toLocaleString()}</time>
                    </div>

                    <div className="trade-levels">
                      <div className="trade-level buy-level">
                        <span className="level-label">Buy at</span>
                        <span className="level-price">{fmtPrice(r.entry_price, r.market)}</span>
                      </div>
                      <div className="trade-level target-level">
                        <span className="level-label">Sell target</span>
                        <span className="level-price">{fmtPrice(r.sell_target, r.market)}</span>
                        <span className="level-pct">+{r.target_pct}%</span>
                      </div>
                      <div className="trade-level stop-level">
                        <span className="level-label">Stop loss</span>
                        <span className="level-price">{fmtPrice(r.stop_loss, r.market)}</span>
                        <span className="level-pct">−{r.stop_pct}%</span>
                      </div>
                    </div>

                    {isOpen && (
                      <div className="history-progress">
                        <span>
                          Current: {r.current_price ? fmtPrice(r.current_price, r.market) : "—"}
                          {r.progress_pct != null && (
                            <span className={r.progress_pct >= 0 ? "up" : "down"}>
                              {" "}({r.progress_pct >= 0 ? "+" : ""}{r.progress_pct}%)
                            </span>
                          )}
                        </span>
                        <span className="scan-info">
                          High since: {r.highest_since ? fmtPrice(r.highest_since, r.market) : "—"} ·
                          Low since: {r.lowest_since ? fmtPrice(r.lowest_since, r.market) : "—"}
                        </span>
                        <span className="scan-info">
                          Window ends: {new Date(r.expires_at).toLocaleString()}
                          {r.window_open === false && " (ended)"}
                        </span>
                      </div>
                    )}

                    {!isOpen && r.result_pct != null && (
                      <div className={`history-result ${r.success ? "up" : r.result_pct >= 0 ? "" : "down"}`}>
                        Closed at {r.exit_price ? fmtPrice(r.exit_price, r.market) : "—"} →{" "}
                        <strong>{r.result_pct >= 0 ? "+" : ""}{r.result_pct}%</strong>
                        {r.status === "target_hit" && r.days_to_target != null &&
                          ` — target hit on day ${r.days_to_target} (success)`}
                        {r.status === "stop_hit" && " — stop loss triggered."}
                        {r.status.startsWith("expired") && " — target not reached in time."}
                      </div>
                    )}

                    <p className="history-summary">{r.summary}</p>
                  </article>
                );
              })}
            </div>
          )}

          <button className="btn btn-ghost" onClick={() => load()} style={{ marginTop: 16 }}>
            Refresh outcomes
          </button>
        </>
      )}
    </div>
  );
}
