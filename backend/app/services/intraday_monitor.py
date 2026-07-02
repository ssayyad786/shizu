"""Scan intraday watchlist and cache signals."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import IntradayWatchlistItem
from app.services.intraday_history import save_intraday_signal, signal_to_api_dict, update_open_intraday
from app.services.intraday_signals import analyze_intraday
from app.services.market_data import fetch_history
from app.services.search import resolve_symbol_name
from app.services.us_market_hours import get_us_market_status, market_status_to_dict

logger = logging.getLogger(__name__)

SCAN_INTERVAL_MINUTES = 2
STALE_AFTER_SECONDS = SCAN_INTERVAL_MINUTES * 60 * 3

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


def scan_intraday_symbol(symbol: str, db: Session | None = None, name: str | None = None) -> dict:
    symbol = symbol.upper()
    df_5m = fetch_history(symbol, period="5d", interval="5m")
    df_15m = fetch_history(symbol, period="5d", interval="15m")
    df_1d = fetch_history(symbol, period="1mo", interval="1d")

    signal = analyze_intraday(symbol, df_5m, df_15m, df_1d)
    result = signal_to_api_dict(signal)
    result["scanned_at"] = datetime.utcnow().isoformat()
    result["is_today_setup"] = signal.actionable
    if name:
        result["name"] = name

    _intraday_signals[symbol] = result

    if db and signal.actionable:
        save_intraday_signal(db, signal)

    return result


def scan_intraday_watchlist(db: Session | None = None) -> list[dict]:
    global _last_intraday_scan

    market = get_us_market_status()
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        update_open_intraday(db)

        if not market["is_open"]:
            logger.info("US market closed (%s) — skipping intraday symbol scan", market["status_label"])
            return []

        items = db.query(IntradayWatchlistItem).order_by(IntradayWatchlistItem.symbol).all()
        valid = {i.symbol.upper() for i in items}
        for key in list(_intraday_signals.keys()):
            if key not in valid:
                del _intraday_signals[key]

        results = []
        for item in items:
            display_name = item.name or resolve_symbol_name(item.symbol)
            try:
                result = scan_intraday_symbol(item.symbol, db=db, name=display_name)
                results.append(result)
            except Exception as e:
                logger.warning("Intraday scan failed for %s: %s", item.symbol, e)
                failed = {
                    "symbol": item.symbol,
                    "name": display_name,
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


def _parse_scanned_at(scanned_at: str | None) -> datetime | None:
    if not scanned_at:
        return None
    try:
        dt = datetime.fromisoformat(scanned_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _scan_age_seconds(scanned_at: str | None) -> int | None:
    dt = _parse_scanned_at(scanned_at)
    if dt is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))


def _is_scan_failed(signal: dict | None) -> bool:
    if not signal:
        return False
    summary = signal.get("summary") or ""
    return summary.startswith("Scan failed")


def classify_scan_state(signal: dict | None, market_open: bool) -> str:
    """fresh | stale | failed | never | cached"""
    if signal is None:
        return "never"
    if _is_scan_failed(signal):
        return "failed"
    age = _scan_age_seconds(signal.get("scanned_at"))
    if age is None:
        return "never"
    if not market_open:
        return "cached"
    if age > STALE_AFTER_SECONDS:
        return "stale"
    return "fresh"


def build_intraday_signals_payload(db: Session) -> dict:
    """Merge watchlist with cached scans and attach per-symbol scan health."""
    market = market_status_to_dict()
    items = db.query(IntradayWatchlistItem).order_by(IntradayWatchlistItem.symbol).all()
    cached, last_scan = get_cached_intraday_signals()
    cache_by_symbol = {s["symbol"].upper(): s for s in cached}

    counts = {"fresh": 0, "stale": 0, "failed": 0, "never": 0, "cached": 0}
    signals: list[dict] = []

    for item in items:
        sym = item.symbol.upper()
        display_name = item.name or resolve_symbol_name(item.symbol)
        cached_signal = cache_by_symbol.get(sym)
        state = classify_scan_state(cached_signal, market["is_open"])
        counts[state] += 1

        if cached_signal:
            row = {
                **cached_signal,
                "name": cached_signal.get("name") or display_name,
                "scan_state": state,
                "scan_age_sec": _scan_age_seconds(cached_signal.get("scanned_at")),
            }
        else:
            row = {
                "symbol": sym,
                "name": display_name,
                "direction": "HOLD",
                "confidence": 0,
                "price": 0,
                "score": 0,
                "summary": (
                    "Not scanned yet — next run within ~2 minutes while market is open."
                    if market["is_open"]
                    else "Market closed — scans resume at next US session open."
                ),
                "actionable": False,
                "reasoning": [],
                "indicators": [],
                "trade_plan": None,
                "scanned_at": None,
                "scan_state": state,
                "scan_age_sec": None,
            }
        signals.append(row)

    signals.sort(
        key=lambda s: (
            0 if s.get("actionable") else 1,
            {"failed": 0, "never": 1, "stale": 2, "fresh": 3, "cached": 4}.get(s.get("scan_state", "never"), 5),
            -abs(s.get("score", 0)),
            s.get("symbol", ""),
        )
    )

    return {
        "signals": signals,
        "today_setups": [s for s in signals if s.get("actionable")],
        "last_scan": last_scan.isoformat() if last_scan else None,
        "market": market,
        "scan_summary": {
            "watchlist_count": len(items),
            "scanned_count": len(items) - counts["never"],
            "fresh_count": counts["fresh"],
            "stale_count": counts["stale"],
            "failed_count": counts["failed"],
            "never_count": counts["never"],
            "cached_count": counts["cached"],
            "interval_minutes": SCAN_INTERVAL_MINUTES,
            "stale_after_minutes": STALE_AFTER_SECONDS // 60,
            "market_open": market["is_open"],
        },
    }
