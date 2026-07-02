from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import HoldingItem, HoldingProfile
from app.services.holding_auth import (
    create_access_token,
    get_current_holding_profile,
    hash_password,
    validate_password,
    validate_username,
    verify_password,
)
from app.services.market import MARKETS, validate_market_symbol
from app.services.monitor import (
    get_cached_holdings_signals,
    remove_cached_holding,
    scan_holding,
    scan_holdings_for_profile,
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


class RegisterBody(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8)


class LoginBody(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    username: str
    profile_id: int


class ProfilePublic(BaseModel):
    username: str
    created_at: datetime
    holdings_count: int


def _purchase_datetime(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, datetime.min.time())


def _profile_item_query(db: Session, profile_id: int, symbol: str, market: str) -> HoldingItem | None:
    return (
        db.query(HoldingItem)
        .filter(
            HoldingItem.profile_id == profile_id,
            HoldingItem.symbol == symbol.upper(),
            HoldingItem.market == market.upper(),
        )
        .first()
    )


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
def register_profile(body: RegisterBody, db: Session = Depends(get_db)):
    try:
        username = validate_username(body.username)
        validate_password(body.password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if db.query(HoldingProfile).filter(HoldingProfile.username == username).first():
        raise HTTPException(409, "Username already taken")

    profile = HoldingProfile(username=username, password_hash=hash_password(body.password))
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Username already taken") from e
    db.refresh(profile)
    return AuthResponse(
        token=create_access_token(profile),
        username=profile.username,
        profile_id=profile.id,
    )


@router.post("/auth/login", response_model=AuthResponse)
def login_profile(body: LoginBody, db: Session = Depends(get_db)):
    try:
        username = validate_username(body.username)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    profile = db.query(HoldingProfile).filter(HoldingProfile.username == username).first()
    if not profile or not verify_password(body.password, profile.password_hash):
        raise HTTPException(401, "Invalid username or password")

    return AuthResponse(
        token=create_access_token(profile),
        username=profile.username,
        profile_id=profile.id,
    )


@router.get("/auth/me")
def current_profile(profile: HoldingProfile = Depends(get_current_holding_profile)):
    return {
        "username": profile.username,
        "profile_id": profile.id,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
    }


@router.get("/profiles", response_model=list[ProfilePublic])
def list_public_profiles(db: Session = Depends(get_db)):
    rows = (
        db.query(
            HoldingProfile.username,
            HoldingProfile.created_at,
            func.count(HoldingItem.id).label("holdings_count"),
        )
        .outerjoin(HoldingItem, HoldingItem.profile_id == HoldingProfile.id)
        .group_by(HoldingProfile.id)
        .order_by(HoldingProfile.username)
        .all()
    )
    return [
        ProfilePublic(username=r.username, created_at=r.created_at, holdings_count=r.holdings_count)
        for r in rows
    ]


@router.get("", response_model=list[HoldingItemOut])
def list_holdings(
    market: str | None = Query(None, pattern=r"^(US|IN)$"),
    db: Session = Depends(get_db),
    profile: HoldingProfile = Depends(get_current_holding_profile),
):
    query = db.query(HoldingItem).filter(HoldingItem.profile_id == profile.id)
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
def add_holding(
    body: HoldingCreate,
    db: Session = Depends(get_db),
    profile: HoldingProfile = Depends(get_current_holding_profile),
):
    symbol = body.symbol.upper().strip()
    market = body.market.upper()
    if market not in MARKETS:
        raise HTTPException(400, f"market must be one of {', '.join(MARKETS)}")

    try:
        validate_market_symbol(market, symbol)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if _profile_item_query(db, profile.id, symbol, market):
        raise HTTPException(409, f"{symbol} is already in your {market} holdings")

    name = body.name or resolve_symbol_name(symbol)
    item = HoldingItem(
        profile_id=profile.id,
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
    profile: HoldingProfile = Depends(get_current_holding_profile),
):
    item = _profile_item_query(db, profile.id, symbol, market)
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
    profile: HoldingProfile = Depends(get_current_holding_profile),
):
    item = _profile_item_query(db, profile.id, symbol, market)
    if not item:
        raise HTTPException(404, f"{symbol} not in {market} holdings")
    remove_cached_holding(item.symbol, item.market, profile.id)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/signals")
def get_holdings_signals(
    market: str | None = Query(None, pattern=r"^(US|IN)$"),
    profile: HoldingProfile = Depends(get_current_holding_profile),
):
    signals, last_scan = get_cached_holdings_signals(market=market, profile_id=profile.id)
    sell_alerts = [s for s in signals if s.get("advice", {}).get("recommendation") == "SELL"]
    return {
        "signals": signals,
        "sell_alerts": sell_alerts,
        "last_scan": last_scan.isoformat() if last_scan else None,
    }


@router.post("/scan")
def trigger_holdings_scan(
    db: Session = Depends(get_db),
    profile: HoldingProfile = Depends(get_current_holding_profile),
):
    results = scan_holdings_for_profile(profile.id, db=db)
    sell_alerts = [s for s in results if s.get("advice", {}).get("recommendation") == "SELL"]
    return {"scanned": len(results), "sell_alerts": sell_alerts, "signals": results}
