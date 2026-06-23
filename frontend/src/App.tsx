import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Market, StockDetail, StockSelection, StockSignal, WishlistItem } from "./api";
import HelpPanel from "./components/HelpPanel";
import AppFooter from "./components/AppFooter";
import HistoryPanel from "./components/HistoryPanel";
import OpportunityPanel from "./components/OpportunityPanel";
import SignalTable from "./components/SignalTable";
import StockDetailView from "./components/StockDetail";
import StockSearchInput from "./components/StockSearchInput";

type Tab = "dashboard" | "history" | "help";

const MARKETS: { id: Market; label: string; flag: string }[] = [
  { id: "US", label: "US", flag: "🇺🇸" },
  { id: "IN", label: "India", flag: "🇮🇳" },
];

function sameSelection(a: StockSelection | null, b: StockSelection | null) {
  return a?.symbol === b?.symbol && a?.market === b?.market;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [activeMarket, setActiveMarket] = useState<Market>("US");
  const [wishlist, setWishlist] = useState<WishlistItem[]>([]);
  const [signals, setSignals] = useState<StockSignal[]>([]);
  const [opportunities, setOpportunities] = useState<StockSignal[]>([]);
  const [lastScan, setLastScan] = useState<string | null>(null);
  const [selected, setSelected] = useState<StockSelection | null>(null);
  const [stockDetail, setStockDetail] = useState<StockDetail | null>(null);
  const [period, setPeriod] = useState("6mo");
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [loading, setLoading] = useState(false);
  const [wishlistLoading, setWishlistLoading] = useState(true);
  const [wishlistError, setWishlistError] = useState("");
  const [scanning, setScanning] = useState(false);

  const wishlistForMarket = useMemo(
    () => wishlist.filter((w) => w.market === activeMarket),
    [wishlist, activeMarket]
  );

  const signalsForMarket = useMemo(
    () => signals.filter((s) => (s.market || "US") === activeMarket),
    [signals, activeMarket]
  );

  const opportunitiesForMarket = useMemo(
    () => opportunities.filter((s) => (s.market || "US") === activeMarket),
    [opportunities, activeMarket]
  );

  const refreshSignals = useCallback(async () => {
    try {
      const data = await api.getSignals();
      setSignals(data.signals);
      setOpportunities(data.opportunities);
      setLastScan(data.last_scan);
    } catch {
      /* backend may not be ready yet */
    }
  }, []);

  const loadWishlist = useCallback(async () => {
    setWishlistError("");
    try {
      const items = await api.getWishlist();
      setWishlist(items);
    } catch (e) {
      setWishlistError(e instanceof Error ? e.message : "Failed to load wishlist");
    } finally {
      setWishlistLoading(false);
    }
  }, []);

  const loadDetail = useCallback(async (pick: StockSelection, p = period) => {
    setLoading(true);
    setDetailError("");
    setSelected(pick);
    setStockDetail(null);
    setActiveMarket(pick.market);
    try {
      const detail = await api.getStockDetail(pick.symbol, p);
      setStockDetail(detail);
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : "Failed to load stock");
      setStockDetail(null);
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    loadWishlist();
    refreshSignals();
    const interval = setInterval(refreshSignals, 30000);
    return () => clearInterval(interval);
  }, [loadWishlist, refreshSignals]);

  useEffect(() => {
    if (selected) {
      loadDetail(selected, period);
    }
  }, [period]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleMarketChange = (market: Market) => {
    setActiveMarket(market);
    setError("");

    const items = wishlist.filter((w) => w.market === market);
    const keep = selected && selected.market === market ? selected : null;
    const inList = keep && items.some((w) => w.symbol === keep.symbol);

    if (inList && keep) {
      if (!sameSelection(selected, keep)) {
        loadDetail(keep, period);
      }
      return;
    }

    if (items.length > 0) {
      loadDetail({ symbol: items[0].symbol, market: items[0].market }, period);
      return;
    }

    setSelected(null);
    setStockDetail(null);
    setDetailError("");
  };

  const handleAdd = async (symbol: string, market: Market, name?: string) => {
    setError("");
    try {
      await api.addToWishlist(symbol, market, name);
      setActiveMarket(market);
      await loadWishlist();
      try {
        await api.triggerScan();
        await refreshSignals();
      } catch (scanErr) {
        setError(
          scanErr instanceof Error
            ? `Added ${symbol}, but scan failed: ${scanErr.message}`
            : `Added ${symbol}, but scan failed`
        );
      }
      await loadDetail({ symbol, market }, period);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to add";
      setError(message);
      if (message.includes("already in your")) {
        const items = await api.getWishlist().catch(() => []);
        setWishlist(items);
        const existing = items.find((w) => w.symbol === symbol && w.market === market);
        if (existing) {
          await loadDetail({ symbol: existing.symbol, market: existing.market }, period);
        }
      }
      throw e;
    }
  };

  const handleRemove = async (symbol: string, market: Market, e: React.MouseEvent) => {
    e.stopPropagation();
    await api.removeFromWishlist(symbol, market);
    if (selected?.symbol === symbol && selected.market === market) {
      setSelected(null);
      setStockDetail(null);
      setDetailError("");
    }
    await loadWishlist();
    await refreshSignals();
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await api.triggerScan();
      await refreshSignals();
    } finally {
      setScanning(false);
    }
  };

  const handleSelect = (symbol: string, market: Market) => {
    setActiveTab("dashboard");
    setPeriod("6mo");
    loadDetail({ symbol, market }, "6mo");
  };

  const showDetail = activeTab === "dashboard" && selected && stockDetail && !detailError;

  return (
    <div className="app-shell">
    <div className="app">
      <aside className="sidebar">
        <div className="header" style={{ borderBottom: "1px solid var(--border)" }}>
          <div>
            <h1>Market Monitor</h1>
            <div className="subtitle">Wishlists</div>
          </div>
        </div>

        <div className="market-tabs sidebar-market-tabs">
          {MARKETS.map((m) => (
            <button
              key={m.id}
              className={`market-tab ${activeMarket === m.id ? "active" : ""}`}
              onClick={() => handleMarketChange(m.id)}
            >
              {m.flag} {m.label}
              <span className="market-count">
                {wishlist.filter((w) => w.market === m.id).length}
              </span>
            </button>
          ))}
        </div>

        <div className="sidebar-section">
          <h2>Add to {activeMarket === "US" ? "US" : "Indian"} wishlist</h2>
          <StockSearchInput market={activeMarket} onAdd={handleAdd} error={error} />
        </div>

        {wishlistError && <div className="error" style={{ margin: "0 16px 8px" }}>{wishlistError}</div>}

        <div className="wishlist">
          {wishlistLoading ? (
            <div style={{ padding: 16, color: "var(--muted)", fontSize: "0.85rem", textAlign: "center" }}>
              Loading wishlist…
            </div>
          ) : wishlistForMarket.length === 0 ? (
            <div style={{ padding: 16, color: "var(--muted)", fontSize: "0.85rem", textAlign: "center" }}>
              No {activeMarket === "US" ? "US" : "Indian"} stocks yet.
            </div>
          ) : (
            wishlistForMarket.map((item) => (
              <div
                key={item.id}
                className={`wishlist-item ${
                  selected?.symbol === item.symbol && selected.market === item.market ? "active" : ""
                }`}
                onClick={() => handleSelect(item.symbol, item.market)}
              >
                <div>
                  <div className="symbol">{item.symbol}</div>
                  {item.name && <div className="name">{item.name}</div>}
                </div>
                <button
                  className="remove"
                  onClick={(e) => handleRemove(item.symbol, item.market, e)}
                  title="Remove"
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <main className="main">
        <header className="header">
          <div>
            <div className="main-tabs">
              <button
                className={`main-tab ${activeTab === "dashboard" ? "active" : ""}`}
                onClick={() => setActiveTab("dashboard")}
              >
                Dashboard
              </button>
              <button
                className={`main-tab ${activeTab === "history" ? "active" : ""}`}
                onClick={() => setActiveTab("history")}
              >
                History
              </button>
              <button
                className={`main-tab ${activeTab === "help" ? "active" : ""}`}
                onClick={() => setActiveTab("help")}
              >
                Help
              </button>
            </div>
            <h1>
              {activeTab === "help"
                ? "Indicator guide"
                : activeTab === "history"
                  ? "Trade signal history"
                  : selected
                    ? `${selected.symbol} — Chart & Analysis`
                    : `${activeMarket === "US" ? "US" : "Indian"} dashboard`}
            </h1>
            {activeTab === "dashboard" && (
              <div className="subtitle scan-info">
                {lastScan
                  ? `Last scan: ${new Date(lastScan).toLocaleString()} · Scans every 5 min · UI refreshes every 30s`
                  : "Waiting for first scan…"}
              </div>
            )}
          </div>
          {activeTab === "dashboard" && (
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <span className="badge live">Monitoring</span>
              <button className="btn btn-ghost" onClick={handleScan} disabled={scanning}>
                {scanning ? "Scanning…" : "Scan now"}
              </button>
            </div>
          )}
        </header>

        {activeTab === "dashboard" && (
          <OpportunityPanel
            opportunities={opportunitiesForMarket}
            market={activeMarket}
            onSelect={handleSelect}
          />
        )}

        <div className="content">
          {activeTab === "help" ? (
            <HelpPanel />
          ) : activeTab === "history" ? (
            <HistoryPanel />
          ) : (
            <>
              {loading && <div style={{ color: "var(--muted)", marginBottom: 16 }}>Loading chart…</div>}

              {detailError && (
                <div className="error" style={{ marginBottom: 16 }}>
                  {detailError}
                </div>
              )}

              {showDetail ? (
                <StockDetailView
                  detail={stockDetail}
                  period={period}
                  onPeriodChange={setPeriod}
                />
              ) : (
                <>
                  <h2 style={{ fontSize: "1rem", marginBottom: 16 }}>
                    {activeMarket === "US" ? "US" : "Indian"} watched stocks
                  </h2>
                  <SignalTable
                    signals={signalsForMarket}
                    market={activeMarket}
                    selected={selected}
                    onSelect={handleSelect}
                  />
                  {signalsForMarket.length === 0 &&
                    wishlist.some((w) => w.market === activeMarket) && (
                    <div className="empty-state">
                      <p>Click "Scan now" to analyze your wishlist.</p>
                    </div>
                  )}
                  {!wishlist.some((w) => w.market === activeMarket) && (
                    <div className="empty-state">
                      <p>Add stocks to your {activeMarket === "US" ? "US" : "Indian"} wishlist to get started.</p>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </main>
    </div>
    <AppFooter />
    </div>
  );
}
