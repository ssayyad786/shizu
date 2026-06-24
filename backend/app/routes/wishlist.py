from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WishlistItem
from app.services.market import MARKETS, validate_market_symbol
from app.services.monitor import remove_cached_signal
from app.services.search import resolve_symbol_name

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


class WishlistCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    name: str | None = None
    market: str = Field(default="US", pattern=r"^(US|IN)$")


class WishlistBulkCreate(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=200)
    market: str = Field(default="US", pattern=r"^(US|IN)$")


class WishlistItemOut(BaseModel):
    id: int
    symbol: str
    market: str
    name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BulkInvalidSymbol(BaseModel):
    symbol: str
    reason: str


class BulkAddResult(BaseModel):
    added: list[WishlistItemOut]
    skipped: list[str]
    invalid: list[BulkInvalidSymbol]


@router.get("", response_model=list[WishlistItemOut])
def list_wishlist(
    market: str | None = Query(None, pattern=r"^(US|IN)$"),
    db: Session = Depends(get_db),
):
    query = db.query(WishlistItem)
    if market:
        query = query.filter(WishlistItem.market == market.upper())
    items = query.order_by(WishlistItem.market, WishlistItem.created_at.desc()).all()

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


@router.post("", response_model=WishlistItemOut, status_code=201)
def add_to_wishlist(body: WishlistCreate, db: Session = Depends(get_db)):
    symbol = body.symbol.upper().strip()
    market = body.market.upper()
    if market not in MARKETS:
        raise HTTPException(400, f"market must be one of {', '.join(MARKETS)}")

    try:
        validate_market_symbol(market, symbol)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    existing = (
        db.query(WishlistItem)
        .filter(WishlistItem.symbol == symbol, WishlistItem.market == market)
        .first()
    )
    if existing:
        raise HTTPException(409, f"{symbol} is already in your {market} wishlist")

    name = body.name or resolve_symbol_name(symbol)
    item = WishlistItem(symbol=symbol, market=market, name=name)
    db.add(item)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"{symbol} is already in your {market} wishlist") from e
    db.refresh(item)
    return item


def _parse_bulk_symbols(raw_symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_symbols:
        for part in raw.replace(";", ",").replace("\n", ",").split(","):
            symbol = part.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            out.append(symbol)
    return out


@router.post("/bulk", response_model=BulkAddResult, status_code=201)
def bulk_add_to_wishlist(body: WishlistBulkCreate, db: Session = Depends(get_db)):
    market = body.market.upper()
    if market not in MARKETS:
        raise HTTPException(400, f"market must be one of {', '.join(MARKETS)}")

    symbols = _parse_bulk_symbols(body.symbols)
    if not symbols:
        raise HTTPException(400, "No valid symbols provided")

    added: list[WishlistItem] = []
    skipped: list[str] = []
    invalid: list[BulkInvalidSymbol] = []

    for symbol in symbols:
        try:
            validate_market_symbol(market, symbol)
        except ValueError as e:
            invalid.append(BulkInvalidSymbol(symbol=symbol, reason=str(e)))
            continue

        existing = (
            db.query(WishlistItem)
            .filter(WishlistItem.symbol == symbol, WishlistItem.market == market)
            .first()
        )
        if existing:
            skipped.append(symbol)
            continue

        name = resolve_symbol_name(symbol)
        item = WishlistItem(symbol=symbol, market=market, name=name)
        try:
            db.add(item)
            db.commit()
            db.refresh(item)
            added.append(item)
        except IntegrityError:
            db.rollback()
            skipped.append(symbol)

    return BulkAddResult(
        added=[WishlistItemOut.model_validate(i) for i in added],
        skipped=skipped,
        invalid=invalid,
    )


@router.delete("/{symbol}")
def remove_from_wishlist(
    symbol: str,
    market: str = Query("US", pattern=r"^(US|IN)$"),
    db: Session = Depends(get_db),
):
    item = (
        db.query(WishlistItem)
        .filter(WishlistItem.symbol == symbol.upper(), WishlistItem.market == market.upper())
        .first()
    )
    if not item:
        raise HTTPException(404, f"{symbol} not in {market} wishlist")
    remove_cached_signal(item.symbol, item.market)
    db.delete(item)
    db.commit()
    return {"ok": True}
