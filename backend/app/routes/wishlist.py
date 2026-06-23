from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WishlistItem

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


class WishlistCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    name: str | None = None


class WishlistItemOut(BaseModel):
    id: int
    symbol: str
    name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[WishlistItemOut])
def list_wishlist(db: Session = Depends(get_db)):
    return db.query(WishlistItem).order_by(WishlistItem.created_at.desc()).all()


@router.post("", response_model=WishlistItemOut, status_code=201)
def add_to_wishlist(body: WishlistCreate, db: Session = Depends(get_db)):
    symbol = body.symbol.upper().strip()
    existing = db.query(WishlistItem).filter(WishlistItem.symbol == symbol).first()
    if existing:
        raise HTTPException(409, f"{symbol} is already in your wishlist")

    item = WishlistItem(symbol=symbol, name=body.name)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{symbol}")
def remove_from_wishlist(symbol: str, db: Session = Depends(get_db)):
    item = db.query(WishlistItem).filter(WishlistItem.symbol == symbol.upper()).first()
    if not item:
        raise HTTPException(404, f"{symbol} not in wishlist")
    db.delete(item)
    db.commit()
    return {"ok": True}
