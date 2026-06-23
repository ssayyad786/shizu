"""US vs Indian market helpers."""

from datetime import datetime, time, timedelta

MARKETS = ("US", "IN")

INDIAN_EXCHANGES = frozenset({"NSI", "BSE", "NSE", "BOM", "NSEI"})


def infer_market(symbol: str, exchange: str | None = None) -> str:
    s = symbol.upper().strip()
    if s.endswith(".NS") or s.endswith(".BO"):
        return "IN"
    if exchange and exchange.upper() in INDIAN_EXCHANGES:
        return "IN"
    return "US"


def validate_market_symbol(market: str, symbol: str) -> None:
    """Raise ValueError if symbol does not belong on the given wishlist."""
    market = market.upper()
    detected = infer_market(symbol)
    if market == "IN" and detected != "IN":
        raise ValueError(
            "Indian wishlist requires NSE/BSE symbols (e.g. RELIANCE.NS, TCS.NS)"
        )
    if market == "US" and detected == "IN":
        raise ValueError("US wishlist cannot include Indian exchange symbols")


def currency_for_market(market: str) -> str:
    return "INR" if market.upper() == "IN" else "USD"


def trade_window_end(created_at: datetime, hold_days: int) -> datetime:
    """
    End of the hold window for daily-bar outcome checks.

    Uses calendar days: a signal on day D expires at end of day (D + hold_days).
    Daily bars on that last day still count toward target/stop.
    """
    last_date = created_at.date() + timedelta(days=hold_days)
    return datetime.combine(last_date, time(23, 59, 59))


def bar_end_from_ts(ts) -> datetime:
    """End of the UTC calendar day for a daily price bar."""
    import pandas as pd

    bar_date = pd.Timestamp(ts).date()
    return datetime.combine(bar_date, time(23, 59, 59))
