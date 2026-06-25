from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WishlistItem(Base):
    __tablename__ = "wishlist"
    __table_args__ = (UniqueConstraint("symbol", "market", name="uq_wishlist_symbol_market"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market: Mapped[str] = mapped_column(String(4), default="US", index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SignalHistory(Base):
    """Saved short-term buy signals with targets and outcome tracking."""

    __tablename__ = "signal_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market: Mapped[str] = mapped_column(String(4), default="US", index=True)
    action: Mapped[str] = mapped_column(String(20))
    entry_price: Mapped[float] = mapped_column(Float)
    sell_target: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target_pct: Mapped[float] = mapped_column(Float)
    stop_pct: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    highest_since: Mapped[float | None] = mapped_column(Float, nullable=True)
    lowest_since: Mapped[float | None] = mapped_column(Float, nullable=True)
    hold_days: Mapped[int] = mapped_column(default=10)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_hit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    days_to_target: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MarketTradeStats(Base):
    """Cumulative stats for trades removed from history after retention period."""

    __tablename__ = "market_trade_stats"

    market: Mapped[str] = mapped_column(String(4), primary_key=True)
    closed_count: Mapped[int] = mapped_column(default=0)
    target_hits: Mapped[int] = mapped_column(default=0)
    stop_hits: Mapped[int] = mapped_column(default=0)
    expired: Mapped[int] = mapped_column(default=0)
    sum_result_pct: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
