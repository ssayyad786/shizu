"""Scan intraday watchlist and cache signals."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import IntradayWatchlistItem
from app.services.intraday_history import save_intraday_signal, signal_to_api_dict, update_open_intraday
from app.services.intraday_signals import analyze_intraday
from app.services.market_data import fetch_history

logger = logging.getLogger(__name__)

_intraday_signals: dict[str, dict] = {}
_last_intraday_scan: datetime | None = None


def get_cached_intraday_signals() -> tuple[list[dict], datetime | None]:
    signals = sorted(
        _intraday_signals.values(),
        key=lambda s: (
            0 if s.get("actionable") else 1,
            -abs(s.get("score", 0)),
        ),
    )
    return signals, _last_intraday_scan


def remove_cached_intraday(symbol: str) -> None:
    _intraday_signals.pop(symbol.upper(), None)


def scan_intraday_symbol(symbol: str, db: Session | None = None) -> dict:
    symbol = symbol.upper()
    df_5m = fetch_history(symbol, period="5d", interval="5m")
    df_15m = fetch_history(symbol, period="5d", interval="15m")
    df_1d = fetch_history(symbol, period="1mo", interval="1d")

    signal = analyze_intraday(symbol, df_5m, df_15m, df_1d)
    result = signal_to_api_dict(signal)
    result["scanned_at"] = datetime.utcnow().isoformat()
    result["is_today_setup"] = signal.actionable

    _intraday_signals[symbol] = result

    if db and signal.actionable:
        save_intraday_signal(db, signal)

    return result


def scan_intraday_watchlist(db: Session | None = None) -> list[dict]:
    global _last_intraday_scan

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        update_open_intraday(db)
        items = db.query(IntradayWatchlistItem).order_by(IntradayWatchlistItem.symbol).all()
        valid = {i.symbol.upper() for i in items}
        for key in list(_intraday_signals.keys()):
            if key not in valid:
                del _intraday_signals[key]

        results = []
        for item in items:
            try:
                results.append(scan_intraday_symbol(item.symbol, db=db))
            except Exception as e:
                logger.warning("Intraday scan failed for %s: %s", item.symbol, e)
                failed = {
                    "symbol": item.symbol,
                    "direction": "HOLD",
                    "confidence": 0,
                    "price": 0,
                    "score": 0,
                    "summary": f"Scan failed: {e}",
                    "actionable": False,
                    "reasoning": [],
                    "indicators": [],
                    "trade_plan": None,
                    "scanned_at": datetime.utcnow().isoformat(),
                    "is_today_setup": False,
                }
                _intraday_signals[item.symbol.upper()] = failed
                results.append(failed)

        _last_intraday_scan = datetime.utcnow()
        return results
    finally:
        if close_db:
            db.close()
