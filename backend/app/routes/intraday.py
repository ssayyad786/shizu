from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IntradayWatchlistItem
from app.services.intraday_history import (
    INTRADAY_HISTORY_LIMIT,
    get_intraday_stats,
    get_today_trades,
    list_intraday_history,
    update_open_intraday,
)
from app.services.intraday_monitor import (
    get_cached_intraday_signals,
    remove_cached_intraday,
    scan_intraday_watchlist,
)
from app.services.market import validate_market_symbol
from app.services.search import resolve_symbol_name

router = APIRouter(prefix="/api/intraday", tags=["intraday"])


class IntradayWatchlistCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    name: str | None = None


class IntradayWatchlistOut(BaseModel):
    id: int
    symbol: str
    name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


def _us_symbol(symbol: str) -> str:
    symbol = symbol.upper().strip()
    try:
        validate_market_symbol("US", symbol)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        raise HTTPException(400, "Intraday list is US stocks only (no .NS/.BO)")
    return symbol


@router.get("/watchlist", response_model=list[IntradayWatchlistOut])
def list_intraday_watchlist(db: Session = Depends(get_db)):
    items = db.query(IntradayWatchlistItem).order_by(IntradayWatchlistItem.created_at.desc()).all()
    dirty = False
    for item in items:
        if not item.name:
            name = resolve_symbol_name(item.symbol)
            if name:
                item.name = name
                dirty = True
    if dirty:
        db.commit()
    return items


@router.post("/watchlist", response_model=IntradayWatchlistOut, status_code=201)
def add_intraday_symbol(body: IntradayWatchlistCreate, db: Session = Depends(get_db)):
    symbol = _us_symbol(body.symbol)
    existing = db.query(IntradayWatchlistItem).filter(IntradayWatchlistItem.symbol == symbol).first()
    if existing:
        raise HTTPException(409, f"{symbol} is already on the intraday list")

    item = IntradayWatchlistItem(symbol=symbol, name=body.name or resolve_symbol_name(symbol))
    db.add(item)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"{symbol} is already on the intraday list") from e
    db.refresh(item)
    return item


class IntradayBulkCreate(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=200)


@router.post("/watchlist/bulk", status_code=201)
def bulk_add_intraday(body: IntradayBulkCreate, db: Session = Depends(get_db)):
    from app.routes.wishlist import _parse_bulk_symbols

    symbols = _parse_bulk_symbols(body.symbols)
    added = []
    skipped = []
    invalid = []
    for symbol in symbols:
        try:
            sym = _us_symbol(symbol)
        except HTTPException as e:
            invalid.append({"symbol": symbol, "reason": e.detail})
            continue
        if db.query(IntradayWatchlistItem).filter(IntradayWatchlistItem.symbol == sym).first():
            skipped.append(sym)
            continue
        item = IntradayWatchlistItem(symbol=sym, name=resolve_symbol_name(sym))
        db.add(item)
        try:
            db.commit()
            db.refresh(item)
            added.append(item)
        except IntegrityError:
            db.rollback()
            skipped.append(sym)
    return {"added": added, "skipped": skipped, "invalid": invalid}


@router.delete("/watchlist/{symbol}")
def remove_intraday_symbol(symbol: str, db: Session = Depends(get_db)):
    symbol = symbol.upper()
    item = db.query(IntradayWatchlistItem).filter(IntradayWatchlistItem.symbol == symbol).first()
    if not item:
        raise HTTPException(404, f"{symbol} not on intraday list")
    remove_cached_intraday(symbol)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/signals")
def get_intraday_signals():
    signals, last_scan = get_cached_intraday_signals()
    today_setups = [s for s in signals if s.get("actionable")]
    return {
        "signals": signals,
        "today_setups": today_setups,
        "last_scan": last_scan.isoformat() if last_scan else None,
    }


@router.post("/scan")
def trigger_intraday_scan():
    results = scan_intraday_watchlist()
    today_setups = [s for s in results if s.get("actionable")]
    return {"scanned": len(results), "today_setups": today_setups, "signals": results}


@router.get("/history")
def get_intraday_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(True),
    db: Session = Depends(get_db),
):
    if refresh:
        update_open_intraday(db)
    records, total = list_intraday_history(db, limit=limit, offset=offset)
    stats = get_intraday_stats(db)
    today_trades = get_today_trades(db)
    return {
        "signals": records,
        "today_trades": today_trades,
        "stats": stats,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(records) < total,
    }
