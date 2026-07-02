from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import HoldingItem
from app.services.market import MARKETS, validate_market_symbol
from app.services.monitor import (
    get_cached_holdings_signals,
    remove_cached_holding,
    scan_holding,
    scan_holdings,
)
from app.services.search import resolve_symbol_name

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


class HoldingCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    market: str = Field(default="US", pattern=r"^(US|IN)$")
    name: str | None = None
    avg_cost: float = Field(..., gt=0)
    shares: float | None = Field(default=None, gt=0)
    purchase_date: date | None = None


class HoldingUpdate(BaseModel):
    avg_cost: float | None = Field(default=None, gt=0)
    shares: float | None = Field(default=None, gt=0)
    purchase_date: date | None = None
    name: str | None = None


class HoldingItemOut(BaseModel):
    id: int
    symbol: str
    market: str
    name: str | None
    avg_cost: float
    shares: float | None
    purchase_date: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


def _purchase_datetime(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, datetime.min.time())


@router.get("", response_model=list[HoldingItemOut])
def list_holdings(
    market: str | None = Query(None, pattern=r"^(US|IN)$"),
    db: Session = Depends(get_db),
):
    query = db.query(HoldingItem)
    if market:
        query = query.filter(HoldingItem.market == market.upper())
    items = query.order_by(HoldingItem.market, HoldingItem.created_at.desc()).all()

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


@router.post("", response_model=dict, status_code=201)
def add_holding(body: HoldingCreate, db: Session = Depends(get_db)):
    symbol = body.symbol.upper().strip()
    market = body.market.upper()
    if market not in MARKETS:
        raise HTTPException(400, f"market must be one of {', '.join(MARKETS)}")

    try:
        validate_market_symbol(market, symbol)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    existing = (
        db.query(HoldingItem)
        .filter(HoldingItem.symbol == symbol, HoldingItem.market == market)
        .first()
    )
    if existing:
        raise HTTPException(409, f"{symbol} is already in your {market} holdings")

    name = body.name or resolve_symbol_name(symbol)
    item = HoldingItem(
        symbol=symbol,
        market=market,
        name=name,
        avg_cost=round(body.avg_cost, 4),
        shares=round(body.shares, 4) if body.shares is not None else None,
        purchase_date=_purchase_datetime(body.purchase_date),
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"{symbol} is already in your {market} holdings") from e
    db.refresh(item)

    try:
        result = scan_holding(item, db=db)
    except Exception as e:
        result = {"holding": HoldingItemOut.model_validate(item), "summary": f"Added but scan failed: {e}"}

    return result


@router.patch("/{symbol}", response_model=HoldingItemOut)
def update_holding(
    symbol: str,
    body: HoldingUpdate,
    market: str = Query("US", pattern=r"^(US|IN)$"),
    db: Session = Depends(get_db),
):
    item = (
        db.query(HoldingItem)
        .filter(HoldingItem.symbol == symbol.upper(), HoldingItem.market == market.upper())
        .first()
    )
    if not item:
        raise HTTPException(404, f"{symbol} not in {market} holdings")

    if body.avg_cost is not None:
        item.avg_cost = round(body.avg_cost, 4)
    if body.shares is not None:
        item.shares = round(body.shares, 4)
    if body.purchase_date is not None:
        item.purchase_date = _purchase_datetime(body.purchase_date)
    if body.name is not None:
        item.name = body.name

    db.commit()
    db.refresh(item)

    try:
        scan_holding(item, db=db)
    except Exception:
        pass

    return item


@router.delete("/{symbol}")
def remove_holding(
    symbol: str,
    market: str = Query("US", pattern=r"^(US|IN)$"),
    db: Session = Depends(get_db),
):
    item = (
        db.query(HoldingItem)
        .filter(HoldingItem.symbol == symbol.upper(), HoldingItem.market == market.upper())
        .first()
    )
    if not item:
        raise HTTPException(404, f"{symbol} not in {market} holdings")
    remove_cached_holding(item.symbol, item.market)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/signals")
def get_holdings_signals(market: str | None = Query(None, pattern=r"^(US|IN)$")):
    signals, last_scan = get_cached_holdings_signals(market=market)
    sell_alerts = [s for s in signals if s.get("advice", {}).get("recommendation") == "SELL"]
    return {
        "signals": signals,
        "sell_alerts": sell_alerts,
        "last_scan": last_scan.isoformat() if last_scan else None,
    }


@router.post("/scan")
def trigger_holdings_scan():
    results = scan_holdings()
    sell_alerts = [s for s in results if s.get("advice", {}).get("recommendation") == "SELL"]
    return {"scanned": len(results), "sell_alerts": sell_alerts, "signals": results}
