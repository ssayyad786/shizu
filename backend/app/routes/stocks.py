from fastapi import APIRouter, HTTPException, Query

from app.services.market import infer_market
from app.services.market_data import df_to_candles, fetch_history, fetch_quote
from app.services.monitor import get_cached_signals, scan_symbol, scan_wishlist
from app.services.search import search_symbols
from app.services.signals import analyze, compute_chart_indicators, trade_plan_to_dict

router = APIRouter(prefix="/api", tags=["stocks"])


@router.get("/search")
def search_stocks(q: str = Query(..., min_length=1, max_length=50)):
    """Search stocks by company name or symbol."""
    try:
        results = search_symbols(q)
        return {"query": q, "results": results}
    except Exception as e:
        raise HTTPException(502, f"Search failed: {e}") from e


@router.get("/signals")
def get_signals(market: str | None = Query(None, pattern=r"^(US|IN)$")):
    signals, last_scan = get_cached_signals(market=market)
    opportunities = [s for s in signals if s.get("can_earn")]
    return {
        "signals": signals,
        "opportunities": opportunities,
        "last_scan": last_scan.isoformat() if last_scan else None,
    }


@router.post("/scan")
def trigger_scan():
    results = scan_wishlist()
    opportunities = [s for s in results if s.get("can_earn")]
    return {"scanned": len(results), "opportunities": opportunities, "signals": results}


@router.get("/stocks/{symbol}")
def get_stock_detail(
    symbol: str,
    period: str = Query("6mo", pattern=r"^(1mo|3mo|6mo|1y|2y|5y)$"),
    interval: str = Query("1d", pattern=r"^(1d|1h|15m)$"),
):
    try:
        df = fetch_history(symbol, period=period, interval=interval)
        quote = fetch_quote(symbol)
        signal = analyze(symbol, df)
        candles = df_to_candles(df)
        indicators = compute_chart_indicators(df)

        return {
            "quote": quote,
            "signal": {
                "action": signal.action.value,
                "confidence": signal.confidence,
                "score": signal.score,
                "summary": signal.summary,
                "can_earn": signal.can_earn,
                "trade_plan": trade_plan_to_dict(signal.trade_plan) if signal.trade_plan else None,
                "indicators": [
                    {"name": i.name, "value": i.value, "signal": i.signal, "score": i.score, "detail": i.detail}
                    for i in signal.indicators
                ],
            },
            "candles": candles,
            "indicators": indicators,
            "period": period,
            "interval": interval,
        }
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/stocks/{symbol}/quote")
def get_quote(symbol: str):
    try:
        return fetch_quote(symbol)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/stocks/{symbol}/scan")
def scan_single(symbol: str, market: str | None = Query(None, pattern=r"^(US|IN)$")):
    try:
        m = market.upper() if market else infer_market(symbol)
        return scan_symbol(symbol, market=m)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
