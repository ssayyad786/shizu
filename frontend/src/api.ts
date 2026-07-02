export type Market = "US" | "IN";

export interface StockSearchResult {
  symbol: string;
  name: string;
  exchange: string;
  type: string;
}

export interface WishlistItem {
  id: number;
  symbol: string;
  market: Market;
  name: string | null;
  created_at: string;
}

export interface HoldingItem {
  id: number;
  symbol: string;
  market: Market;
  name: string | null;
  avg_cost: number;
  shares: number | null;
  purchase_date: string | null;
  created_at: string;
}

export interface HoldingAdvice {
  recommendation: "SELL" | "HOLD";
  strength: "STRONG" | "MODERATE" | "NEUTRAL" | "BULLISH";
  headline: string;
  summary: string;
  avg_cost: number;
  current_price: number;
  shares: number | null;
  unrealized_pnl_pct: number | null;
  unrealized_pnl: number | null;
  upper_target: number | null;
  lower_target: number | null;
  upper_pct: number | null;
  lower_pct: number | null;
  mid_level: number | null;
  range_note: string | null;
  reasoning: string[];
  confidence: number;
  score: number;
}

export interface HoldingSignal {
  symbol: string;
  market: Market;
  action: string;
  confidence: number;
  price: number;
  score: number;
  summary: string;
  can_earn: boolean;
  indicators: IndicatorSignal[];
  trade_plan?: TradePlan | null;
  outlook?: SignalOutlook | null;
  holding: HoldingItem;
  advice: HoldingAdvice;
  scanned_at?: string;
}

export interface HoldingFormData {
  symbol: string;
  name?: string;
  avg_cost: number;
  shares?: number;
  purchase_date?: string;
}

export interface IntradayWatchlistItem {
  id: number;
  symbol: string;
  name: string | null;
  created_at: string;
}

export interface IntradayTradePlan {
  direction: string;
  entry_price: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  stop_pct: number;
  target_1_pct: number;
  target_2_pct: number;
  risk_reward: number;
  hold_minutes: number;
  expires_at: string;
}

export interface IntradayTradeReason {
  factor: string;
  weight: string;
  bias: string;
  detail: string;
}

export interface IntradayLiveSignal {
  symbol: string;
  direction: string;
  confidence: number;
  price: number;
  score: number;
  summary: string;
  actionable: boolean;
  reasoning: string[];
  why_headline?: string;
  trade_reasons?: IntradayTradeReason[];
  vwap?: number | null;
  rvol?: number | null;
  daily_trend?: string | null;
  indicators: IndicatorSignal[];
  trade_plan?: IntradayTradePlan | null;
  scanned_at?: string;
}

export interface IntradayHistoryRecord {
  id: number;
  symbol: string;
  name?: string | null;
  direction: string;
  entry_price: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  stop_pct: number;
  target_1_pct: number;
  target_2_pct: number;
  risk_reward: number;
  hold_minutes: number;
  confidence: number;
  score: number;
  summary: string;
  reasoning: string[];
  why_headline?: string;
  trade_reasons?: IntradayTradeReason[];
  status: string;
  exit_price: number | null;
  result_pct: number | null;
  success: boolean;
  is_today: boolean;
  trade_date: string;
  created_at: string;
  expires_at: string;
  closed_at: string | null;
  target_hit_at: string | null;
  current_price?: number | null;
  progress_pct?: number | null;
}

export interface IntradayStats {
  total_signals: number;
  open: number;
  closed: number;
  wins: number;
  losses: number;
  target_hits: number;
  stop_hits: number;
  expired: number;
  win_rate: number;
  avg_result_pct: number;
  today_closed: number;
  today_wins: number;
  today_win_rate: number;
}

export interface UsMarketStatus {
  is_open: boolean;
  timezone: string;
  open_time: string;
  close_time: string;
  session_open_at: string | null;
  session_close_at: string | null;
  next_session_open_at: string | null;
  seconds_to_close: number | null;
  seconds_to_open: number | null;
  status_label: string;
  message: string;
}

export interface IntradayBacktestOutcome {
  status: string;
  exit_price: number;
  result_pct: number;
  success: boolean;
  closed_at: string | null;
  mfe_pct: number;
  mae_pct: number;
}

export interface IntradayBacktestResult {
  replay_type?: "shizu_intraday_backtest";
  symbol: string;
  date: string;
  traded: boolean;
  scans_run: number;
  session_bars?: number;
  entry_time_et?: string;
  message?: string;
  signal?: IntradayLiveSignal & { entry_time_et?: string };
  trade_plan?: IntradayTradePlan & {
    stop_pct: number;
    target_1_pct: number;
    target_2_pct: number;
    risk_reward: number;
    hold_minutes: number;
  };
  outcome?: IntradayBacktestOutcome;
  recorded_trade?: IntradayHistoryRecord | null;
  scan_log?: Array<{
    time_et: string;
    actionable: boolean;
    direction: string;
    score: number;
    confidence: number;
    summary: string;
  }>;
}

export interface IntradayBacktestRangeResult {
  replay_type: "shizu_intraday_backtest_range";
  symbol: string;
  start_date: string;
  end_date: string;
  trading_days: number;
  trades: number;
  wins: number;
  losses: number;
  no_trade_days: number;
  win_rate: number;
  total_result_pct: number;
  avg_result_pct: number;
  results: IntradayBacktestResult[];
  notes?: string[];
}

export interface IntradayTradingDays {
  start_date: string;
  end_date: string;
  trading_days: string[];
  count: number;
  max_trading_days: number;
  max_calendar_days: number;
}

export const INTRADAY_MAX_RANGE_TRADING_DAYS = 30;
export const INTRADAY_MAX_RANGE_CALENDAR_DAYS = 90;

export interface IntradayHistoryPage {
  signals: IntradayHistoryRecord[];
  today_trades: IntradayHistoryRecord[];
  stats: IntradayStats;
  market?: UsMarketStatus;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface BulkInvalidSymbol {
  symbol: string;
  reason: string;
}

export interface BulkAddResult {
  added: WishlistItem[];
  skipped: string[];
  invalid: BulkInvalidSymbol[];
}

export interface IndicatorSignal {
  name: string;
  value: number | null;
  signal: string;
  score: number;
  detail: string;
}

export interface TradePlan {
  entry_price: number;
  sell_target: number;
  stop_loss: number;
  target_pct: number;
  stop_pct: number;
  atr: number;
  hold_days: number;
  expires_at: string;
}

export interface SignalOutlook {
  reasoning: string[];
  upper_target: number;
  lower_target: number;
  upper_pct: number;
  lower_pct: number;
  mid_level: number | null;
  range_note: string;
}

export interface StockSignal {
  symbol: string;
  market?: Market;
  action: string;
  confidence: number;
  price: number;
  score: number;
  summary: string;
  can_earn: boolean;
  indicators: IndicatorSignal[];
  trade_plan?: TradePlan | null;
  outlook?: SignalOutlook | null;
  scanned_at?: string;
}

export interface HistoryRecord {
  id: number;
  symbol: string;
  name?: string | null;
  market: Market;
  action: string;
  entry_price: number;
  sell_target: number;
  stop_loss: number;
  target_pct: number;
  stop_pct: number;
  confidence: number;
  score: number;
  summary: string;
  status: string;
  exit_price: number | null;
  result_pct: number | null;
  highest_since: number | null;
  lowest_since: number | null;
  hold_days: number;
  target_hit_at: string | null;
  days_to_target: number | null;
  success: boolean;
  window_open?: boolean;
  created_at: string;
  expires_at: string;
  closed_at: string | null;
  current_price?: number | null;
  progress_pct?: number | null;
}

export interface HistoryStats {
  market: Market | null;
  total_signals: number;
  open: number;
  closed: number;
  wins: number;
  losses: number;
  target_hits?: number;
  stop_hits?: number;
  expired?: number;
  win_rate: number;
  avg_result_pct: number;
}

export interface HistoryPage {
  signals: HistoryRecord[];
  stats: HistoryStats;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface StockDetail {
  quote: {
    symbol: string;
    price: number;
    change: number;
    change_pct: number;
    volume: number;
    currency: string;
  };
  signal: {
    action: string;
    confidence: number;
    score: number;
    summary: string;
    can_earn: boolean;
    trade_plan?: TradePlan | null;
    outlook?: SignalOutlook | null;
    indicators: IndicatorSignal[];
  };
  candles: Candle[];
  indicators: {
    ema9: (number | null)[];
    ema21: (number | null)[];
    rsi: (number | null)[];
    macd: (number | null)[];
    macd_signal: (number | null)[];
    macd_hist: (number | null)[];
    bb_upper: (number | null)[];
    bb_lower: (number | null)[];
    bb_mid: (number | null)[];
  };
  period: string;
  interval: string;
}

const BASE = "/api";

function normalizeMarket(symbol: string, market?: Market): Market {
  if (market === "US" || market === "IN") return market;
  const s = symbol.toUpperCase();
  if (s.endsWith(".NS") || s.endsWith(".BO")) return "IN";
  return "US";
}

function normalizeWishlistItem(item: WishlistItem): WishlistItem {
  return { ...item, market: normalizeMarket(item.symbol, item.market) };
}

function normalizeHoldingItem(item: HoldingItem): HoldingItem {
  return { ...item, market: normalizeMarket(item.symbol, item.market) };
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store", ...options });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg || String(d)).join(", ")
          : res.statusText;
    if (res.status === 504) {
      throw new Error("Server timed out — try again in a moment");
    }
    throw new Error(message || "Request failed");
  }
  return res.json();
}

export type IntradayReportFormat = "json" | "csv";

async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : res.statusText);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const filename = match?.[1] || fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export type StockSelection = { symbol: string; market: Market };

export function currencyForMarket(market: Market): string {
  return market === "IN" ? "₹" : "$";
}

export const api = {
  getWishlist: async (market?: Market) => {
    const items = await request<WishlistItem[]>(
      market ? `/wishlist?market=${market}` : "/wishlist"
    );
    return items.map(normalizeWishlistItem);
  },
  addToWishlist: (symbol: string, market: Market, name?: string) =>
    request<WishlistItem>("/wishlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, market, name }),
    }),
  bulkAddToWishlist: (symbols: string[], market: Market) =>
    request<BulkAddResult>("/wishlist/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbols, market }),
    }),
  removeFromWishlist: (symbol: string, market: Market) =>
    request<{ ok: boolean }>(`/wishlist/${symbol}?market=${market}`, { method: "DELETE" }),
  getSignals: (market?: Market) =>
    request<{
      signals: StockSignal[];
      opportunities: StockSignal[];
      last_scan: string | null;
      scan_in_progress: boolean;
    }>(market ? `/signals?market=${market}` : "/signals"),
  triggerScan: () =>
    request<{ status: "started" | "already_running" }>("/scan", { method: "POST" }),
  scanSymbol: (symbol: string, market: Market) =>
    request<StockSignal>(`/stocks/${encodeURIComponent(symbol)}/scan?market=${market}`, {
      method: "POST",
    }),
  getStockDetail: (symbol: string, period = "6mo", interval = "1d") =>
    request<StockDetail>(`/stocks/${symbol}?period=${period}&interval=${interval}`),
  searchStocks: (q: string) =>
    request<{ query: string; results: StockSearchResult[] }>(`/search?q=${encodeURIComponent(q)}`),
  getHistory: (
    market?: Market,
    opts?: { limit?: number; offset?: number; refresh?: boolean }
  ) => {
    const params = new URLSearchParams();
    if (market) params.set("market", market);
    if (opts?.limit != null) params.set("limit", String(opts.limit));
    if (opts?.offset != null) params.set("offset", String(opts.offset));
    if (opts?.refresh != null) params.set("refresh", opts.refresh ? "true" : "false");
    const qs = params.toString();
    return request<HistoryPage>(`/history${qs ? `?${qs}` : ""}`);
  },
  getHoldings: async (market?: Market) => {
    const items = await request<HoldingItem[]>(
      market ? `/holdings?market=${market}` : "/holdings"
    );
    return items.map(normalizeHoldingItem);
  },
  addHolding: (
    symbol: string,
    market: Market,
    body: { avg_cost: number; shares?: number; purchase_date?: string; name?: string }
  ) =>
    request<HoldingSignal>("/holdings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, market, ...body }),
    }),
  updateHolding: (
    symbol: string,
    market: Market,
    body: { avg_cost?: number; shares?: number; purchase_date?: string; name?: string }
  ) =>
    request<HoldingItem>(`/holdings/${symbol}?market=${market}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  removeHolding: (symbol: string, market: Market) =>
    request<{ ok: boolean }>(`/holdings/${symbol}?market=${market}`, { method: "DELETE" }),
  getHoldingsSignals: (market?: Market) =>
    request<{
      signals: HoldingSignal[];
      sell_alerts: HoldingSignal[];
      last_scan: string | null;
    }>(market ? `/holdings/signals?market=${market}` : "/holdings/signals"),
  triggerHoldingsScan: () =>
    request<{ scanned: number; sell_alerts: HoldingSignal[]; signals: HoldingSignal[] }>(
      "/holdings/scan",
      { method: "POST" }
    ),
  getIntradayWatchlist: () => request<IntradayWatchlistItem[]>("/intraday/watchlist"),
  addIntradaySymbol: (symbol: string, name?: string) =>
    request<IntradayWatchlistItem>("/intraday/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, name }),
    }),
  bulkAddIntraday: (symbols: string[]) =>
    request<{ added: IntradayWatchlistItem[]; skipped: string[]; invalid: BulkInvalidSymbol[] }>(
      "/intraday/watchlist/bulk",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols }),
      }
    ),
  removeIntradaySymbol: (symbol: string) =>
    request<{ ok: boolean }>(`/intraday/watchlist/${symbol}`, { method: "DELETE" }),
  getIntradaySignals: () =>
    request<{
      signals: IntradayLiveSignal[];
      today_setups: IntradayLiveSignal[];
      last_scan: string | null;
      market: UsMarketStatus;
    }>("/intraday/signals"),
  getIntradayMarketStatus: () => request<UsMarketStatus>("/intraday/market-status"),
  triggerIntradayScan: () =>
    request<{
      scanned: number;
      skipped?: boolean;
      today_setups: IntradayLiveSignal[];
      signals: IntradayLiveSignal[];
      market: UsMarketStatus;
    }>("/intraday/scan", { method: "POST" }),
  getIntradayHistory: (opts?: { limit?: number; offset?: number; refresh?: boolean }) => {
    const params = new URLSearchParams();
    if (opts?.limit != null) params.set("limit", String(opts.limit));
    if (opts?.offset != null) params.set("offset", String(opts.offset));
    if (opts?.refresh != null) params.set("refresh", opts.refresh ? "true" : "false");
    const qs = params.toString();
    return request<IntradayHistoryPage>(`/intraday/history${qs ? `?${qs}` : ""}`);
  },
  downloadIntradayReport: (format: IntradayReportFormat = "json") =>
    downloadFile(`/intraday/report?format=${format}`, `shizu_intraday_report.${format}`),
  runIntradayBacktest: (symbol: string, date: string, endDate?: string) => {
    const params = new URLSearchParams({ symbol: symbol.toUpperCase(), date });
    if (endDate && endDate !== date) {
      params.set("end_date", endDate);
    }
    return request<IntradayBacktestResult | IntradayBacktestRangeResult>(`/intraday/backtest?${params}`);
  },
  getIntradayTradingDays: (start: string, end: string) => {
    const params = new URLSearchParams({ start, end });
    return request<IntradayTradingDays>(`/intraday/trading-days?${params}`);
  },
  runIntradayBacktestDay: (symbol: string, date: string, signal?: AbortSignal) => {
    const params = new URLSearchParams({ symbol: symbol.toUpperCase(), date, light: "true" });
    return request<IntradayBacktestResult>(`/intraday/backtest?${params}`, { signal });
  },
};
