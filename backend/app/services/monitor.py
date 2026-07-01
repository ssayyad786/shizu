import logging
import threading
from dataclasses import asdict
from datetime import datetime



from sqlalchemy.orm import Session



from app.database import SessionLocal

from app.models import HoldingItem, WishlistItem

from app.services.history import save_buy_signal, update_open_signals

from app.services.holdings_analysis import signal_to_holding_payload

from app.services.market import infer_market

from app.services.market_data import fetch_history

from app.services.signals import TradeSignal, analyze, signal_outlook_to_dict, trade_plan_to_dict



logger = logging.getLogger(__name__)



_latest_signals: dict[str, dict] = {}

_last_scan: datetime | None = None

_holdings_signals: dict[str, dict] = {}

_last_holdings_scan: datetime | None = None
_scan_lock = threading.Lock()
_scan_in_progress = False


def is_scan_in_progress() -> bool:
    return _scan_in_progress





def _cache_key(symbol: str, market: str) -> str:

    return f"{market.upper()}:{symbol.upper()}"





def remove_cached_signal(symbol: str, market: str) -> None:

    _latest_signals.pop(_cache_key(symbol, market), None)





def remove_cached_holding(symbol: str, market: str) -> None:
    _holdings_signals.pop(_cache_key(symbol, market), None)


def get_cached_signals(market: str | None = None) -> tuple[list[dict], datetime | None]:
    signals = sorted(_latest_signals.values(), key=lambda s: s["score"], reverse=True)
    if market:
        signals = [s for s in signals if s.get("market") == market.upper()]
    return signals, _last_scan


def get_cached_holdings_signals(market: str | None = None) -> tuple[list[dict], datetime | None]:
    signals = sorted(
        _holdings_signals.values(),
        key=lambda s: (
            0 if s.get("advice", {}).get("recommendation") == "SELL" else 1,
            -abs(s.get("score", 0)),
        ),
    )
    if market:
        signals = [s for s in signals if s.get("market") == market.upper()]
    return signals, _last_holdings_scan


def scan_symbol(symbol: str, db: Session | None = None, market: str | None = None) -> dict:

    symbol = symbol.upper()

    market = (market or infer_market(symbol)).upper()

    df = fetch_history(symbol)

    signal: TradeSignal = analyze(symbol, df)

    result = {

        "symbol": signal.symbol,

        "market": market,

        "action": signal.action.value,

        "confidence": signal.confidence,

        "price": signal.price,

        "score": signal.score,

        "summary": signal.summary,

        "can_earn": signal.can_earn,

        "indicators": [asdict(i) for i in signal.indicators],

        "trade_plan": trade_plan_to_dict(signal.trade_plan) if signal.trade_plan else None,

        "outlook": signal_outlook_to_dict(signal.outlook) if signal.outlook else None,

        "scanned_at": datetime.utcnow().isoformat(),

    }

    _latest_signals[_cache_key(symbol, market)] = result



    if db and signal.can_earn:

        save_buy_signal(db, signal, market=market)



    return result





def scan_wishlist(db: Session | None = None) -> list[dict]:

    global _last_scan

    close_db = False

    if db is None:

        db = SessionLocal()

        close_db = True



    try:

        update_open_signals(db)

        items = db.query(WishlistItem).order_by(WishlistItem.market, WishlistItem.symbol).all()

        valid_keys = {_cache_key(i.symbol, i.market) for i in items}

        for key in list(_latest_signals.keys()):

            if key not in valid_keys:

                del _latest_signals[key]



        results = []

        for item in items:

            try:

                results.append(scan_symbol(item.symbol, db=db, market=item.market))

            except Exception as e:

                logger.warning("Failed to scan %s (%s): %s", item.symbol, item.market, e)

                failed = {

                    "symbol": item.symbol,

                    "market": item.market,

                    "action": "HOLD",

                    "confidence": 0,

                    "price": 0,

                    "score": 0,

                    "summary": f"Scan failed: {e}",

                    "can_earn": False,

                    "indicators": [],

                    "trade_plan": None,

                    "scanned_at": datetime.utcnow().isoformat(),

                }

                _latest_signals[_cache_key(item.symbol, item.market)] = failed

                results.append(failed)

        _last_scan = datetime.utcnow()

        return results

    finally:

        if close_db:

            db.close()


def scan_wishlist_background() -> bool:
    """Run a full wishlist scan in a background thread. Returns False if one is already running."""
    global _scan_in_progress

    if not _scan_lock.acquire(blocking=False):
        logger.info("Scan already in progress, skipping duplicate request")
        return False

    def _run():
        global _scan_in_progress
        try:
            _scan_in_progress = True
            scan_wishlist()
            scan_holdings()
        except Exception:
            logger.exception("Background wishlist scan failed")
        finally:
            _scan_in_progress = False
            _scan_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return True


def scan_holding(item: HoldingItem, db: Session | None = None) -> dict:

    symbol = item.symbol.upper()

    market = item.market.upper()

    df = fetch_history(symbol)

    signal: TradeSignal = analyze(symbol, df)

    result = signal_to_holding_payload(signal, item)

    _holdings_signals[_cache_key(symbol, market)] = result

    return result





def scan_holdings(db: Session | None = None) -> list[dict]:

    global _last_holdings_scan

    close_db = False

    if db is None:

        db = SessionLocal()

        close_db = True



    try:

        items = db.query(HoldingItem).order_by(HoldingItem.market, HoldingItem.symbol).all()

        valid_keys = {_cache_key(i.symbol, i.market) for i in items}

        for key in list(_holdings_signals.keys()):

            if key not in valid_keys:

                del _holdings_signals[key]



        results = []

        for item in items:

            try:

                results.append(scan_holding(item, db=db))

            except Exception as e:

                logger.warning("Failed to scan holding %s (%s): %s", item.symbol, item.market, e)

                failed = {

                    "symbol": item.symbol,

                    "market": item.market,

                    "action": "HOLD",

                    "confidence": 0,

                    "price": 0,

                    "score": 0,

                    "summary": f"Scan failed: {e}",

                    "can_earn": False,

                    "indicators": [],

                    "trade_plan": None,

                    "outlook": None,

                    "holding": {

                        "id": item.id,

                        "symbol": item.symbol,

                        "market": item.market,

                        "name": item.name,

                        "avg_cost": item.avg_cost,

                        "shares": item.shares,

                        "purchase_date": item.purchase_date.isoformat() if item.purchase_date else None,

                        "created_at": item.created_at.isoformat() if item.created_at else None,

                    },

                    "advice": {

                        "recommendation": "HOLD",

                        "strength": "NEUTRAL",

                        "headline": f"Could not analyze: {e}",

                        "summary": f"Scan failed: {e}",

                        "avg_cost": item.avg_cost,

                        "current_price": 0,

                        "shares": item.shares,

                        "unrealized_pnl_pct": None,

                        "unrealized_pnl": None,

                        "upper_target": None,

                        "lower_target": None,

                        "upper_pct": None,

                        "lower_pct": None,

                        "mid_level": None,

                        "range_note": None,

                        "reasoning": [],

                        "confidence": 0,

                        "score": 0,

                    },

                    "scanned_at": datetime.utcnow().isoformat(),

                }

                _holdings_signals[_cache_key(item.symbol, item.market)] = failed

                results.append(failed)

        _last_holdings_scan = datetime.utcnow()

        return results

    finally:

        if close_db:

            db.close()


