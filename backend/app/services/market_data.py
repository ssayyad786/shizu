import yfinance as yf
import pandas as pd


def fetch_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    ticker = yf.Ticker(symbol.upper())
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"No data found for symbol '{symbol}'")
    return df


def fetch_quote(symbol: str) -> dict:
    ticker = yf.Ticker(symbol.upper())
    info = ticker.fast_info
    hist = ticker.history(period="5d")
    if hist.empty:
        raise ValueError(f"No quote data for '{symbol}'")

    prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else float(hist["Close"].iloc[-1])
    current = float(hist["Close"].iloc[-1])
    try:
        live = float(getattr(info, "last_price", 0) or 0)
        if live > 0:
            current = live
    except (TypeError, ValueError):
        pass
    change = current - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0

    return {
        "symbol": symbol.upper(),
        "price": round(current, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "volume": int(hist["Volume"].iloc[-1]),
        "currency": getattr(info, "currency", "USD") or "USD",
    }


def df_to_candles(df: pd.DataFrame) -> list[dict]:
    candles = []
    for idx, row in df.iterrows():
        ts = int(idx.timestamp()) if hasattr(idx, "timestamp") else int(pd.Timestamp(idx).timestamp())
        candles.append({
            "time": ts,
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        })
    return candles
