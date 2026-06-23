import logging
from dataclasses import asdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import WishlistItem
from app.services.history import save_buy_signal, update_open_signals
from app.services.market_data import fetch_history
from app.services.signals import TradeSignal, analyze, trade_plan_to_dict

logger = logging.getLogger(__name__)

_latest_signals: dict[str, dict] = {}
_last_scan: datetime | None = None


def get_cached_signals() -> tuple[list[dict], datetime | None]:
    signals = sorted(_latest_signals.values(), key=lambda s: s["score"], reverse=True)
    return signals, _last_scan


def scan_symbol(symbol: str, db: Session | None = None) -> dict:
    df = fetch_history(symbol)
    signal: TradeSignal = analyze(symbol, df)
    result = {
        "symbol": signal.symbol,
        "action": signal.action.value,
        "confidence": signal.confidence,
        "price": signal.price,
        "score": signal.score,
        "summary": signal.summary,
        "can_earn": signal.can_earn,
        "indicators": [asdict(i) for i in signal.indicators],
        "trade_plan": trade_plan_to_dict(signal.trade_plan) if signal.trade_plan else None,
        "scanned_at": datetime.utcnow().isoformat(),
    }
    _latest_signals[symbol.upper()] = result

    if db and signal.can_earn:
        save_buy_signal(db, signal)

    return result


def scan_wishlist(db: Session | None = None) -> list[dict]:
    global _last_scan
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        update_open_signals(db)
        items = db.query(WishlistItem).all()
        results = []
        for item in items:
            try:
                results.append(scan_symbol(item.symbol, db=db))
            except Exception as e:
                logger.warning("Failed to scan %s: %s", item.symbol, e)
                results.append({
                    "symbol": item.symbol,
                    "action": "HOLD",
                    "confidence": 0,
                    "price": 0,
                    "score": 0,
                    "summary": f"Scan failed: {e}",
                    "can_earn": False,
                    "indicators": [],
                    "trade_plan": None,
                    "scanned_at": datetime.utcnow().isoformat(),
                })
        _last_scan = datetime.utcnow()
        return results
    finally:
        if close_db:
            db.close()
