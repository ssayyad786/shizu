from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SignalHistory
from app.services.history import get_history_stats, history_to_dict, update_open_signals
from app.services.market_data import fetch_quote

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(db: Session = Depends(get_db)):
    update_open_signals(db)
    records = db.query(SignalHistory).order_by(SignalHistory.created_at.desc()).all()
    result = []
    for r in records:
        current = None
        if r.status == "open":
            try:
                current = fetch_quote(r.symbol)["price"]
            except Exception:
                pass
        result.append(history_to_dict(r, current))
    return {"signals": result, "stats": get_history_stats(db)}


@router.post("/refresh")
def refresh_outcomes(db: Session = Depends(get_db)):
    updated = update_open_signals(db)
    return {"updated": updated, "stats": get_history_stats(db)}
