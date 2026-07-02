"""Replay intraday logic on historical bars for a symbol + date."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from app.models import IntradaySignalHistory
from app.services.intraday_history import intraday_to_dict
from app.services.intraday_monitor import signal_to_api_dict
from app.services.intraday_signals import (
    ENTRY_CUTOFF_ET,
    ENTRY_EARLIEST_ET,
    US_EASTERN,
    analyze_intraday,
)
from app.services.market_data import fetch_history
from app.services.us_market_hours import is_us_trading_day
from app.version import __version__

SCAN_INTERVAL_MINUTES = 2
MAX_RANGE_TRADING_DAYS = 30
MAX_RANGE_CALENDAR_DAYS = 90
FRAME_CACHE_TTL_SEC = 300
_frame_cache: dict[str, tuple[float, pd.DataFrame, pd.DataFrame, pd.DataFrame]] = {}


def _to_eastern(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if work.index.tz is None:
        work.index = work.index.tz_localize("UTC")
    work.index = work.index.tz_convert(US_EASTERN)
    return work


def _slice_as_of(df_et: pd.DataFrame, as_of_et: datetime) -> pd.DataFrame:
    return df_et[df_et.index <= as_of_et]


def _session_day_bars(df_et: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    return df_et[df_et.index.date == trade_date]


def _history_period_for_range(start: date, end: date) -> str:
    span = (end - start).days
    if span <= 25:
        return "1mo"
    if span <= 55:
        return "2mo"
    return "3mo"


def _load_symbol_frames(symbol: str, period: str = "1mo") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and cache Yahoo intraday/daily frames (Eastern tz) for repeat day replays."""
    symbol = symbol.upper()
    cache_key = f"{symbol}:{period}"
    now = time.time()
    cached = _frame_cache.get(cache_key)
    if cached and now - cached[0] < FRAME_CACHE_TTL_SEC:
        return cached[1], cached[2], cached[3]

    df_5m = _to_eastern(fetch_history(symbol, period=period, interval="5m"))
    df_15m = _to_eastern(fetch_history(symbol, period=period, interval="15m"))
    df_1d = _to_eastern(fetch_history(symbol, period="6mo", interval="1d"))
    _frame_cache[cache_key] = (now, df_5m, df_15m, df_1d)

    if len(_frame_cache) > 8:
        oldest_key = min(_frame_cache, key=lambda k: _frame_cache[k][0])
        del _frame_cache[oldest_key]

    return df_5m, df_15m, df_1d


def lighten_backtest_result(result: dict) -> dict:
    """Drop bulky fields for range replay responses."""
    slim = {k: v for k, v in result.items() if k != "scan_log"}
    signal = slim.get("signal")
    if isinstance(signal, dict):
        slim["signal"] = {k: v for k, v in signal.items() if k != "indicators"}
    return slim


def validate_date_range(start: date, end: date) -> None:
    if start > end:
        raise ValueError("Start date must be on or before end date")
    if (end - start).days > MAX_RANGE_CALENDAR_DAYS:
        raise ValueError(
            f"Date range spans more than {MAX_RANGE_CALENDAR_DAYS} calendar days. "
            "Use a shorter range."
        )


def _parse_trade_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def parse_trade_date(date_str: str) -> date:
    return _parse_trade_date(date_str)


def iter_us_trading_days(start: date, end: date) -> list[date]:
    validate_date_range(start, end)
    days: list[date] = []
    d = start
    while d <= end:
        if is_us_trading_day(d):
            days.append(d)
        d += timedelta(days=1)
    return days


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


def _backtest_day(
    symbol: str,
    trade_date: date,
    df_5m_full: pd.DataFrame,
    df_15m_full: pd.DataFrame,
    df_1d_full: pd.DataFrame,
    db: Session | None = None,
) -> dict:
    date_str = trade_date.isoformat()
    session_5m = _session_day_bars(df_5m_full, trade_date)
    if session_5m.empty:
        return {
            "replay_type": "shizu_intraday_backtest",
            "app_version": __version__,
            "symbol": symbol,
            "date": date_str,
            "traded": False,
            "scans_run": 0,
            "session_bars": 0,
            "message": f"No 5-minute data for {symbol} on {date_str}.",
            "recorded_trade": _find_recorded_trade(db, symbol, trade_date),
        }

    scan_log: list[dict] = []
    entry_signal = None
    entry_time: datetime | None = None

    for as_of in _scan_times(trade_date):
        df_5m = _slice_as_of(df_5m_full, as_of)
        df_15m = _slice_as_of(df_15m_full, as_of)
        df_1d = df_1d_full[df_1d_full.index.date <= trade_date]

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
    }


def backtest_intraday(
    symbol: str,
    date_str: str,
    db: Session | None = None,
    *,
    light: bool = False,
) -> dict:
    symbol = symbol.upper()
    trade_date = _parse_trade_date(date_str)

    if not is_us_trading_day(trade_date):
        raise ValueError(f"{date_str} is not a US market trading day")

    df_5m_full, df_15m_full, df_1d_full = _load_symbol_frames(symbol, period="1mo")

    result = _backtest_day(symbol, trade_date, df_5m_full, df_15m_full, df_1d_full, db=db)
    if not result["traded"] and result.get("session_bars", 0) == 0:
        raise ValueError(
            f"No 5-minute data for {symbol} on {date_str}. "
            "Yahoo may not have intraday history that far back (try last ~30 days)."
        )

    if not light:
        result["notes"] = [
            "Replay runs ORB + VWAP rules every 2 minutes from 9:45 AM–2:30 PM ET.",
            "First actionable signal is taken (one trade per replay, matching live save rules).",
            "Outcome uses 5m bar highs/lows after entry through market close.",
            "Compare recorded_trade if the app actually traded this symbol that day.",
        ]
    return lighten_backtest_result(result) if light else result


def backtest_intraday_range(
    symbol: str,
    start_str: str,
    end_str: str,
    db: Session | None = None,
) -> dict:
    symbol = symbol.upper()
    start = _parse_trade_date(start_str)
    end = _parse_trade_date(end_str)
    trading_days = iter_us_trading_days(start, end)

    if not trading_days:
        raise ValueError("No US trading days in this date range")
    if len(trading_days) > MAX_RANGE_TRADING_DAYS:
        raise ValueError(
            f"Range spans {len(trading_days)} trading days; maximum is {MAX_RANGE_TRADING_DAYS}. "
            "Use a shorter range."
        )

    hist_period = _history_period_for_range(start, end)
    df_5m_full, df_15m_full, df_1d_full = _load_symbol_frames(symbol, period=hist_period)

    day_results: list[dict] = []
    for trade_date in trading_days:
        day_results.append(
            _backtest_day(symbol, trade_date, df_5m_full, df_15m_full, df_1d_full, db=db)
        )

    traded = [r for r in day_results if r.get("traded")]
    wins = [r for r in traded if r.get("outcome", {}).get("success")]
    losses = [r for r in traded if r.get("traded") and not r.get("outcome", {}).get("success")]
    no_trade = [r for r in day_results if not r.get("traded")]
    total_pct = sum(r.get("outcome", {}).get("result_pct", 0) for r in traded)

    return {
        "replay_type": "shizu_intraday_backtest_range",
        "app_version": __version__,
        "symbol": symbol,
        "start_date": start_str,
        "end_date": end_str,
        "trading_days": len(trading_days),
        "trades": len(traded),
        "wins": len(wins),
        "losses": len(losses),
        "no_trade_days": len(no_trade),
        "win_rate": round(len(wins) / len(traded) * 100, 1) if traded else 0.0,
        "total_result_pct": round(total_pct, 2),
        "avg_result_pct": round(total_pct / len(traded), 2) if traded else 0.0,
        "results": day_results,
        "notes": [
            f"Replayed {len(trading_days)} US trading day(s) from {start_str} to {end_str}.",
            "Each day uses current ORB + VWAP rules (one trade max per day).",
            "Days with no 5m data or no setup are listed as no-trade.",
        ],
    }
