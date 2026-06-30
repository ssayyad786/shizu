import { useCallback, useEffect, useState } from "react";
import {
  api,
  IntradayHistoryRecord,
  IntradayLiveSignal,
  IntradayStats,
  IntradayWatchlistItem,
  Market,
  UsMarketStatus,
} from "../api";
import WishlistAdd from "./WishlistAdd";
import WhyTradeBlock from "./WhyTradeBlock";
import IntradayReportDownload from "./IntradayReportDownload";
import IntradayDatasetExport from "./IntradayDatasetExport";
import IntradayBacktestPanel from "./IntradayBacktestPanel";

function fmt(n: number) {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatCountdown(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function useCountdown(targetIso: string | null | undefined): number | null {
  const [remaining, setRemaining] = useState<number | null>(null);
  useEffect(() => {
    if (!targetIso) {
      setRemaining(null);
      return;
    }
    const update = () => {
      const ms = new Date(targetIso).getTime() - Date.now();
      setRemaining(Math.max(0, Math.floor(ms / 1000)));
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [targetIso]);
  return remaining;
}

function UsMarketBanner({ market }: { market: UsMarketStatus }) {
  const countdownTarget = market.is_open ? market.session_close_at : market.next_session_open_at;
  const remaining = useCountdown(countdownTarget);
  const countdown =
    remaining != null ? formatCountdown(remaining) : market.is_open ? "—" : null;

  return (
    <div className={`us-market-banner ${market.is_open ? "us-market-open" : "us-market-closed"}`}>
      <div className="us-market-banner-main">
        <span className="us-market-dot" aria-hidden />
        <strong>{market.is_open ? "US market open" : "US market closed"}</strong>
        <span className="us-market-hours">
          Regular session {market.open_time}–{market.close_time} ET
        </span>
      </div>
      {countdown != null && (
        <span className="us-market-countdown">
          {market.is_open ? "Closes in " : "Opens in "}
          <strong>{countdown}</strong>
        </span>
      )}
      {!market.is_open && <p className="us-market-note">{market.message}</p>}
    </div>
  );
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

function SetupCard({
  signal,
  defaultOpen = false,
  showTodayBadge = false,
}: {
  signal: IntradayLiveSignal;
  defaultOpen?: boolean;
  showTodayBadge?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const plan = signal.trade_plan;
  const isLong = signal.direction === "LONG";
  const tone = isLong ? "long" : signal.direction === "SHORT" ? "short" : "hold";

  return (
    <article className={`intraday-card ${tone} ${open ? "expanded" : "collapsed"}`}>
      <button
        type="button"
        className="intraday-card-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="intraday-chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
        <div className="intraday-card-summary">
          <span className="intraday-symbol">{signal.symbol}</span>
          <span className={`intraday-dir-pill ${tone}`}>{signal.direction}</span>
          <span className="intraday-summary-stat">{signal.confidence}%</span>
          {plan && (
            <>
              <span className="intraday-summary-stat">@ {fmt(plan.entry_price)}</span>
              <span className="intraday-summary-stat target-text">T1 {fmt(plan.target_1)}</span>
              <span className="intraday-summary-stat stop-text">Stop {fmt(plan.stop_loss)}</span>
            </>
          )}
        </div>
        {showTodayBadge && signal.actionable && (
          <span className="intraday-badge-today">Today</span>
        )}
      </button>

      {open && (
        <div className="intraday-card-body">
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
            <p className="intraday-meta">
              VWAP {fmt(signal.vwap)} · RVOL {signal.rvol ?? "—"}× · Daily {signal.daily_trend}
            </p>
          )}
          <p className="intraday-summary">{signal.summary}</p>
          <WhyTradeBlock
            headline={signal.why_headline}
            reasons={signal.trade_reasons}
            fallbackBullets={signal.reasoning}
          />
        </div>
      )}
    </article>
  );
}

function TradeCard({
  record,
  defaultOpen = false,
}: {
  record: IntradayHistoryRecord;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const st = statusLabel(record);
  const isLong = record.direction === "LONG";
  const tone = isLong ? "long" : "short";

  return (
    <article className={`intraday-card ${tone} ${st.className} ${open ? "expanded" : "collapsed"}`}>
      <button
        type="button"
        className="intraday-card-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="intraday-chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
        <div className="intraday-card-summary">
          <span className="intraday-symbol">{record.symbol}</span>
          {record.name && <span className="intraday-name-inline">{record.name}</span>}
          <span className={`intraday-dir-pill ${tone}`}>{record.direction}</span>
          <span className="intraday-summary-stat">@ {fmt(record.entry_price)}</span>
          <span className={`intraday-status-inline ${st.className}`}>{st.text}</span>
          {record.progress_pct != null && record.status === "open" && (
            <span className={`intraday-summary-stat ${record.progress_pct >= 0 ? "pnl-up" : "pnl-down"}`}>
              {record.progress_pct > 0 ? "+" : ""}{record.progress_pct}%
            </span>
          )}
          {record.result_pct != null && record.status !== "open" && (
            <span className={`intraday-summary-stat ${record.result_pct >= 0 ? "pnl-up" : "pnl-down"}`}>
              {record.result_pct > 0 ? "+" : ""}{record.result_pct}%
            </span>
          )}
        </div>
      </button>

      {open && (
        <div className="intraday-card-body">
          <div className={`intraday-status ${st.className}`}>{st.text}</div>
          <div className="intraday-levels compact">
            <div><span>{record.direction}</span><strong>{fmt(record.entry_price)}</strong></div>
            <div><span>T1</span><strong>{fmt(record.target_1)}</strong></div>
            <div><span>T2</span><strong>{fmt(record.target_2)}</strong></div>
            <div><span>Stop</span><strong>{fmt(record.stop_loss)}</strong></div>
            {record.current_price != null && (
              <div><span>Now</span><strong>{fmt(record.current_price)}</strong></div>
            )}
            <div><span>R:R</span><strong>{record.risk_reward}:1</strong></div>
          </div>
          <p className="intraday-summary">{record.summary}</p>
          <WhyTradeBlock
            headline={record.why_headline}
            reasons={record.trade_reasons}
            fallbackBullets={record.reasoning}
          />
        </div>
      )}
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
  const [market, setMarket] = useState<UsMarketStatus | null>(null);
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
      setMarket(sig.market ?? hist.market ?? null);
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

  const handleAdd = async (symbol: string, _market: Market, name?: string) => {
    await api.addIntradaySymbol(symbol, name);
    if (market?.is_open) {
      await api.triggerIntradayScan();
    }
    await refresh(true);
  };

  const handleBulkComplete = async (result: import("../api").BulkAddResult) => {
    if (result.added.length > 0) {
      if (market?.is_open) {
        await api.triggerIntradayScan();
      }
      await refresh(true);
    }
  };

  const handleRemove = async (symbol: string) => {
    await api.removeIntradaySymbol(symbol);
    await refresh(true);
  };

  const handleScan = async () => {
    if (!market?.is_open) return;
    setScanning(true);
    try {
      await api.triggerIntradayScan();
      await refresh(true);
    } finally {
      setScanning(false);
    }
  };

  const marketOpen = market?.is_open ?? false;

  const openTodayTrades = todayTrades.filter((t) => t.status === "open");

  return (
    <div className="intraday-panel">
      {market && <UsMarketBanner market={market} />}

      <IntradayReportDownload onError={setError} />
      <IntradayDatasetExport onError={setError} />
      <IntradayBacktestPanel watchlistSymbols={watchlist.map((w) => w.symbol)} onError={setError} />

      <div className="intraday-toolbar">
        <p className="intraday-intro">
          US intraday model — VWAP, market structure, RVOL, EMA stack, opening range &amp; gap.
          {marketOpen ? (
            <> Scans every <strong>2 minutes</strong> while the market is open.</>
          ) : (
            <> Scans run only during US regular hours (9:30 AM–4:00 PM ET).</>
          )}{" "}
          Click a symbol to expand trade details.
        </p>
        <div className="intraday-toolbar-actions">
          {lastScan && <span className="scan-info">Last scan: {new Date(lastScan).toLocaleString()}</span>}
          <button
            className="btn btn-ghost"
            onClick={handleScan}
            disabled={scanning || !marketOpen}
            title={marketOpen ? undefined : "US market is closed"}
          >
            {scanning ? "Scanning…" : "Scan now"}
          </button>
        </div>
      </div>

      {error && <div className="error content-error">{error}</div>}

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
          <p className="intraday-today-note">Tap a row to expand entry, targets, and why we suggest the trade.</p>
          <div className="intraday-card-list">
            {todaySetups.map((s, i) => (
              <SetupCard key={`setup-${s.symbol}`} signal={s} showTodayBadge defaultOpen={i === 0} />
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
          <div className="intraday-card-list">
            {signals.map((s) => (
              <SetupCard key={s.symbol} signal={s} />
            ))}
          </div>
        </section>
      )}

      <section className="intraday-section">
        <div className="intraday-section-header">
          <h2 className="section-title">Intraday history &amp; accuracy</h2>
          <IntradayReportDownload compact onError={setError} />
        </div>
        <p className="intraday-history-note">
          Separate from swing History — tracks only intraday trade ideas.
        </p>
        {history.length === 0 ? (
          <div className="empty-state"><p>No intraday trades recorded yet.</p></div>
        ) : (
          <div className="intraday-card-list">
            {history.map((r) => (
              <TradeCard key={r.id} record={r} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
