export interface StockSearchResult {
  symbol: string;
  name: string;
  exchange: string;
  type: string;
}

export interface WishlistItem {
  id: number;
  symbol: string;
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
  created_at: string;
  expires_at: string;
  closed_at: string | null;
  current_price?: number | null;
  progress_pct?: number | null;
}

export interface HistoryStats {
  total_signals: number;
  open: number;
  closed: number;
  wins: number;
  losses: number;
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

export const api = {
  getWishlist: () => request<WishlistItem[]>("/wishlist"),
  addToWishlist: (symbol: string, name?: string) =>
    request<WishlistItem>("/wishlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, name }),
    }),
  removeFromWishlist: (symbol: string) =>
    request<{ ok: boolean }>(`/wishlist/${symbol}`, { method: "DELETE" }),
  getSignals: () =>
    request<{ signals: StockSignal[]; opportunities: StockSignal[]; last_scan: string | null }>("/signals"),
  triggerScan: () =>
    request<{ scanned: number; opportunities: StockSignal[]; signals: StockSignal[] }>("/scan", { method: "POST" }),
  getStockDetail: (symbol: string, period = "6mo", interval = "1d") =>
    request<StockDetail>(`/stocks/${symbol}?period=${period}&interval=${interval}`),
  searchStocks: (q: string) =>
    request<{ query: string; results: StockSearchResult[] }>(`/search?q=${encodeURIComponent(q)}`),
  getHistory: () =>
    request<{ signals: HistoryRecord[]; stats: HistoryStats }>("/history"),
};
