from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
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


class HoldingProfile(Base):
    """Per-user holdings account — password-protected, isolated holdings data."""

    __tablename__ = "holding_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HoldingItem(Base):
    """Stocks the user owns — used for sell/hold recommendations."""

    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("profile_id", "symbol", "market", name="uq_holdings_profile_symbol_market"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("holding_profiles.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market: Mapped[str] = mapped_column(String(4), default="US", index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avg_cost: Mapped[float] = mapped_column(Float)
    shares: Mapped[float | None] = mapped_column(Float, nullable=True)
    purchase_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IntradayWatchlistItem(Base):
    """US symbols watched for intraday setups."""

    __tablename__ = "intraday_watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IntradaySignalHistory(Base):
    """Intraday trade ideas and outcomes — separate from swing history."""

    __tablename__ = "intraday_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    direction: Mapped[str] = mapped_column(String(8))
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target_1: Mapped[float] = mapped_column(Float)
    target_2: Mapped[float] = mapped_column(Float)
    stop_pct: Mapped[float] = mapped_column(Float)
    target_1_pct: Mapped[float] = mapped_column(Float)
    target_2_pct: Mapped[float] = mapped_column(Float)
    risk_reward: Mapped[float] = mapped_column(Float)
    hold_minutes: Mapped[int] = mapped_column(default=60)
    confidence: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    highest_since: Mapped[float | None] = mapped_column(Float, nullable=True)
    lowest_since: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_hit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trade_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
