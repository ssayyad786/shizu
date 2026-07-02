from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
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
from app.services.intraday_report import build_intraday_report, report_filename, report_to_csv
from app.services.intraday_backtest import (
    MAX_RANGE_TRADING_DAYS,
    backtest_intraday,
    backtest_intraday_range,
    iter_us_trading_days,
    parse_trade_date,
)
from app.services.market import validate_market_symbol
from app.services.search import resolve_symbol_name
from app.services.us_market_hours import market_status_to_dict

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


@router.get("/market-status")
def get_market_status():
    return market_status_to_dict()


@router.get("/signals")
def get_intraday_signals():
    signals, last_scan = get_cached_intraday_signals()
    today_setups = [s for s in signals if s.get("actionable")]
    return {
        "signals": signals,
        "today_setups": today_setups,
        "last_scan": last_scan.isoformat() if last_scan else None,
        "market": market_status_to_dict(),
    }


@router.post("/scan")
def trigger_intraday_scan():
    market = market_status_to_dict()
    if not market["is_open"]:
        signals, last_scan = get_cached_intraday_signals()
        return {
            "scanned": 0,
            "skipped": True,
            "market": market,
            "today_setups": [s for s in signals if s.get("actionable")],
            "signals": signals,
            "last_scan": last_scan.isoformat() if last_scan else None,
        }
    results = scan_intraday_watchlist()
    today_setups = [s for s in results if s.get("actionable")]
    return {
        "scanned": len(results),
        "skipped": False,
        "market": market_status_to_dict(),
        "today_setups": today_setups,
        "signals": results,
    }


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
        "market": market_status_to_dict(),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(records) < total,
    }


@router.get("/report")
def download_intraday_report(
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    """Download full intraday report for algo review (JSON with analysis, or CSV trade log)."""
    report = build_intraday_report(db)
    filename = report_filename(format)
    if format == "csv":
        body = report_to_csv(report)
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    body = json.dumps(report, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/trading-days")
def get_trading_days(
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    """List US trading days in a date range (for range replay progress)."""
    try:
        start_d = parse_trade_date(start)
        end_d = parse_trade_date(end)
        days = iter_us_trading_days(start_d, end_d)
        if not days:
            raise ValueError("No US trading days in this date range")
        if len(days) > MAX_RANGE_TRADING_DAYS:
            raise ValueError(
                f"Range spans {len(days)} trading days; maximum is {MAX_RANGE_TRADING_DAYS}. "
                "Use a shorter range."
            )
        return {
            "start_date": start,
            "end_date": end,
            "trading_days": [d.isoformat() for d in days],
            "count": len(days),
        }
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/backtest")
def run_intraday_backtest(
    symbol: str,
    date: str = Query(..., description="Start date YYYY-MM-DD (or single day)"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD for range replay"),
    db: Session = Depends(get_db),
):
    """Replay current intraday logic on historical bars for a symbol and date or date range."""
    sym = _us_symbol(symbol)
    try:
        if end_date and end_date != date:
            return backtest_intraday_range(sym, date, end_date, db=db)
        return backtest_intraday(sym, date, db=db)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
