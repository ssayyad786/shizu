"""Replay intraday logic on historical bars for a symbol + date."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from app.models import IntradaySignalHistory
from app.services.intraday_history import intraday_to_dict
from app.services.intraday_monitor import signal_to_api_dict
from app.services.intraday_signals import (
    ENTRY_CUTOFF_ET,
    ENTRY_EARLIEST_ET,
    SESSION_CLOSE,
    US_EASTERN,
    analyze_intraday,
)
from app.services.market_data import fetch_history
from app.services.us_market_hours import is_us_trading_day
from app.version import __version__

SCAN_INTERVAL_MINUTES = 2


def _to_eastern(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if work.index.tz is None:
        work.index = work.index.tz_localize("UTC")
    work.index = work.index.tz_convert(US_EASTERN)
    return work


def _slice_as_of(df: pd.DataFrame, as_of_et: datetime) -> pd.DataFrame:
    return _to_eastern(df)[_to_eastern(df).index <= as_of_et]


def _session_day_bars(df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    return _to_eastern(df)[_to_eastern(df).index.date == trade_date]


def _parse_trade_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _scan_times(trade_date: date) -> list[datetime]:
    open_dt = datetime.combine(trade_date, ENTRY_EARLIEST_ET, tzinfo=US_EASTERN)
    cutoff_dt = datetime.combine(trade_date, ENTRY_CUTOFF_ET, tzinfo=US_EASTERN)
    times: list[datetime] = []
    t = open_dt
    while t <= cutoff_dt:
        times.append(t)
        t += timedelta(minutes=SCAN_INTERVAL_MINUTES)
    return times


def _result_pct_long(entry: float, exit_price: float) -> float:
    return round((exit_price - entry) / entry * 100, 2)


def _result_pct_short(entry: float, exit_price: float) -> float:
    return round((entry - exit_price) / entry * 100, 2)


def _simulate_outcome(
    direction: str,
    entry: float,
    stop: float,
    target_1: float,
    target_2: float,
    bars: pd.DataFrame,
) -> dict:
    is_long = direction == "LONG"
    highest = entry
    lowest = entry

    if bars.empty:
        return {
            "status": "no_data",
            "exit_price": entry,
            "result_pct": 0.0,
            "success": False,
            "closed_at": None,
            "mfe_pct": 0.0,
            "mae_pct": 0.0,
        }

    for ts, row in bars.iterrows():
        high = float(row["High"])
        low = float(row["Low"])
        highest = max(highest, high)
        lowest = min(lowest, low)

        if is_long:
            if low <= stop:
                return {
                    "status": "stop_hit",
                    "exit_price": stop,
                    "result_pct": _result_pct_long(entry, stop),
                    "success": False,
                    "closed_at": ts.isoformat(),
                    "mfe_pct": round((highest - entry) / entry * 100, 2),
                    "mae_pct": round((lowest - entry) / entry * 100, 2),
                }
            if high >= target_2:
                return {
                    "status": "target_2_hit",
                    "exit_price": target_2,
                    "result_pct": _result_pct_long(entry, target_2),
                    "success": True,
                    "closed_at": ts.isoformat(),
                    "mfe_pct": round((highest - entry) / entry * 100, 2),
                    "mae_pct": round((lowest - entry) / entry * 100, 2),
                }
            if high >= target_1:
                return {
                    "status": "target_hit",
                    "exit_price": target_1,
                    "result_pct": _result_pct_long(entry, target_1),
                    "success": True,
                    "closed_at": ts.isoformat(),
                    "mfe_pct": round((highest - entry) / entry * 100, 2),
                    "mae_pct": round((lowest - entry) / entry * 100, 2),
                }
        else:
            if high >= stop:
                return {
                    "status": "stop_hit",
                    "exit_price": stop,
                    "result_pct": _result_pct_short(entry, stop),
                    "success": False,
                    "closed_at": ts.isoformat(),
                    "mfe_pct": round((entry - lowest) / entry * 100, 2),
                    "mae_pct": round((entry - highest) / entry * 100, 2),
                }
            if low <= target_2:
                return {
                    "status": "target_2_hit",
                    "exit_price": target_2,
                    "result_pct": _result_pct_short(entry, target_2),
                    "success": True,
                    "closed_at": ts.isoformat(),
                    "mfe_pct": round((entry - lowest) / entry * 100, 2),
                    "mae_pct": round((entry - highest) / entry * 100, 2),
                }
            if low <= target_1:
                return {
                    "status": "target_hit",
                    "exit_price": target_1,
                    "result_pct": _result_pct_short(entry, target_1),
                    "success": True,
                    "closed_at": ts.isoformat(),
                    "mfe_pct": round((entry - lowest) / entry * 100, 2),
                    "mae_pct": round((entry - highest) / entry * 100, 2),
                }

    last_close = float(bars.iloc[-1]["Close"])
    result = _result_pct_long(entry, last_close) if is_long else _result_pct_short(entry, last_close)
    status = "expired_win" if result > 0 else "expired_loss"
    return {
        "status": status,
        "exit_price": round(last_close, 2),
        "result_pct": result,
        "success": status == "expired_win",
        "closed_at": bars.index[-1].isoformat(),
        "mfe_pct": round((highest - entry) / entry * 100, 2) if is_long else round((entry - lowest) / entry * 100, 2),
        "mae_pct": round((lowest - entry) / entry * 100, 2) if is_long else round((entry - highest) / entry * 100, 2),
    }


def _find_recorded_trade(db: Session | None, symbol: str, trade_date: date) -> dict | None:
    if db is None:
        return None
    day_start = datetime.combine(trade_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    row = (
        db.query(IntradaySignalHistory)
        .filter(
            IntradaySignalHistory.symbol == symbol.upper(),
            IntradaySignalHistory.trade_date >= day_start,
            IntradaySignalHistory.trade_date < day_end,
        )
        .order_by(IntradaySignalHistory.created_at.asc())
        .first()
    )
    if not row:
        return None
    return intraday_to_dict(row)


def backtest_intraday(symbol: str, date_str: str, db: Session | None = None) -> dict:
    symbol = symbol.upper()
    trade_date = _parse_trade_date(date_str)

    if not is_us_trading_day(trade_date):
        raise ValueError(f"{date_str} is not a US market trading day")

    df_5m_full = fetch_history(symbol, period="1mo", interval="5m")
    df_15m_full = fetch_history(symbol, period="1mo", interval="15m")
    df_1d_full = fetch_history(symbol, period="6mo", interval="1d")

    session_5m = _session_day_bars(df_5m_full, trade_date)
    if session_5m.empty:
        raise ValueError(
            f"No 5-minute data for {symbol} on {date_str}. "
            "Yahoo may not have intraday history that far back (try last ~30 days)."
        )

    scan_log: list[dict] = []
    entry_signal = None
    entry_time: datetime | None = None

    for as_of in _scan_times(trade_date):
        df_5m = _slice_as_of(df_5m_full, as_of)
        df_15m = _slice_as_of(df_15m_full, as_of)
        df_1d = _to_eastern(df_1d_full)
        df_1d = df_1d[df_1d.index.date <= trade_date]

        if len(df_5m) < 30:
            continue

        try:
            signal = analyze_intraday(symbol, df_5m, df_15m, df_1d, as_of_et=as_of)
        except ValueError:
            continue

        snap = {
            "time_et": as_of.strftime("%H:%M"),
            "actionable": signal.actionable,
            "direction": signal.direction.value,
            "score": signal.score,
            "confidence": signal.confidence,
            "summary": signal.summary,
        }
        scan_log.append(snap)

        if signal.actionable and entry_signal is None:
            entry_signal = signal
            entry_time = as_of
            break

    session_close = datetime.combine(trade_date, SESSION_CLOSE, tzinfo=US_EASTERN)
    recorded = _find_recorded_trade(db, symbol, trade_date)

    if entry_signal is None or entry_time is None:
        return {
            "replay_type": "shizu_intraday_backtest",
            "app_version": __version__,
            "symbol": symbol,
            "date": date_str,
            "traded": False,
            "scans_run": len(scan_log),
            "session_bars": len(session_5m),
            "message": "No actionable setup — current rules would not have entered a trade.",
            "scan_log": scan_log[-12:],
            "recorded_trade": recorded,
        }

    plan = entry_signal.trade_plan
    assert plan is not None

    forward = session_5m[session_5m.index > entry_time]
    outcome = _simulate_outcome(
        plan.direction,
        plan.entry_price,
        plan.stop_loss,
        plan.target_1,
        plan.target_2,
        forward,
    )

    signal_dict = signal_to_api_dict(entry_signal)
    signal_dict["entry_time_et"] = entry_time.strftime("%Y-%m-%d %H:%M:%S %Z")

    return {
        "replay_type": "shizu_intraday_backtest",
        "app_version": __version__,
        "symbol": symbol,
        "date": date_str,
        "traded": True,
        "scans_run": len(scan_log),
        "session_bars": len(session_5m),
        "entry_time_et": entry_time.isoformat(),
        "signal": signal_dict,
        "trade_plan": {
            "direction": plan.direction,
            "entry_price": plan.entry_price,
            "stop_loss": plan.stop_loss,
            "target_1": plan.target_1,
            "target_2": plan.target_2,
            "stop_pct": plan.stop_pct,
            "target_1_pct": plan.target_1_pct,
            "target_2_pct": plan.target_2_pct,
            "risk_reward": plan.risk_reward,
            "hold_minutes": plan.hold_minutes,
        },
        "outcome": outcome,
        "scan_log": scan_log,
        "recorded_trade": recorded,
        "notes": [
            "Replay runs ORB + VWAP rules every 2 minutes from 9:45 AM–2:30 PM ET.",
            "First actionable signal is taken (one trade per replay, matching live save rules).",
            "Outcome uses 5m bar highs/lows after entry through market close.",
            "Compare recorded_trade if the app actually traded this symbol that day.",
        ],
    }
