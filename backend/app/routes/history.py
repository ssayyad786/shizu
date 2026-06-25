from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SignalHistory
from app.services.history import (
    backfill_history_names,
    get_history_stats,
    history_to_dict,
    update_open_signals,
)
from app.services.market_data import fetch_quote

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(
    market: str | None = Query(None, pattern=r"^(US|IN)$"),
    db: Session = Depends(get_db),
):
    update_open_signals(db)
    backfill_history_names(db)
    query = db.query(SignalHistory)
    if market:
        query = query.filter(SignalHistory.market == market.upper())
    records = query.order_by(SignalHistory.created_at.desc()).all()
    quote_cache: dict[str, float | None] = {}
    result = []
    for r in records:
        current = None
        if r.status == "open":
            sym = r.symbol.upper()
            if sym not in quote_cache:
                try:
                    quote_cache[sym] = float(fetch_quote(sym)["price"])
                except Exception:
                    quote_cache[sym] = None
            current = quote_cache[sym]
        result.append(history_to_dict(r, current))
    return {"signals": result, "stats": get_history_stats(db, market=market)}


@router.post("/refresh")
def refresh_outcomes(
    market: str | None = Query(None, pattern=r"^(US|IN)$"),
    db: Session = Depends(get_db),
):
    updated = update_open_signals(db)
    return {"updated": updated, "stats": get_history_stats(db, market=market)}
