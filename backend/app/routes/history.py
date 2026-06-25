from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.history import (
    HISTORY_DEFAULT_LIMIT,
    HISTORY_MAX_LIMIT,
    backfill_history_names,
    get_history_stats,
    list_history_page,
    maybe_purge_old_history,
    records_to_dicts,
    update_open_signals,
)

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(
    market: str | None = Query(None, pattern=r"^(US|IN)$"),
    limit: int = Query(HISTORY_DEFAULT_LIMIT, ge=1, le=HISTORY_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(True, description="Run outcome checks (Yahoo calls for open trades only)"),
    db: Session = Depends(get_db),
):
    if refresh:
        update_open_signals(db)
        backfill_history_names(db)

    maybe_purge_old_history(db)

    records, total = list_history_page(db, market, limit, offset)
    signals = records_to_dicts(records)
    return {
        "signals": signals,
        "stats": get_history_stats(db, market=market),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(signals) < total,
    }


@router.post("/refresh")
def refresh_outcomes(
    market: str | None = Query(None, pattern=r"^(US|IN)$"),
    db: Session = Depends(get_db),
):
    updated = update_open_signals(db)
    return {"updated": updated, "stats": get_history_stats(db, market=market)}
