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

    hold_days = estimated trading sessions (Mon–Fri) to reach target, max 10.
    Daily bars on the expiry day still count toward target/stop.
    """
    return add_trading_days(created_at, hold_days)


def add_trading_days(start: datetime, trading_days: int) -> datetime:
    """Add N weekday sessions (Mon–Fri). Exchange holidays are not modeled."""
    if trading_days < 1:
        trading_days = 1
    d = start.date()
    added = 0
    while added < trading_days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return datetime.combine(d, time(23, 59, 59))


def bar_end_from_ts(ts) -> datetime:
    """End of the UTC calendar day for a daily price bar."""
    import pandas as pd

    bar_date = pd.Timestamp(ts).date()
    return datetime.combine(bar_date, time(23, 59, 59))
