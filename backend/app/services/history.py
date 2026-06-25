import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.models import MarketTradeStats, SignalHistory, WishlistItem
from app.services.market import bar_end_from_ts, trade_window_end
from app.services.market_data import fetch_history, fetch_quote
from app.services.search import resolve_symbol_name
from app.services.signals import TradeSignal

logger = logging.getLogger(__name__)

HISTORY_DEFAULT_LIMIT = 30
HISTORY_MAX_LIMIT = 100
NAME_BACKFILL_BATCH = 10
TRADE_RETENTION_DAYS = 30

_last_purge_at: datetime | None = None


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


def backfill_history_names(db: Session, limit: int = NAME_BACKFILL_BATCH) -> int:
    updated = 0
    rows = (
        db.query(SignalHistory)
        .filter(SignalHistory.name.is_(None))
        .order_by(SignalHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    for record in rows:
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

    # One Yahoo quote per symbol (not per row).
    quote_cache: dict[str, float | None] = {}
    for sym in {r.symbol.upper() for r in open_records}:
        try:
            quote_cache[sym] = float(fetch_quote(sym)["price"])
        except Exception as e:
            logger.warning("Quote failed for %s: %s", sym, e)
            quote_cache[sym] = None

    for record in open_records:
        current = quote_cache.get(record.symbol.upper())

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


def _get_or_create_rollup(db: Session, market: str) -> MarketTradeStats:
    market = market.upper()
    row = db.query(MarketTradeStats).filter(MarketTradeStats.market == market).first()
    if row:
        return row
    row = MarketTradeStats(market=market)
    db.add(row)
    db.flush()
    return row


def _accumulate_record_into_rollup(rollup: MarketTradeStats, record: SignalHistory) -> None:
    rollup.closed_count += 1
    if _is_success(record):
        rollup.target_hits += 1
    elif record.status == "stop_hit":
        rollup.stop_hits += 1
    elif record.status.startswith("expired"):
        rollup.expired += 1
    rollup.sum_result_pct += float(record.result_pct or 0.0)


def purge_old_history(db: Session, retention_days: int = TRADE_RETENTION_DAYS) -> int:
    """
    Delete closed trade cards older than retention_days.
    Their stats are merged into market_trade_stats first so totals stay correct.
    Open trades are never deleted.
    """
    global _last_purge_at
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    old_rows = (
        db.query(SignalHistory)
        .filter(
            SignalHistory.status != "open",
            SignalHistory.closed_at.isnot(None),
            SignalHistory.closed_at < cutoff,
        )
        .all()
    )
    if not old_rows:
        _last_purge_at = datetime.utcnow()
        return 0

    by_market: dict[str, list[SignalHistory]] = {}
    for row in old_rows:
        by_market.setdefault(row.market.upper(), []).append(row)

    for market, rows in by_market.items():
        rollup = _get_or_create_rollup(db, market)
        for record in rows:
            _accumulate_record_into_rollup(rollup, record)
            db.delete(record)
        rollup.updated_at = datetime.utcnow()

    db.commit()
    _last_purge_at = datetime.utcnow()
    logger.info("Purged %d closed trade(s) older than %d days", len(old_rows), retention_days)
    return len(old_rows)


def maybe_purge_old_history(db: Session) -> int:
    """Run retention purge at most once every 6 hours."""
    global _last_purge_at
    now = datetime.utcnow()
    if _last_purge_at and (now - _last_purge_at).total_seconds() < 6 * 3600:
        return 0
    return purge_old_history(db)


def _live_market_stats(db: Session, market: str) -> dict:
    from sqlalchemy import func

    base = db.query(SignalHistory).filter(SignalHistory.market == market.upper())
    total = base.count()
    open_count = base.filter(SignalHistory.status == "open").count()
    closed_count = total - open_count
    target_hits = base.filter(
        SignalHistory.status == "target_hit",
        SignalHistory.target_hit_at.isnot(None),
        SignalHistory.target_hit_at <= SignalHistory.expires_at,
    ).count()
    stop_hits = base.filter(SignalHistory.status == "stop_hit").count()
    expired = base.filter(SignalHistory.status.like("expired%")).count()
    sum_result = (
        db.query(func.sum(SignalHistory.result_pct))
        .filter(SignalHistory.market == market.upper(), SignalHistory.status != "open")
        .scalar()
    )
    return {
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "target_hits": target_hits,
        "stop_hits": stop_hits,
        "expired": expired,
        "sum_result_pct": float(sum_result or 0.0),
    }


def _archived_market_stats(db: Session, market: str) -> dict:
    row = db.query(MarketTradeStats).filter(MarketTradeStats.market == market.upper()).first()
    if not row:
        return {
            "closed": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "expired": 0,
            "sum_result_pct": 0.0,
        }
    return {
        "closed": row.closed_count,
        "target_hits": row.target_hits,
        "stop_hits": row.stop_hits,
        "expired": row.expired,
        "sum_result_pct": row.sum_result_pct,
    }


def get_history_stats(db: Session, market: str | None = None) -> dict:
    if not market:
        us = get_history_stats(db, "US")
        ind = get_history_stats(db, "IN")
        closed = us["closed"] + ind["closed"]
        target_hits = (us["target_hits"] or 0) + (ind["target_hits"] or 0)
        sum_pct = 0.0
        for s in (us, ind):
            closed_s = s["closed"]
            if closed_s:
                sum_pct += s["avg_result_pct"] * closed_s
        return {
            "market": None,
            "total_signals": us["total_signals"] + ind["total_signals"],
            "open": us["open"] + ind["open"],
            "closed": closed,
            "wins": target_hits,
            "losses": closed - target_hits,
            "target_hits": target_hits,
            "stop_hits": (us["stop_hits"] or 0) + (ind["stop_hits"] or 0),
            "expired": (us["expired"] or 0) + (ind["expired"] or 0),
            "win_rate": round(target_hits / closed * 100, 1) if closed else 0.0,
            "avg_result_pct": round(sum_pct / closed, 2) if closed else 0.0,
        }

    market = market.upper()
    live = _live_market_stats(db, market)
    arch = _archived_market_stats(db, market)

    closed = arch["closed"] + live["closed"]
    target_hits = arch["target_hits"] + live["target_hits"]
    stop_hits = arch["stop_hits"] + live["stop_hits"]
    expired = arch["expired"] + live["expired"]
    sum_result = arch["sum_result_pct"] + live["sum_result_pct"]
    total_signals = arch["closed"] + live["total"]

    return {
        "market": market,
        "total_signals": total_signals,
        "open": live["open"],
        "closed": closed,
        "wins": target_hits,
        "losses": closed - target_hits,
        "target_hits": target_hits,
        "stop_hits": stop_hits,
        "expired": expired,
        "win_rate": round(target_hits / closed * 100, 1) if closed else 0.0,
        "avg_result_pct": round(sum_result / closed, 2) if closed else 0.0,
        "archived_closed": arch["closed"],
    }


def list_history_page(
    db: Session,
    market: str | None,
    limit: int,
    offset: int,
) -> tuple[list[SignalHistory], int]:
    query = db.query(SignalHistory)
    if market:
        query = query.filter(SignalHistory.market == market.upper())
    total = query.count()
    rows = (
        query.order_by(SignalHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows, total


def records_to_dicts(
    records: list[SignalHistory],
    quote_cache: dict[str, float | None] | None = None,
) -> list[dict]:
    quote_cache = quote_cache or {}
    result = []
    for r in records:
        current = None
        if r.status == "open":
            sym = r.symbol.upper()
            if sym not in quote_cache:
                try:
                    quote_cache[sym] = float(fetch_quote(sym)["price"])
                except Exception:
                    quote_cache[sym] = None
            current = quote_cache[sym]
        result.append(history_to_dict(r, current))
    return result
