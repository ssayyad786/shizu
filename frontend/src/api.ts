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
  scanned_at?: string;
}

export interface HistoryRecord {
  id: number;
  symbol: string;
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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export function currencyForMarket(market: Market): string {
  return market === "IN" ? "₹" : "$";
}

export const api = {
  getWishlist: (market?: Market) =>
    request<WishlistItem[]>(market ? `/wishlist?market=${market}` : "/wishlist"),
  addToWishlist: (symbol: string, market: Market, name?: string) =>
    request<WishlistItem>("/wishlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, market, name }),
    }),
  removeFromWishlist: (symbol: string, market: Market) =>
    request<{ ok: boolean }>(`/wishlist/${symbol}?market=${market}`, { method: "DELETE" }),
  getSignals: (market?: Market) =>
    request<{ signals: StockSignal[]; opportunities: StockSignal[]; last_scan: string | null }>(
      market ? `/signals?market=${market}` : "/signals"
    ),
  triggerScan: () =>
    request<{ scanned: number; opportunities: StockSignal[]; signals: StockSignal[] }>("/scan", { method: "POST" }),
  getStockDetail: (symbol: string, period = "6mo", interval = "1d") =>
    request<StockDetail>(`/stocks/${symbol}?period=${period}&interval=${interval}`),
  searchStocks: (q: string) =>
    request<{ query: string; results: StockSearchResult[] }>(`/search?q=${encodeURIComponent(q)}`),
  getHistory: (market?: Market) =>
    request<{ signals: HistoryRecord[]; stats: HistoryStats }>(
      market ? `/history?market=${market}` : "/history"
    ),
};
