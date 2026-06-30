"""Persist and track US intraday trade outcomes."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import IntradaySignalHistory, IntradayWatchlistItem
from app.services.intraday_signals import IntradaySignal, trade_plan_to_dict
from app.services.market_data import fetch_quote
from app.services.search import resolve_symbol_name

logger = logging.getLogger(__name__)

INTRADAY_HISTORY_LIMIT = 50


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _today_utc_date() -> datetime:
    return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def _lookup_name(db: Session, symbol: str) -> str | None:
    item = db.query(IntradayWatchlistItem).filter(IntradayWatchlistItem.symbol == symbol.upper()).first()
    if item and item.name:
        return item.name
    return resolve_symbol_name(symbol)


def save_intraday_signal(db: Session, signal: IntradaySignal) -> IntradaySignalHistory | None:
    if not signal.actionable or not signal.trade_plan:
        return None

    symbol = signal.symbol.upper()
    trade_date = _today_utc_date()
    existing = (
        db.query(IntradaySignalHistory)
        .filter(
            IntradaySignalHistory.symbol == symbol,
            IntradaySignalHistory.status == "open",
            IntradaySignalHistory.trade_date >= trade_date,
        )
        .first()
    )
    if existing:
        return None

    plan = signal.trade_plan
    created_at = datetime.utcnow()
    expires_at = datetime.fromisoformat(plan.expires_at.replace("Z", ""))

    record = IntradaySignalHistory(
        symbol=symbol,
        name=_lookup_name(db, symbol),
        direction=plan.direction,
        entry_price=plan.entry_price,
        stop_loss=plan.stop_loss,
        target_1=plan.target_1,
        target_2=plan.target_2,
        stop_pct=plan.stop_pct,
        target_1_pct=plan.target_1_pct,
        target_2_pct=plan.target_2_pct,
        risk_reward=plan.risk_reward,
        hold_minutes=plan.hold_minutes,
        confidence=signal.confidence,
        score=signal.score,
        summary=signal.summary,
        reasoning=json.dumps({
            "headline": signal.why_headline,
            "reasons": signal.trade_reasons or [],
            "bullets": signal.reasoning,
        }),
        status="open",
        highest_since=plan.entry_price,
        lowest_since=plan.entry_price,
        trade_date=trade_date,
        created_at=created_at,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("Saved intraday %s for %s @ %s", plan.direction, symbol, plan.entry_price)
    return record


def _close_record(
    record: IntradaySignalHistory,
    status: str,
    exit_price: float,
    result_pct: float,
    now: datetime,
    *,
    target_hit_at: datetime | None = None,
) -> None:
    record.status = status
    record.exit_price = round(exit_price, 2)
    record.result_pct = round(result_pct, 2)
    record.closed_at = now
    if target_hit_at:
        record.target_hit_at = target_hit_at


def _result_pct_long(entry: float, exit: float) -> float:
    return (exit - entry) / entry * 100


def _result_pct_short(entry: float, exit: float) -> float:
    return (entry - exit) / entry * 100


def _try_live_close(record: IntradaySignalHistory, price: float, now: datetime) -> bool:
    now = _naive_utc(now)
    if now < _naive_utc(record.created_at):
        return False

    entry = record.entry_price
    is_long = record.direction == "LONG"

    if is_long:
        if price <= record.stop_loss:
            _close_record(record, "stop_hit", record.stop_loss, _result_pct_long(entry, record.stop_loss), now)
            return True
        if price >= record.target_2:
            _close_record(
                record, "target_2_hit", record.target_2, _result_pct_long(entry, record.target_2), now, target_hit_at=now
            )
            return True
        if price >= record.target_1:
            _close_record(
                record, "target_hit", record.target_1, _result_pct_long(entry, record.target_1), now, target_hit_at=now
            )
            return True
    else:
        if price >= record.stop_loss:
            _close_record(record, "stop_hit", record.stop_loss, _result_pct_short(entry, record.stop_loss), now)
            return True
        if price <= record.target_2:
            _close_record(
                record, "target_2_hit", record.target_2, _result_pct_short(entry, record.target_2), now, target_hit_at=now
            )
            return True
        if price <= record.target_1:
            _close_record(
                record, "target_hit", record.target_1, _result_pct_short(entry, record.target_1), now, target_hit_at=now
            )
            return True

    if now >= _naive_utc(record.expires_at):
        result = _result_pct_long(entry, price) if is_long else _result_pct_short(entry, price)
        status = "expired_win" if result > 0 else "expired_loss"
        _close_record(record, status, price, result, now)
        return True

    return False


def update_open_intraday(db: Session) -> int:
    now = datetime.utcnow()
    open_rows = db.query(IntradaySignalHistory).filter(IntradaySignalHistory.status == "open").all()
    updated = 0
    dirty = False

    for record in open_rows:
        try:
            quote = fetch_quote(record.symbol)
            price = float(quote["price"])
            entry = record.entry_price
            record.highest_since = round(max(record.highest_since or entry, price), 2)
            record.lowest_since = round(min(record.lowest_since or entry, price), 2)
            dirty = True
            if _try_live_close(record, price, now):
                updated += 1
                dirty = True
        except Exception as e:
            logger.warning("Intraday outcome check failed for %s: %s", record.symbol, e)

    if dirty:
        db.commit()
    return updated


def _parse_reasoning(record: IntradaySignalHistory) -> tuple[str, list[dict], list[str]]:
    why_headline = ""
    trade_reasons: list[dict] = []
    bullets: list[str] = []
    if not record.reasoning:
        return why_headline, trade_reasons, bullets
    try:
        parsed = json.loads(record.reasoning)
        if isinstance(parsed, dict):
            why_headline = parsed.get("headline", "")
            trade_reasons = parsed.get("reasons", [])
            bullets = parsed.get("bullets", [])
            return why_headline, trade_reasons, bullets
        if isinstance(parsed, list):
            return "", [], parsed
    except json.JSONDecodeError:
        pass
    return "", [], [record.reasoning]


def intraday_to_dict(record: IntradaySignalHistory, current_price: float | None = None) -> dict:
    why_headline, trade_reasons, reasoning_bullets = _parse_reasoning(record)
    reasoning = reasoning_bullets

    progress_pct = None
    if record.status == "open" and current_price is not None:
        if record.direction == "LONG":
            progress_pct = round((current_price - record.entry_price) / record.entry_price * 100, 2)
        else:
            progress_pct = round((record.entry_price - current_price) / record.entry_price * 100, 2)

    is_today = _naive_utc(record.trade_date) >= _today_utc_date()
    success = record.status in ("target_hit", "target_2_hit")

    return {
        "id": record.id,
        "symbol": record.symbol,
        "name": record.name,
        "direction": record.direction,
        "entry_price": record.entry_price,
        "stop_loss": record.stop_loss,
        "target_1": record.target_1,
        "target_2": record.target_2,
        "stop_pct": record.stop_pct,
        "target_1_pct": record.target_1_pct,
        "target_2_pct": record.target_2_pct,
        "risk_reward": record.risk_reward,
        "hold_minutes": record.hold_minutes,
        "confidence": record.confidence,
        "score": record.score,
        "summary": record.summary,
        "reasoning": reasoning,
        "why_headline": why_headline,
        "trade_reasons": trade_reasons,
        "status": record.status,
        "exit_price": record.exit_price,
        "result_pct": record.result_pct,
        "success": success,
        "is_today": is_today,
        "trade_date": record.trade_date.isoformat(),
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "closed_at": record.closed_at.isoformat() if record.closed_at else None,
        "target_hit_at": record.target_hit_at.isoformat() if record.target_hit_at else None,
        "current_price": current_price,
        "progress_pct": progress_pct,
    }


def get_today_trades(db: Session) -> list[dict]:
    today_start = _today_utc_date()
    rows = (
        db.query(IntradaySignalHistory)
        .filter(IntradaySignalHistory.trade_date >= today_start)
        .order_by(IntradaySignalHistory.created_at.desc())
        .all()
    )
    out = []
    for r in rows:
        current = None
        if r.status == "open":
            try:
                current = float(fetch_quote(r.symbol)["price"])
            except Exception:
                pass
        out.append(intraday_to_dict(r, current))
    return out


def list_intraday_history(db: Session, limit: int = INTRADAY_HISTORY_LIMIT, offset: int = 0) -> tuple[list[dict], int]:
    base = db.query(IntradaySignalHistory).order_by(IntradaySignalHistory.created_at.desc())
    total = base.count()
    rows = base.offset(offset).limit(limit).all()
    return [intraday_to_dict(r) for r in rows], total


def get_intraday_stats(db: Session) -> dict:
    rows = db.query(IntradaySignalHistory).filter(IntradaySignalHistory.status != "open").all()
    closed = len(rows)
    wins = sum(1 for r in rows if r.status in ("target_hit", "target_2_hit"))
    stops = sum(1 for r in rows if r.status == "stop_hit")
    expired = sum(1 for r in rows if r.status.startswith("expired"))
    sum_pct = sum(r.result_pct or 0 for r in rows)
    today_start = _today_utc_date()
    today_closed = [r for r in rows if _naive_utc(r.trade_date) >= today_start]
    today_wins = sum(1 for r in today_closed if r.status in ("target_hit", "target_2_hit"))

    return {
        "total_signals": db.query(IntradaySignalHistory).count(),
        "open": db.query(IntradaySignalHistory).filter(IntradaySignalHistory.status == "open").count(),
        "closed": closed,
        "wins": wins,
        "losses": closed - wins,
        "target_hits": wins,
        "stop_hits": stops,
        "expired": expired,
        "win_rate": round(wins / closed * 100, 1) if closed else 0.0,
        "avg_result_pct": round(sum_pct / closed, 2) if closed else 0.0,
        "today_closed": len(today_closed),
        "today_wins": today_wins,
        "today_win_rate": round(today_wins / len(today_closed) * 100, 1) if today_closed else 0.0,
    }


def signal_to_api_dict(signal: IntradaySignal) -> dict:
    from dataclasses import asdict

    return {
        "symbol": signal.symbol,
        "direction": signal.direction.value,
        "confidence": signal.confidence,
        "price": signal.price,
        "score": signal.score,
        "summary": signal.summary,
        "actionable": signal.actionable,
        "reasoning": signal.reasoning,
        "why_headline": signal.why_headline,
        "trade_reasons": signal.trade_reasons or [],
        "vwap": signal.vwap,
        "rvol": signal.rvol,
        "daily_trend": signal.daily_trend,
        "indicators": [asdict(i) for i in signal.indicators],
        "trade_plan": trade_plan_to_dict(signal.trade_plan),
    }
