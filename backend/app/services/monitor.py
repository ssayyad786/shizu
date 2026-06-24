import logging

from dataclasses import asdict

from datetime import datetime



from sqlalchemy.orm import Session



from app.database import SessionLocal

from app.models import WishlistItem

from app.services.history import save_buy_signal, update_open_signals

from app.services.market import infer_market

from app.services.market_data import fetch_history

from app.services.signals import TradeSignal, analyze, signal_outlook_to_dict, trade_plan_to_dict



logger = logging.getLogger(__name__)



_latest_signals: dict[str, dict] = {}

_last_scan: datetime | None = None





def _cache_key(symbol: str, market: str) -> str:

    return f"{market.upper()}:{symbol.upper()}"





def remove_cached_signal(symbol: str, market: str) -> None:

    _latest_signals.pop(_cache_key(symbol, market), None)





def get_cached_signals(market: str | None = None) -> tuple[list[dict], datetime | None]:

    signals = sorted(_latest_signals.values(), key=lambda s: s["score"], reverse=True)

    if market:

        signals = [s for s in signals if s.get("market") == market.upper()]

    return signals, _last_scan





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


