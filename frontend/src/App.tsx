import { useCallback, useEffect, useMemo, useState } from "react";
import { api, BulkAddResult, HoldingItem, Market, StockDetail, StockSelection, StockSignal, WishlistItem } from "./api";
import HelpPanel from "./components/HelpPanel";
import AppFooter from "./components/AppFooter";
import BrandMark from "./components/BrandMark";
import HistoryPanel from "./components/HistoryPanel";
import HoldingsPanel from "./components/HoldingsPanel";
import IntradayPanel from "./components/IntradayPanel";
import IntradayReportDownload from "./components/IntradayReportDownload";
import MarketTabs from "./components/MarketTabs";
import MobileToolbar from "./components/MobileToolbar";
import OpportunityPanel from "./components/OpportunityPanel";
import SignalTable from "./components/SignalTable";
import StockDetailView from "./components/StockDetail";
import WishlistAdd from "./components/WishlistAdd";
import ViewModeToggle, { getDefaultViewMode, saveViewMode, ViewMode } from "./components/ViewModeToggle";

type Tab = "dashboard" | "intraday" | "holdings" | "history" | "help";
type MobilePanel = "wishlist" | "main";

function sameSelection(a: StockSelection | null, b: StockSelection | null) {
  return a?.symbol === b?.symbol && a?.market === b?.market;
}

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>(getDefaultViewMode);
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("main");
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [activeMarket, setActiveMarket] = useState<Market>("US");
  const [wishlist, setWishlist] = useState<WishlistItem[]>([]);
  const [holdings, setHoldings] = useState<HoldingItem[]>([]);
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

  const isMobileLayout = viewMode === "mobile";

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

  const changeViewMode = (mode: ViewMode) => {
    saveViewMode(mode);
    setViewMode(mode);
  };

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

  const loadHoldings = useCallback(async () => {
    try {
      const items = await api.getHoldings();
      setHoldings(items);
    } catch {
      /* backend may not be ready yet */
    }
  }, []);

  const holdingsCounts = useMemo(
    () => ({
      US: holdings.filter((h) => h.market === "US").length,
      IN: holdings.filter((h) => h.market === "IN").length,
    }),
    [holdings]
  );

  const loadDetail = useCallback(async (pick: StockSelection, p = period) => {
    setLoading(true);
    setDetailError("");
    setSelected(pick);
    setStockDetail(null);
    setActiveMarket(pick.market);
    if (viewMode === "mobile") setMobilePanel("main");
    try {
      const detail = await api.getStockDetail(pick.symbol, p);
      setStockDetail(detail);
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : "Failed to load stock");
      setStockDetail(null);
    } finally {
      setLoading(false);
    }
  }, [period, viewMode]);

  useEffect(() => {
    loadWishlist();
    loadHoldings();
    refreshSignals();
    const interval = setInterval(refreshSignals, 30000);
    return () => clearInterval(interval);
  }, [loadWishlist, loadHoldings, refreshSignals]);

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

  const handleBulkComplete = async (result: BulkAddResult) => {
    setError("");
    await loadWishlist();

    if (result.added.length > 0) {
      try {
        await api.triggerScan();
        await refreshSignals();
      } catch (scanErr) {
        setError(
          scanErr instanceof Error
            ? `Imported ${result.added.length}, but scan failed: ${scanErr.message}`
            : `Imported ${result.added.length}, but scan failed`
        );
      }

      const first = result.added[0];
      await loadDetail({ symbol: first.symbol, market: first.market }, period);
      setActiveTab("dashboard");
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

  const openMobileTab = (tab: Tab) => {
    setActiveTab(tab);
    setMobilePanel("main");
  };

  const showDetail = activeTab === "dashboard" && selected && stockDetail && !detailError;

  const sidebarContent = (
    <>
      <div className="header sidebar-header">
        <BrandMark tagline="Market Monitor" />
      </div>

      {!isMobileLayout && (
        <div className="sidebar-market-tabs">
          <MarketTabs
            activeMarket={activeMarket}
            wishlist={wishlist}
            onChange={handleMarketChange}
          />
        </div>
      )}

      <div className="sidebar-section">
        <h2>Add to {activeMarket === "US" ? "US" : "Indian"} wishlist</h2>
        <WishlistAdd
          market={activeMarket}
          onAdd={handleAdd}
          onBulkComplete={handleBulkComplete}
          error={error}
        />
      </div>

      {wishlistError && <div className="error sidebar-error">{wishlistError}</div>}

      <div className="wishlist">
        {wishlistLoading ? (
          <div className="wishlist-empty">Loading wishlist…</div>
        ) : wishlistForMarket.length === 0 ? (
          <div className="wishlist-empty">
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
                aria-label={`Remove ${item.symbol}`}
              >
                ×
              </button>
            </div>
          ))
        )}
      </div>
    </>
  );

  const mainContent = (
    <>
      <header className="header main-header">
        <div>
          <div className="main-tabs">
            <button
              className={`main-tab ${activeTab === "dashboard" ? "active" : ""}`}
              onClick={() => openMobileTab("dashboard")}
            >
              Dashboard
            </button>
            <button
              className={`main-tab ${activeTab === "intraday" ? "active" : ""}`}
              onClick={() => openMobileTab("intraday")}
            >
              Intraday
            </button>
            <button
              className={`main-tab ${activeTab === "holdings" ? "active" : ""}`}
              onClick={() => openMobileTab("holdings")}
            >
              My Holdings
            </button>
            <button
              className={`main-tab ${activeTab === "history" ? "active" : ""}`}
              onClick={() => openMobileTab("history")}
            >
              History
            </button>
            <button
              className={`main-tab ${activeTab === "help" ? "active" : ""}`}
              onClick={() => openMobileTab("help")}
            >
              Help
            </button>
          </div>
          <h1>
            {activeTab === "help"
              ? "Indicator guide"
              : activeTab === "history"
                ? "Trade signal history"
                : activeTab === "intraday"
                  ? "US intraday — VWAP & structure"
                  : activeTab === "holdings"
                  ? "My holdings — sell / hold advice"
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
        <div className="header-actions">
          {!isMobileLayout && <ViewModeToggle mode={viewMode} onChange={changeViewMode} />}
          {activeTab === "intraday" && (
            <IntradayReportDownload compact />
          )}
          {activeTab === "dashboard" && (
            <>
              <span className="badge live">Monitoring</span>
              <button className="btn btn-ghost" onClick={handleScan} disabled={scanning}>
                {scanning ? "Scanning…" : "Scan now"}
              </button>
            </>
          )}
        </div>
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
        ) : activeTab === "intraday" ? (
          <IntradayPanel />
        ) : activeTab === "holdings" ? (
          <HoldingsPanel
            market={activeMarket}
            onMarketChange={handleMarketChange}
            holdingsCounts={holdingsCounts}
            onHoldingsChange={loadHoldings}
          />
        ) : (
          <>
            {isMobileLayout && selected && (
              <button
                type="button"
                className="btn btn-ghost mobile-back-btn"
                onClick={() => {
                  setSelected(null);
                  setStockDetail(null);
                  setDetailError("");
                }}
              >
                ← Back to list
              </button>
            )}

            {loading && <div className="loading-hint">Loading chart…</div>}

            {detailError && (
              <div className="error content-error">{detailError}</div>
            )}

            {showDetail ? (
              <StockDetailView
                detail={stockDetail}
                period={period}
                onPeriodChange={setPeriod}
              />
            ) : (
              <>
                <h2 className="section-title">
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
    </>
  );

  return (
    <div className={`app-shell view-mode-${viewMode}`}>
      {isMobileLayout ? (
        <div className="mobile-layout">
          <MobileToolbar
            activeMarket={activeMarket}
            wishlist={wishlist}
            onMarketChange={handleMarketChange}
            viewMode={viewMode}
            onViewModeChange={changeViewMode}
          />
          <div className="mobile-body">
            {mobilePanel === "wishlist" ? (
              <aside className="sidebar mobile-sidebar">{sidebarContent}</aside>
            ) : (
              <main className="main mobile-main">{mainContent}</main>
            )}
          </div>
          <nav className="mobile-bottom-nav" aria-label="Main navigation">
            <button
              type="button"
              className={`mobile-nav-btn ${mobilePanel === "wishlist" ? "active" : ""}`}
              onClick={() => setMobilePanel("wishlist")}
            >
              <span className="mobile-nav-icon">★</span>
              Wishlist
            </button>
            <button
              type="button"
              className={`mobile-nav-btn ${mobilePanel === "main" && activeTab === "dashboard" ? "active" : ""}`}
              onClick={() => openMobileTab("dashboard")}
            >
              <span className="mobile-nav-icon">📊</span>
              Dashboard
            </button>
            <button
              type="button"
              className={`mobile-nav-btn ${mobilePanel === "main" && activeTab === "intraday" ? "active" : ""}`}
              onClick={() => openMobileTab("intraday")}
            >
              <span className="mobile-nav-icon">⚡</span>
              Intraday
            </button>
            <button
              type="button"
              className={`mobile-nav-btn ${mobilePanel === "main" && activeTab === "holdings" ? "active" : ""}`}
              onClick={() => openMobileTab("holdings")}
            >
              <span className="mobile-nav-icon">💼</span>
              Holdings
            </button>
            <button
              type="button"
              className={`mobile-nav-btn ${mobilePanel === "main" && activeTab === "history" ? "active" : ""}`}
              onClick={() => openMobileTab("history")}
            >
              <span className="mobile-nav-icon">📈</span>
              History
            </button>
            <button
              type="button"
              className={`mobile-nav-btn ${mobilePanel === "main" && activeTab === "help" ? "active" : ""}`}
              onClick={() => openMobileTab("help")}
            >
              <span className="mobile-nav-icon">?</span>
              Help
            </button>
          </nav>
        </div>
      ) : (
        <div className="app">
          <aside className="sidebar">{sidebarContent}</aside>
          <main className="main">{mainContent}</main>
        </div>
      )}
      <AppFooter />
    </div>
  );
}
