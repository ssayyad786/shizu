import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { api, currencyForMarket, HistoryRecord, HistoryStats, Market } from "../api";

const MARKETS: { id: Market; label: string }[] = [
  { id: "US", label: "US" },
  { id: "IN", label: "India" },
];

const PAGE_SIZE = 30;
const GROUPS_PAGE = 12;

function statusLabel(record: HistoryRecord): { text: string; className: string } {
  switch (record.status) {
    case "target_hit":
      return { text: "Target hit", className: "status-win" };
    case "stop_hit":
      return { text: "Stop hit", className: "status-loss" };
    case "expired_win":
      return { text: "Window end — profit", className: "status-neutral" };
    case "expired_loss":
      return { text: "Window end — loss", className: "status-loss" };
    default:
      if (record.status === "open" && record.window_open === false) {
        return { text: "Window ended", className: "status-neutral" };
      }
      return { text: "In progress", className: "status-open" };
  }
}

function fmtPrice(n: number, market: Market) {
  const sym = currencyForMarket(market);
  return `${sym}${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function signalDateKey(record: HistoryRecord): string {
  return record.created_at.slice(0, 10);
}

function formatHistoryDateHeader(dateKey: string, isToday: boolean): string {
  const d = new Date(`${dateKey}T12:00:00`);
  const formatted = d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  return isToday ? `Today — ${formatted}` : formatted;
}

function isTodayDate(dateKey: string): boolean {
  const today = new Date();
  const key = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  return dateKey === key;
}

function groupHistoryByDate(records: HistoryRecord[]) {
  const byDate = new Map<string, HistoryRecord[]>();
  for (const record of records) {
    const key = signalDateKey(record);
    const list = byDate.get(key);
    if (list) list.push(record);
    else byDate.set(key, [record]);
  }

  const groups: { dateKey: string; isToday: boolean; trades: HistoryRecord[] }[] = [];
  const seen = new Set<string>();
  for (const record of records) {
    const key = signalDateKey(record);
    if (seen.has(key)) continue;
    seen.add(key);
    const trades = byDate.get(key) ?? [];
    groups.push({
      dateKey: key,
      isToday: isTodayDate(key),
      trades,
    });
  }
  return groups;
}

function daySummary(trades: HistoryRecord[]): string {
  const closed = trades.filter((t) => t.status !== "open");
  const wins = closed.filter((t) => t.success).length;
  const open = trades.length - closed.length;
  const parts = [`${trades.length} signal${trades.length === 1 ? "" : "s"}`];
  if (closed.length > 0) parts.push(`${wins}/${closed.length} targets hit`);
  if (open > 0) parts.push(`${open} open`);
  return parts.join(" · ");
}

function StatsBar({ stats }: { stats: HistoryStats }) {
  return (
    <div className="intraday-stats history-stats-bar">
      <div className="intraday-stat">
        <span>Win rate</span>
        <strong>{stats.win_rate}%</strong>
      </div>
      <div className="intraday-stat">
        <span>Target hits</span>
        <strong>{stats.target_hits ?? stats.wins}</strong>
      </div>
      <div className="intraday-stat">
        <span>Open</span>
        <strong>{stats.open}</strong>
      </div>
      <div className="intraday-stat">
        <span>Stop losses</span>
        <strong>{stats.stop_hits ?? 0}</strong>
      </div>
      <div className="intraday-stat">
        <span>Avg result</span>
        <strong>
          {stats.avg_result_pct > 0 ? "+" : ""}
          {stats.avg_result_pct}%
        </strong>
      </div>
      <div className="intraday-stat">
        <span>Total</span>
        <strong>{stats.total_signals}</strong>
      </div>
    </div>
  );
}

const HistoryTradeCard = memo(function HistoryTradeCard({
  record,
  defaultOpen = false,
}: {
  record: HistoryRecord;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const st = statusLabel(record);
  const isOpen = record.status === "open";
  const actionLabel = record.action.replace("_", " ");

  return (
    <article className={`intraday-card buy ${st.className} ${open ? "expanded" : "collapsed"}`}>
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
          <span className={`intraday-dir-pill ${record.action.includes("STRONG") ? "long" : "hold"}`}>
            {actionLabel}
          </span>
          <span className="intraday-summary-stat">@ {fmtPrice(record.entry_price, record.market)}</span>
          <span className={`intraday-status-inline ${st.className}`}>{st.text}</span>
          {isOpen && record.progress_pct != null && (
            <span className={`intraday-summary-stat ${record.progress_pct >= 0 ? "pnl-up" : "pnl-down"}`}>
              {record.progress_pct > 0 ? "+" : ""}
              {record.progress_pct}%
            </span>
          )}
          {!isOpen && record.result_pct != null && (
            <span className={`intraday-summary-stat ${record.result_pct >= 0 ? "pnl-up" : "pnl-down"}`}>
              {record.result_pct > 0 ? "+" : ""}
              {record.result_pct}%
            </span>
          )}
        </div>
      </button>

      {open && (
        <div className="intraday-card-body">
          <div className={`intraday-status ${st.className}`}>{st.text}</div>
          <div className="intraday-levels compact">
            <div>
              <span>Entry</span>
              <strong>{fmtPrice(record.entry_price, record.market)}</strong>
            </div>
            <div className="target-text">
              <span>Target</span>
              <strong>
                {fmtPrice(record.sell_target, record.market)} (+{record.target_pct}%)
              </strong>
            </div>
            <div className="stop-text">
              <span>Stop</span>
              <strong>
                {fmtPrice(record.stop_loss, record.market)} (−{record.stop_pct}%)
              </strong>
            </div>
            <div>
              <span>Score</span>
              <strong>{record.score}</strong>
            </div>
            <div>
              <span>Conf</span>
              <strong>{record.confidence}%</strong>
            </div>
            <div>
              <span>Window</span>
              <strong>{record.hold_days}d</strong>
            </div>
          </div>

          {isOpen && (
            <div className="history-progress-block">
              <span>
                Current: {record.current_price ? fmtPrice(record.current_price, record.market) : "—"}
              </span>
              <span className="scan-info">
                High: {record.highest_since ? fmtPrice(record.highest_since, record.market) : "—"} · Low:{" "}
                {record.lowest_since ? fmtPrice(record.lowest_since, record.market) : "—"}
              </span>
              <span className="scan-info">
                Window ends {new Date(record.expires_at).toLocaleString()}
                {record.window_open === false && " (ended)"}
              </span>
            </div>
          )}

          {!isOpen && record.result_pct != null && (
            <p className={`history-closed-line ${record.success ? "pnl-up" : record.result_pct >= 0 ? "" : "pnl-down"}`}>
              Closed at {record.exit_price ? fmtPrice(record.exit_price, record.market) : "—"} →{" "}
              <strong>
                {record.result_pct >= 0 ? "+" : ""}
                {record.result_pct}%
              </strong>
              {record.status === "target_hit" && record.days_to_target != null &&
                ` · target hit day ${record.days_to_target}`}
              {record.status === "stop_hit" && " · stop triggered"}
              {record.status.startsWith("expired") && " · target not reached in window"}
            </p>
          )}

          <p className="intraday-summary">{record.summary}</p>
          <p className="scan-info">Signal saved {new Date(record.created_at).toLocaleString()}</p>
        </div>
      )}
    </article>
  );
});

export default function HistoryPanel() {
  const [market, setMarket] = useState<Market>("US");
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [historyGroupsShown, setHistoryGroupsShown] = useState(GROUPS_PAGE);

  const load = useCallback(async (m: Market, opts?: { silent?: boolean; refreshPrices?: boolean }) => {
    const silent = opts?.silent ?? false;
    const refreshPrices = opts?.refreshPrices ?? false;
    if (silent) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await api.getHistory(m, {
        limit: PAGE_SIZE,
        offset: 0,
        refresh: refreshPrices,
      });
      setRecords(data.signals);
      setStats(data.stats);
      setTotal(data.total);
      setHasMore(data.has_more);
      setHistoryGroupsShown(GROUPS_PAGE);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const data = await api.getHistory(market, {
        limit: PAGE_SIZE,
        offset: records.length,
        refresh: false,
      });
      setRecords((prev) => [...prev, ...data.signals]);
      setTotal(data.total);
      setHasMore(data.has_more);
    } finally {
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    setRecords([]);
    load(market, { refreshPrices: true });
    const interval = setInterval(() => load(market, { silent: true, refreshPrices: false }), 90000);
    return () => clearInterval(interval);
  }, [market, load]);

  const openTrades = useMemo(() => records.filter((r) => r.status === "open"), [records]);
  const closedGroups = useMemo(
    () => groupHistoryByDate(records.filter((r) => r.status !== "open")),
    [records]
  );
  const visibleClosedGroups = useMemo(
    () => closedGroups.slice(0, historyGroupsShown),
    [closedGroups, historyGroupsShown]
  );

  const hasData = records.length > 0 || stats !== null;

  return (
    <div className="history-panel intraday-panel">
      <section className="intraday-section history-intro">
        <h2 className="section-title">Swing trade history</h2>
        <p className="intraday-intro">
          Every <strong>BUY</strong> or <strong>STRONG BUY</strong> with an achievable target is saved per market.
          Success means the sell target was hit within the estimated <strong>1–10 trading day</strong> window.
          Tap any row to expand entry, targets, and outcome.
        </p>
      </section>

      <div className="market-tabs history-market-tabs">
        {MARKETS.map((m) => (
          <button
            key={m.id}
            type="button"
            className={`market-tab ${market === m.id ? "active" : ""}`}
            onClick={() => setMarket(m.id)}
          >
            {m.label}
            {stats && market === m.id && stats.total_signals > 0 && (
              <span className="market-tab-count">{stats.total_signals}</span>
            )}
          </button>
        ))}
      </div>

      <div className="intraday-toolbar">
        <p className="scan-info history-toolbar-meta">
          {hasData && !loading
            ? `Showing ${records.length} of ${total} signal${total === 1 ? "" : "s"}`
            : " "}
          {refreshing && hasData && " · Updating outcomes…"}
        </p>
        <div className="intraday-toolbar-actions">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => load(market, { silent: true, refreshPrices: true })}
            disabled={loading || refreshing}
          >
            {refreshing ? "Refreshing…" : "Refresh outcomes"}
          </button>
        </div>
      </div>

      {loading && !hasData ? (
        <div className="loading-hint">Loading trade history…</div>
      ) : (
        <>
          {stats && stats.total_signals > 0 && <StatsBar stats={stats} />}

          {records.length === 0 ? (
            <div className="empty-state">
              <h2>No saved signals yet</h2>
              <p>
                Add stocks to your {market === "US" ? "US" : "Indian"} wishlist. When a BUY signal fires, it
                appears here with entry, target, and stop.
              </p>
            </div>
          ) : (
            <>
              {openTrades.length > 0 && (
                <section className="intraday-section intraday-today history-open-section">
                  <h2 className="section-title">Open trades — tracking window</h2>
                  <p className="intraday-today-note">
                    {openTrades.length} active signal{openTrades.length === 1 ? "" : "s"} being monitored for
                    target or stop.
                  </p>
                  <div className="intraday-card-list">
                    {openTrades.map((r, i) => (
                      <HistoryTradeCard key={r.id} record={r} defaultOpen={i === 0} />
                    ))}
                  </div>
                </section>
              )}

              <section className="intraday-section">
                <div className="intraday-section-header">
                  <h2 className="section-title">Past signals by date</h2>
                </div>
                <p className="intraday-history-note">
                  Grouped by signal date — separate from the Intraday tab (session trades).
                </p>

                {closedGroups.length === 0 ? (
                  <div className="empty-state">
                    <p>No closed signals yet — outcomes appear here once trades finish.</p>
                  </div>
                ) : (
                  <div className="intraday-history-by-date">
                    {visibleClosedGroups.map((group) => (
                      <section
                        key={group.dateKey}
                        className={`intraday-history-date-group${group.isToday ? " is-today" : ""}`}
                      >
                        <div className="intraday-history-date-header">
                          <h3>{formatHistoryDateHeader(group.dateKey, group.isToday)}</h3>
                          <span className="intraday-history-date-meta">{daySummary(group.trades)}</span>
                        </div>
                        <div className="intraday-card-list">
                          {group.trades.map((r) => (
                            <HistoryTradeCard key={r.id} record={r} />
                          ))}
                        </div>
                      </section>
                    ))}

                    {closedGroups.length > visibleClosedGroups.length && (
                      <button
                        type="button"
                        className="btn btn-ghost intraday-history-show-more"
                        onClick={() => setHistoryGroupsShown((n) => n + GROUPS_PAGE)}
                      >
                        Show older days ({closedGroups.length - visibleClosedGroups.length} more)
                      </button>
                    )}
                  </div>
                )}
              </section>

              {hasMore && (
                <button
                  type="button"
                  className="btn btn-ghost intraday-history-show-more"
                  onClick={loadMore}
                  disabled={loadingMore}
                >
                  {loadingMore ? "Loading…" : `Load more signals (${total - records.length} remaining)`}
                </button>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
