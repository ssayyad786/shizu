import { useCallback, useEffect, useState } from "react";
import {
  api,
  IntradayHistoryRecord,
  IntradayLiveSignal,
  IntradayStats,
  IntradayWatchlistItem,
} from "../api";
import WishlistAdd from "./WishlistAdd";
import WhyTradeBlock from "./WhyTradeBlock";

function fmt(n: number) {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function statusLabel(record: IntradayHistoryRecord) {
  switch (record.status) {
    case "target_hit":
      return { text: "Target 1 hit", className: "status-win" };
    case "target_2_hit":
      return { text: "Target 2 hit", className: "status-win" };
    case "stop_hit":
      return { text: "Stop hit", className: "status-loss" };
    case "expired_win":
      return { text: "Session end — profit", className: "status-neutral" };
    case "expired_loss":
      return { text: "Session end — loss", className: "status-loss" };
    default:
      return { text: "Active — place order", className: "status-open" };
  }
}

function SetupCard({ signal }: { signal: IntradayLiveSignal }) {
  const plan = signal.trade_plan;
  const isLong = signal.direction === "LONG";
  return (
    <article className={`intraday-setup-card ${isLong ? "long" : "short"}`}>
      <header className="intraday-setup-header">
        <div>
          <div className="intraday-symbol">{signal.symbol}</div>
          <div className="intraday-direction">
            {signal.direction} · {signal.confidence}% confidence
          </div>
        </div>
        <span className="intraday-badge-today">Today</span>
      </header>
      {plan && (
        <div className="intraday-levels">
          <div><span>Entry</span><strong>{fmt(plan.entry_price)}</strong></div>
          <div className="target-text"><span>T1</span><strong>{fmt(plan.target_1)} (+{plan.target_1_pct}%)</strong></div>
          <div className="target-text"><span>T2</span><strong>{fmt(plan.target_2)} (+{plan.target_2_pct}%)</strong></div>
          <div className="stop-text"><span>Stop</span><strong>{fmt(plan.stop_loss)} (−{plan.stop_pct}%)</strong></div>
          <div><span>R:R</span><strong>{plan.risk_reward}:1</strong></div>
          <div><span>Hold</span><strong>~{plan.hold_minutes} min</strong></div>
        </div>
      )}
      {signal.vwap != null && (
        <p className="intraday-meta">VWAP {fmt(signal.vwap)} · RVOL {signal.rvol ?? "—"}× · Daily {signal.daily_trend}</p>
      )}
      <p className="intraday-summary">{signal.summary}</p>
      <WhyTradeBlock
        headline={signal.why_headline}
        reasons={signal.trade_reasons}
        fallbackBullets={signal.reasoning}
      />
    </article>
  );
}

function TradeCard({ record }: { record: IntradayHistoryRecord }) {
  const st = statusLabel(record);
  const isLong = record.direction === "LONG";
  return (
    <article className={`intraday-trade-card ${st.className} ${isLong ? "long" : "short"}`}>
      <header>
        <div className="intraday-symbol">{record.symbol}</div>
        {record.name && <div className="intraday-name">{record.name}</div>}
      </header>
      <div className={`intraday-status ${st.className}`}>{st.text}</div>
      <div className="intraday-levels compact">
        <div><span>{record.direction}</span><strong>{fmt(record.entry_price)}</strong></div>
        <div><span>T1</span><strong>{fmt(record.target_1)}</strong></div>
        <div><span>Stop</span><strong>{fmt(record.stop_loss)}</strong></div>
        {record.current_price != null && (
          <div><span>Now</span><strong>{fmt(record.current_price)}</strong></div>
        )}
        {record.progress_pct != null && record.status === "open" && (
          <div><span>P&amp;L</span><strong className={record.progress_pct >= 0 ? "pnl-up" : "pnl-down"}>
            {record.progress_pct > 0 ? "+" : ""}{record.progress_pct}%
          </strong></div>
        )}
        {record.result_pct != null && record.status !== "open" && (
          <div><span>Result</span><strong className={record.result_pct >= 0 ? "pnl-up" : "pnl-down"}>
            {record.result_pct > 0 ? "+" : ""}{record.result_pct}%
          </strong></div>
        )}
      </div>
      <WhyTradeBlock
        headline={record.why_headline}
        reasons={record.trade_reasons}
        fallbackBullets={record.reasoning}
      />
    </article>
  );
}

function StatsBar({ stats }: { stats: IntradayStats }) {
  return (
    <div className="intraday-stats">
      <div className="intraday-stat"><span>All-time win rate</span><strong>{stats.win_rate}%</strong></div>
      <div className="intraday-stat"><span>Closed</span><strong>{stats.closed}</strong></div>
      <div className="intraday-stat"><span>Avg result</span><strong>{stats.avg_result_pct > 0 ? "+" : ""}{stats.avg_result_pct}%</strong></div>
      <div className="intraday-stat"><span>Today</span><strong>{stats.today_wins}/{stats.today_closed} wins</strong></div>
      <div className="intraday-stat"><span>Open</span><strong>{stats.open}</strong></div>
    </div>
  );
}

export default function IntradayPanel() {
  const [watchlist, setWatchlist] = useState<IntradayWatchlistItem[]>([]);
  const [signals, setSignals] = useState<IntradayLiveSignal[]>([]);
  const [todaySetups, setTodaySetups] = useState<IntradayLiveSignal[]>([]);
  const [todayTrades, setTodayTrades] = useState<IntradayHistoryRecord[]>([]);
  const [history, setHistory] = useState<IntradayHistoryRecord[]>([]);
  const [stats, setStats] = useState<IntradayStats | null>(null);
  const [lastScan, setLastScan] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [wl, sig, hist] = await Promise.all([
        api.getIntradayWatchlist(),
        api.getIntradaySignals(),
        api.getIntradayHistory({ refresh: true }),
      ]);
      setWatchlist(wl);
      setSignals(sig.signals);
      setTodaySetups(sig.today_setups);
      setLastScan(sig.last_scan);
      setTodayTrades(hist.today_trades);
      setHistory(hist.signals);
      setStats(hist.stats);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load intraday data");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(() => refresh(true), 60000);
    return () => clearInterval(interval);
  }, [refresh]);

  const handleAdd = async (symbol: string, _market: "US", name?: string) => {
    await api.addIntradaySymbol(symbol, name);
    await api.triggerIntradayScan();
    await refresh(true);
  };

  const handleBulkComplete = async (result: import("../api").BulkAddResult) => {
    if (result.added.length > 0) {
      await api.triggerIntradayScan();
      await refresh(true);
    }
  };

  const handleRemove = async (symbol: string) => {
    await api.removeIntradaySymbol(symbol);
    await refresh(true);
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await api.triggerIntradayScan();
      await refresh(true);
    } finally {
      setScanning(false);
    }
  };

  const openTodayTrades = todayTrades.filter((t) => t.status === "open");

  return (
    <div className="intraday-panel">
      <div className="intraday-toolbar">
        <p className="intraday-intro">
          US intraday model — VWAP, market structure, RVOL, EMA stack, opening range &amp; gap.
          Scans every <strong>2 minutes</strong> during market hours.
        </p>
        <div className="intraday-toolbar-actions">
          {lastScan && <span className="scan-info">Last scan: {new Date(lastScan).toLocaleString()}</span>}
          <button className="btn btn-ghost" onClick={handleScan} disabled={scanning}>
            {scanning ? "Scanning…" : "Scan now"}
          </button>
        </div>
      </div>

      {stats && <StatsBar stats={stats} />}

      <section className="intraday-section">
        <h2 className="section-title">Intraday watchlist (US)</h2>
        <WishlistAdd
          market="US"
          onAdd={handleAdd}
          onBulkComplete={handleBulkComplete}
          bulkAdd={async (symbols) => {
            const res = await api.bulkAddIntraday(symbols);
            return {
              added: res.added.map((a) => ({
                id: a.id,
                symbol: a.symbol,
                market: "US" as const,
                name: a.name,
                created_at: a.created_at,
              })),
              skipped: res.skipped,
              invalid: res.invalid,
            };
          }}
          error={error}
        />
        <div className="intraday-watchlist-chips">
          {watchlist.map((item) => (
            <span key={item.id} className="intraday-chip">
              {item.symbol}
              <button type="button" onClick={() => handleRemove(item.symbol)} aria-label={`Remove ${item.symbol}`}>×</button>
            </span>
          ))}
        </div>
      </section>

      {(todaySetups.length > 0 || openTodayTrades.length > 0) && (
        <section className="intraday-section intraday-today">
          <h2>Today&apos;s trades — ready for market order</h2>
          <p className="intraday-today-note">New setups and open positions for today appear here first.</p>
          <div className="intraday-today-grid">
            {todaySetups.map((s) => (
              <SetupCard key={`setup-${s.symbol}`} signal={s} />
            ))}
            {openTodayTrades.map((t) => (
              <TradeCard key={`trade-${t.id}`} record={t} />
            ))}
          </div>
        </section>
      )}

      {loading ? (
        <div className="loading-hint">Loading intraday data…</div>
      ) : signals.length === 0 ? (
        <div className="empty-state">
          <p>Add US stocks to the intraday list to start scanning 5m / 15m charts.</p>
        </div>
      ) : (
        <section className="intraday-section">
          <h2 className="section-title">Live signals</h2>
          <div className="intraday-signals-grid">
            {signals.map((s) => (
              <SetupCard key={s.symbol} signal={s} />
            ))}
          </div>
        </section>
      )}

      <section className="intraday-section">
        <h2 className="section-title">Intraday history &amp; accuracy</h2>
        <p className="intraday-history-note">Separate from swing History — tracks only intraday trade ideas.</p>
        {history.length === 0 ? (
          <div className="empty-state"><p>No intraday trades recorded yet.</p></div>
        ) : (
          <div className="intraday-history-list">
            {history.map((r) => (
              <TradeCard key={r.id} record={r} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
