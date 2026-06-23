import logging
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.models import SignalHistory
from app.services.market_data import fetch_history
from app.services.signals import SHORT_TERM_HOLD_DAYS, TradeSignal, trade_plan_to_dict

logger = logging.getLogger(__name__)


def _plan_from_signal(signal: TradeSignal) -> dict | None:
    if not signal.trade_plan:
        return None
    return trade_plan_to_dict(signal.trade_plan)


def save_buy_signal(db: Session, signal: TradeSignal) -> SignalHistory | None:
    if not signal.can_earn or not signal.trade_plan:
        return None

    symbol = signal.symbol.upper()
    existing = (
        db.query(SignalHistory)
        .filter(SignalHistory.symbol == symbol, SignalHistory.status == "open")
        .first()
    )
    if existing:
        return None

    plan = signal.trade_plan
    record = SignalHistory(
        symbol=symbol,
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
        hold_days=SHORT_TERM_HOLD_DAYS,
        expires_at=datetime.fromisoformat(plan.expires_at),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("Saved buy signal for %s @ %s, target %s", symbol, plan.entry_price, plan.sell_target)
    return record


def _close_record(
    record: SignalHistory,
    status: str,
    exit_price: float,
    result_pct: float,
    now: datetime,
) -> None:
    record.status = status
    record.exit_price = round(exit_price, 2)
    record.result_pct = round(result_pct, 2)
    record.closed_at = now


def update_open_signals(db: Session) -> int:
    """Check price history since entry and update target/stop/expiry outcomes."""
    open_records = db.query(SignalHistory).filter(SignalHistory.status == "open").all()
    if not open_records:
        return 0

    updated = 0
    now = datetime.utcnow()

    for record in open_records:
        try:
            df = fetch_history(record.symbol, period="3mo", interval="1d")
            entry_date = pd.Timestamp(record.created_at.date())
            mask = df.index >= entry_date
            since = df.loc[mask] if mask.any() else df.tail(1)

            if since.empty:
                continue

            high = float(since["High"].max())
            low = float(since["Low"].min())
            current = float(since["Close"].iloc[-1])

            record.highest_since = round(max(record.highest_since or current, high), 2)
            record.lowest_since = round(min(record.lowest_since or current, low), 2)

            target_hit = high >= record.sell_target
            stop_hit = low <= record.stop_loss

            if target_hit and not stop_hit:
                result = (record.sell_target - record.entry_price) / record.entry_price * 100
                _close_record(record, "target_hit", record.sell_target, result, now)
                updated += 1
            elif stop_hit:
                result = (record.stop_loss - record.entry_price) / record.entry_price * 100
                _close_record(record, "stop_hit", record.stop_loss, result, now)
                updated += 1
            elif now >= record.expires_at:
                result = (current - record.entry_price) / record.entry_price * 100
                status = "expired_win" if result > 0 else "expired_loss"
                _close_record(record, status, current, result, now)
                updated += 1
        except Exception as e:
            logger.warning("Failed to update signal %s for %s: %s", record.id, record.symbol, e)

    if updated:
        db.commit()
    return updated


def history_to_dict(record: SignalHistory, current_price: float | None = None) -> dict:
    progress_pct = None
    if record.status == "open" and current_price:
        progress_pct = round((current_price - record.entry_price) / record.entry_price * 100, 2)

    return {
        "id": record.id,
        "symbol": record.symbol,
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
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "closed_at": record.closed_at.isoformat() if record.closed_at else None,
        "current_price": current_price,
        "progress_pct": progress_pct,
    }


def get_history_stats(db: Session) -> dict:
    closed = db.query(SignalHistory).filter(SignalHistory.status != "open").all()
    open_count = db.query(SignalHistory).filter(SignalHistory.status == "open").count()

    wins = [r for r in closed if r.status == "target_hit" or (r.result_pct and r.result_pct > 0)]
    losses = [r for r in closed if r.status in ("stop_hit", "expired_loss") or (r.result_pct and r.result_pct <= 0)]

    total_closed = len(closed)
    win_rate = round(len(wins) / total_closed * 100, 1) if total_closed else 0
    avg_result = round(sum(r.result_pct or 0 for r in closed) / total_closed, 2) if total_closed else 0

    return {
        "total_signals": total_closed + open_count,
        "open": open_count,
        "closed": total_closed,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "avg_result_pct": avg_result,
    }
