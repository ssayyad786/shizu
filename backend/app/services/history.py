import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.models import SignalHistory, WishlistItem
from app.services.market import bar_end_from_ts, trade_window_end
from app.services.market_data import fetch_history, fetch_quote
from app.services.search import resolve_symbol_name
from app.services.signals import TradeSignal

logger = logging.getLogger(__name__)


def _lookup_symbol_name(db: Session, symbol: str, market: str) -> str | None:
    item = (
        db.query(WishlistItem)
        .filter(WishlistItem.symbol == symbol.upper(), WishlistItem.market == market.upper())
        .first()
    )
    if item and item.name:
        return item.name
    return resolve_symbol_name(symbol)


def _ensure_record_name(db: Session, record: SignalHistory) -> bool:
    if record.name:
        return False
    name = _lookup_symbol_name(db, record.symbol, record.market)
    if name:
        record.name = name
        return True
    return False


def backfill_history_names(db: Session) -> int:
    updated = 0
    for record in db.query(SignalHistory).filter(SignalHistory.name.is_(None)).all():
        if _ensure_record_name(db, record):
            updated += 1
    if updated:
        db.commit()
    return updated


def save_buy_signal(db: Session, signal: TradeSignal, market: str = "US") -> SignalHistory | None:
    if not signal.can_earn or not signal.trade_plan:
        return None

    symbol = signal.symbol.upper()
    market = market.upper()
    existing = (
        db.query(SignalHistory)
        .filter(
            SignalHistory.symbol == symbol,
            SignalHistory.market == market,
            SignalHistory.status == "open",
        )
        .first()
    )
    if existing:
        return None

    plan = signal.trade_plan
    created_at = datetime.utcnow()
    expires_at = trade_window_end(created_at, plan.hold_days)
    company_name = _lookup_symbol_name(db, symbol, market)

    record = SignalHistory(
        symbol=symbol,
        market=market,
        name=company_name,
        action=signal.action.value,
        entry_price=plan.entry_price,
        sell_target=plan.sell_target,
        stop_loss=plan.stop_loss,
        target_pct=plan.target_pct,
        stop_pct=plan.stop_pct,
        confidence=signal.confidence,
        score=signal.score,
        summary=signal.summary,
        status="open",
        highest_since=plan.entry_price,
        lowest_since=plan.entry_price,
        hold_days=plan.hold_days,
        created_at=created_at,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(
        "Saved %s buy signal for %s @ %s, target %s, window until %s",
        market,
        symbol,
        plan.entry_price,
        plan.sell_target,
        expires_at.isoformat(),
    )
    return record


def _close_record(
    record: SignalHistory,
    status: str,
    exit_price: float,
    result_pct: float,
    now: datetime,
    *,
    target_hit_at: datetime | None = None,
    days_to_target: int | None = None,
) -> None:
    record.status = status
    record.exit_price = round(exit_price, 2)
    record.result_pct = round(result_pct, 2)
    record.closed_at = now
    if target_hit_at is not None:
        record.target_hit_at = target_hit_at
    if days_to_target is not None:
        record.days_to_target = days_to_target


def _naive_utc(dt: datetime) -> datetime:
    """Normalize datetimes for safe comparison (SQLite may return aware values)."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _history_since_entry(df: pd.DataFrame, created_at: datetime) -> pd.DataFrame:
    """Daily bars on or after the signal date (timezone-safe)."""
    if df.empty:
        return df
    work = df.copy()
    if getattr(work.index, "tz", None) is not None:
        work.index = work.index.tz_convert("UTC").tz_localize(None)
    entry_date = pd.Timestamp(_naive_utc(created_at).date())
    mask = work.index.normalize() >= entry_date
    return work.loc[mask] if mask.any() else pd.DataFrame()


def _apply_live_price(record: SignalHistory, price: float, now: datetime) -> bool:
    """Update high/low extrema and close if live price hits target or stop."""
    entry = record.entry_price
    new_high = round(max(record.highest_since or entry, price), 2)
    new_low = round(min(record.lowest_since or entry, price), 2)
    record.highest_since = new_high
    record.lowest_since = new_low
    return _try_live_close(record, price, now)


def _days_in_window(created: datetime, hit_at: datetime) -> int:
    return max((_naive_utc(hit_at).date() - _naive_utc(created).date()).days, 0)


def _try_live_close(record: SignalHistory, price: float, now: datetime) -> bool:
    """
    Close open trade using latest price (intraday / live).
    Runs after signal time so same-day moves count once the signal exists.
    """
    now = _naive_utc(now)
    created = _naive_utc(record.created_at)
    expires = _naive_utc(record.expires_at)

    if now < created or now > expires:
        return False

    if price <= record.stop_loss:
        result = (record.stop_loss - record.entry_price) / record.entry_price * 100
        _close_record(record, "stop_hit", record.stop_loss, result, now)
        return True

    if price >= record.sell_target:
        result = (record.sell_target - record.entry_price) / record.entry_price * 100
        _close_record(
            record,
            "target_hit",
            record.sell_target,
            result,
            now,
            target_hit_at=now,
            days_to_target=_days_in_window(record.created_at, now),
        )
        return True

    return False


def _evaluate_bars(record: SignalHistory, since: pd.DataFrame, now: datetime) -> bool:
    """
    Walk daily bars in time order.

    Rules (daily data):
    - Skip stop/target on the signal day (bar includes pre-signal prices).
    - Success only if target is hit on a bar ending on or before expires_at.
    - Target after the window does not count.
    """
    created = _naive_utc(record.created_at)
    expires = _naive_utc(record.expires_at)
    now = _naive_utc(now)
    signal_day = created.date()
    last_in_window_close: float | None = None

    for ts, row in since.iterrows():
        bar_end = bar_end_from_ts(ts)
        bar_date = bar_end.date()

        if bar_date < signal_day:
            continue

        close = float(row["Close"])
        if bar_end <= expires:
            last_in_window_close = close

        # Outcome checks from the day after the signal (next session onward).
        if bar_date <= signal_day:
            continue

        low = float(row["Low"])
        high = float(row["High"])

        if bar_end <= expires:
            if low <= record.stop_loss:
                result = (record.stop_loss - record.entry_price) / record.entry_price * 100
                _close_record(record, "stop_hit", record.stop_loss, result, now)
                return True

            if high >= record.sell_target:
                result = (record.sell_target - record.entry_price) / record.entry_price * 100
                _close_record(
                    record,
                    "target_hit",
                    record.sell_target,
                    result,
                    now,
                    target_hit_at=bar_end,
                    days_to_target=_days_in_window(created, bar_end),
                )
                return True
            continue

        exit_price = last_in_window_close if last_in_window_close is not None else close
        result = (exit_price - record.entry_price) / record.entry_price * 100
        status = "expired_win" if result > 0 else "expired_loss"
        _close_record(record, status, exit_price, result, now)
        return True

    if now >= expires:
        exit_price = last_in_window_close
        if exit_price is None and not since.empty:
            exit_price = float(since["Close"].iloc[-1])
        if exit_price is None:
            exit_price = record.entry_price
        result = (exit_price - record.entry_price) / record.entry_price * 100
        status = "expired_win" if result > 0 else "expired_loss"
        _close_record(record, status, exit_price, result, now)
        return True

    return False


def update_open_signals(db: Session) -> int:
    """Check price history since entry and update target/stop/expiry outcomes."""
    open_records = db.query(SignalHistory).filter(SignalHistory.status == "open").all()
    if not open_records:
        return 0

    updated = 0
    dirty = False
    now = datetime.utcnow()

    for record in open_records:
        current: float | None = None
        try:
            current = float(fetch_quote(record.symbol)["price"])
        except Exception as e:
            logger.warning("Quote failed for %s: %s", record.symbol, e)

        if current is not None:
            try:
                if _apply_live_price(record, current, now):
                    updated += 1
                    dirty = True
                    continue
                dirty = True
            except Exception as e:
                logger.warning("Live update failed for %s: %s", record.symbol, e)

        try:
            df = fetch_history(record.symbol, period="3mo", interval="1d")
            since = _history_since_entry(df, record.created_at)

            if since.empty:
                if current is not None and now >= _naive_utc(record.expires_at):
                    _close_record(record, "expired_loss", record.entry_price, 0.0, now)
                    updated += 1
                    dirty = True
                continue

            if current is not None:
                bar_high = float(since["High"].max())
                bar_low = float(since["Low"].min())
                entry = record.entry_price
                record.highest_since = round(max(record.highest_since or entry, bar_high, current), 2)
                record.lowest_since = round(min(record.lowest_since or entry, bar_low, current), 2)
                dirty = True

            if _evaluate_bars(record, since, now):
                updated += 1
                dirty = True
        except Exception as e:
            logger.warning("Failed to update signal %s for %s: %s", record.id, record.symbol, e)

    if dirty:
        db.commit()
    return updated


def _is_success(record: SignalHistory) -> bool:
    if record.status != "target_hit" or record.target_hit_at is None:
        return False
    return _naive_utc(record.target_hit_at) <= _naive_utc(record.expires_at)


def history_to_dict(record: SignalHistory, current_price: float | None = None) -> dict:
    progress_pct = None
    if record.status == "open" and current_price:
        progress_pct = round((current_price - record.entry_price) / record.entry_price * 100, 2)

    now = datetime.utcnow()
    window_open = record.status == "open" and _naive_utc(now) <= _naive_utc(record.expires_at)

    return {
        "id": record.id,
        "symbol": record.symbol,
        "name": record.name,
        "market": record.market,
        "action": record.action,
        "entry_price": record.entry_price,
        "sell_target": record.sell_target,
        "stop_loss": record.stop_loss,
        "target_pct": record.target_pct,
        "stop_pct": record.stop_pct,
        "confidence": record.confidence,
        "score": record.score,
        "summary": record.summary,
        "status": record.status,
        "exit_price": record.exit_price,
        "result_pct": record.result_pct,
        "highest_since": record.highest_since,
        "lowest_since": record.lowest_since,
        "hold_days": record.hold_days,
        "target_hit_at": record.target_hit_at.isoformat() if record.target_hit_at else None,
        "days_to_target": record.days_to_target,
        "success": _is_success(record),
        "window_open": window_open,
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "closed_at": record.closed_at.isoformat() if record.closed_at else None,
        "current_price": current_price,
        "progress_pct": progress_pct,
    }


def get_history_stats(db: Session, market: str | None = None) -> dict:
    query = db.query(SignalHistory)
    if market:
        query = query.filter(SignalHistory.market == market.upper())

    all_records = query.all()
    closed = [r for r in all_records if r.status != "open"]
    open_count = sum(1 for r in all_records if r.status == "open")

    target_hits = [r for r in closed if _is_success(r)]
    stop_hits = [r for r in closed if r.status == "stop_hit"]
    expired = [r for r in closed if r.status.startswith("expired")]

    total_closed = len(closed)
    win_rate = round(len(target_hits) / total_closed * 100, 1) if total_closed else 0
    avg_result = round(sum(r.result_pct or 0 for r in closed) / total_closed, 2) if total_closed else 0

    return {
        "market": market.upper() if market else None,
        "total_signals": total_closed + open_count,
        "open": open_count,
        "closed": total_closed,
        "wins": len(target_hits),
        "losses": total_closed - len(target_hits),
        "target_hits": len(target_hits),
        "stop_hits": len(stop_hits),
        "expired": len(expired),
        "win_rate": win_rate,
        "avg_result_pct": avg_result,
    }
