import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  ApiError,
  currencyForMarket,
  HoldingFormData,
  HoldingSignal,
  Market,
} from "../api";
import { getHoldingsSession, HoldingsSession, setHoldingsSession } from "../holdingsAuth";
import HoldingsAdd from "./HoldingsAdd";
import HoldingsAuthGate from "./HoldingsAuthGate";
import MarketTabs from "./MarketTabs";

interface Props {
  market: Market;
  onMarketChange: (market: Market) => void;
}

function fmt(n: number | null | undefined, market: Market) {
  if (n == null || !Number.isFinite(n)) return "—";
  const sym = currencyForMarket(market);
  return `${sym}${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(n: number | null | undefined) {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function recommendationClass(rec: string, strength: string) {
  if (rec === "SELL" && strength === "STRONG") return "sell-strong";
  if (rec === "SELL") return "sell";
  if (strength === "BULLISH") return "bullish";
  return "hold";
}

function HoldingCard({
  item,
  market,
  onRemove,
  onUpdate,
}: {
  item: HoldingSignal;
  market: Market;
  onRemove: (symbol: string, market: Market) => void;
  onUpdate: (symbol: string, market: Market, avg_cost: number, shares?: number) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [avgCost, setAvgCost] = useState(String(item.holding.avg_cost));
  const [shares, setShares] = useState(item.holding.shares != null ? String(item.holding.shares) : "");
  const [saving, setSaving] = useState(false);

  const m = item.market || market;
  const advice = item.advice;
  const recClass = recommendationClass(advice.recommendation, advice.strength);

  const saveEdit = async () => {
    const avg = parseFloat(avgCost);
    if (!Number.isFinite(avg) || avg <= 0) return;
    const shareNum = shares.trim() ? parseFloat(shares) : undefined;
    setSaving(true);
    try {
      await onUpdate(item.symbol, m, avg, shareNum);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className={`holding-card ${recClass}`}>
      <header className="holding-card-header">
        <div>
          <div className="holding-symbol">{item.symbol}</div>
          {item.holding.name && <div className="holding-name">{item.holding.name}</div>}
        </div>
        <div className="holding-rec-badge">
          {advice.recommendation}
          {advice.strength !== "NEUTRAL" && advice.strength !== "BULLISH" && (
            <span className="holding-strength"> · {advice.strength}</span>
          )}
        </div>
      </header>

      <p className="holding-headline">{advice.headline}</p>

      <div className="holding-levels">
        <div>
          <span className="holding-level-label">Your avg</span>
          <strong>{fmt(advice.avg_cost, m)}</strong>
        </div>
        <div>
          <span className="holding-level-label">Current</span>
          <strong>{fmt(advice.current_price, m)}</strong>
        </div>
        <div>
          <span className="holding-level-label">P&amp;L</span>
          <strong className={advice.unrealized_pnl_pct != null && advice.unrealized_pnl_pct >= 0 ? "pnl-up" : "pnl-down"}>
            {fmtPct(advice.unrealized_pnl_pct)}
            {advice.unrealized_pnl != null && (
              <span className="holding-pnl-amt"> ({fmt(advice.unrealized_pnl, m)})</span>
            )}
          </strong>
        </div>
      </div>

      {(advice.upper_target != null || advice.lower_target != null) && (
        <div className="holding-targets">
          {advice.upper_target != null && (
            <div className="target-text">
              <strong>Upside target:</strong> {fmt(advice.upper_target, m)}
              {advice.upper_pct != null && ` (+${advice.upper_pct}%)`}
            </div>
          )}
          {advice.lower_target != null && (
            <div className="stop-text">
              <strong>Support / stop zone:</strong> {fmt(advice.lower_target, m)}
              {advice.lower_pct != null && ` (${advice.lower_pct}%)`}
            </div>
          )}
        </div>
      )}

      {advice.reasoning.length > 0 && (
        <ul className="holding-reasoning">
          {advice.reasoning.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}

      <p className="holding-summary">{advice.summary}</p>
      <p className="holding-meta">
        Model: {item.action.replace("_", " ")} · {advice.confidence}% confidence · score {advice.score}
      </p>

      {editing ? (
        <div className="holding-edit-row">
          <input
            className="holdings-input"
            type="number"
            step="any"
            value={avgCost}
            onChange={(e) => setAvgCost(e.target.value)}
            placeholder="Avg cost"
          />
          <input
            className="holdings-input"
            type="number"
            step="any"
            value={shares}
            onChange={(e) => setShares(e.target.value)}
            placeholder="Shares"
          />
          <button type="button" className="btn btn-primary" onClick={saveEdit} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </div>
      ) : (
        <div className="holding-actions">
          <button type="button" className="btn btn-ghost" onClick={() => setEditing(true)}>
            Edit cost
          </button>
          <button
            type="button"
            className="btn btn-ghost holding-remove"
            onClick={() => onRemove(item.symbol, m)}
          >
            Remove
          </button>
        </div>
      )}
    </article>
  );
}

export default function HoldingsPanel({ market, onMarketChange }: Props) {
  const [session, setSession] = useState<HoldingsSession | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [signals, setSignals] = useState<HoldingSignal[]>([]);
  const [sellAlerts, setSellAlerts] = useState<HoldingSignal[]>([]);
  const [lastScan, setLastScan] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");

  const holdingsCounts = useMemo(
    () => ({
      US: signals.filter((s) => (s.market || "US") === "US").length,
      IN: signals.filter((s) => (s.market || "IN") === "IN").length,
    }),
    [signals]
  );

  const refresh = useCallback(
    async (silent = false) => {
      if (!getHoldingsSession()) return;
      if (!silent) setLoading(true);
      try {
        const data = await api.getHoldingsSignals(market);
        setSignals(data.signals);
        setSellAlerts(data.sell_alerts);
        setLastScan(data.last_scan);
        setError("");
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Failed to load holdings";
        if (e instanceof ApiError && e.status === 401) {
          setHoldingsSession(null);
          setSession(null);
        }
        setError(msg);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [market]
  );

  useEffect(() => {
    const stored = getHoldingsSession();
    if (!stored) {
      setAuthChecked(true);
      return;
    }
    api
      .getHoldingProfileMe()
      .then(() => setSession(stored))
      .catch(() => setHoldingsSession(null))
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    if (!session) return;
    refresh();
    const interval = setInterval(() => refresh(true), 60000);
    return () => clearInterval(interval);
  }, [refresh, session]);

  const handleAuthenticated = async (s: HoldingsSession) => {
    setHoldingsSession(s);
    setError("");
    try {
      await api.getHoldingProfileMe();
      setSession(s);
    } catch (e) {
      setHoldingsSession(null);
      setSession(null);
      setError(e instanceof Error ? e.message : "Sign-in failed — please try again");
      throw e;
    }
  };

  const handleSignOut = async () => {
    try {
      await api.logoutHoldingProfile();
    } catch {
      /* clear local session even if logout request fails */
    }
    setHoldingsSession(null);
    setSession(null);
    setSignals([]);
    setSellAlerts([]);
    setLastScan(null);
    setError("");
  };

  const handleAdd = async (data: HoldingFormData) => {
    setError("");
    await api.addHolding(data.symbol, market, {
      avg_cost: data.avg_cost,
      shares: data.shares,
      purchase_date: data.purchase_date,
      name: data.name,
    });
    await api.triggerHoldingsScan();
    await refresh(true);
  };

  const handleRemove = async (symbol: string, m: Market) => {
    await api.removeHolding(symbol, m);
    await refresh(true);
  };

  const handleUpdate = async (symbol: string, m: Market, avg_cost: number, shares?: number) => {
    await api.updateHolding(symbol, m, { avg_cost, shares });
    await api.triggerHoldingsScan();
    await refresh(true);
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await api.triggerHoldingsScan();
      await refresh(true);
    } finally {
      setScanning(false);
    }
  };

  if (!authChecked) {
    return <div className="loading-hint">Checking session…</div>;
  }

  if (!session) {
    return <HoldingsAuthGate onAuthenticated={handleAuthenticated} />;
  }

  const sellForMarket = sellAlerts;

  return (
    <div className="holdings-panel">
      <div className="holdings-session-bar">
        <span>
          Signed in as <strong>{session.username}</strong>
        </span>
        <button type="button" className="btn btn-ghost" onClick={handleSignOut}>
          Sign out
        </button>
      </div>

      <div className="holdings-toolbar">
        <MarketTabs
          activeMarket={market}
          wishlist={[]}
          counts={holdingsCounts}
          onChange={onMarketChange}
        />
        <div className="holdings-toolbar-actions">
          {lastScan && (
            <span className="scan-info">
              Last scan: {new Date(lastScan).toLocaleString()}
            </span>
          )}
          <button className="btn btn-ghost" onClick={handleScan} disabled={scanning}>
            {scanning ? "Scanning…" : "Scan now"}
          </button>
        </div>
      </div>

      <section className="holdings-add-section">
        <h2 className="section-title">Add a position</h2>
        <HoldingsAdd market={market} onAdd={handleAdd} error={error} />
      </section>

      {sellForMarket.length > 0 && (
        <section className="holdings-alerts">
          <h2>
            {market === "US" ? "US" : "Indian"} sell alerts ({sellForMarket.length})
          </h2>
          <p className="holdings-alerts-note">
            Bearish indicator score — review whether to reduce or exit.
          </p>
        </section>
      )}

      {loading ? (
        <div className="loading-hint">Loading holdings…</div>
      ) : signals.length === 0 ? (
        <div className="empty-state">
          <p>
            No {market === "US" ? "US" : "Indian"} holdings yet. Add a stock you own to get sell/hold advice.
          </p>
        </div>
      ) : (
        <div className="holdings-grid">
          {signals.map((item) => (
            <HoldingCard
              key={`${item.market}:${item.symbol}`}
              item={item}
              market={market}
              onRemove={handleRemove}
              onUpdate={handleUpdate}
            />
          ))}
        </div>
      )}
    </div>
  );
}
