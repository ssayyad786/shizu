import requests

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"


def search_symbols(query: str, limit: int = 8) -> list[dict]:
    params = {
        "q": query.strip(),
        "quotesCount": limit,
        "newsCount": 0,
        "enableFuzzyQuery": True,
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for quote in data.get("quotes", []):
        symbol = quote.get("symbol")
        if not symbol:
            continue

        quote_type = quote.get("quoteType", "")
        if quote_type not in ("EQUITY", "ETF", "MUTUALFUND"):
            continue

        name = quote.get("longname") or quote.get("shortname") or symbol
        exchange = quote.get("exchange") or quote.get("exchDisp") or ""

        results.append({
            "symbol": symbol,
            "name": name,
            "exchange": exchange,
            "type": quote_type,
        })

    return results[:limit]


def resolve_symbol_name(symbol: str) -> str | None:
    """Look up company name for a symbol (used when add/bulk omits name)."""
    sym = symbol.upper().strip()
    if not sym:
        return None

    try:
        for result in search_symbols(sym, limit=8):
            if result["symbol"].upper() == sym:
                return result["name"]
    except Exception:
        pass

    try:
        import yfinance as yf

        ticker = yf.Ticker(sym)
        info = ticker.info or {}
        return info.get("longName") or info.get("shortName")
    except Exception:
        return None
