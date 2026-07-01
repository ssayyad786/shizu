"""US intraday signal engine — ORB + VWAP playbook (opening range breakout model)."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from enum import Enum
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import ta

US_EASTERN = ZoneInfo("America/New_York")
SESSION_CLOSE = time(16, 0)
ENTRY_EARLIEST_ET = time(9, 45)  # after 15-minute opening range forms
ENTRY_CUTOFF_ET = time(14, 30)  # avoid late-day breakouts (low follow-through)
INTRADAY_MIN_CONFIDENCE = 50.0
INTRADAY_MIN_SCORE = 0.35
STOP_ATR_MULT = 1.25
MIN_STOP_PCT = 0.30
OR_BARS_5M = 3  # 9:30–9:45 ET on 5m chart
MIN_BREAKOUT_RVOL = 1.15  # vs 20-bar 5m average on breakout bar
MIN_RETEST_RVOL = 0.95
MIN_CONTINUATION_RVOL = 1.05
RETEST_TOLERANCE_PCT = 0.30
CONTINUATION_VWAP_MIN_PCT = 0.12
CONTINUATION_VWAP_MAX_PCT = 0.75
VWAP_MAX_CHASE_PCT = 0.85
VWAP_MAX_DUMP_PCT = 0.85

WEIGHTS = {
    "orb": 0.35,
    "vwap": 0.25,
    "volume": 0.20,
    "ema": 0.10,
    "daily_trend": 0.10,
}

FACTOR_LABELS = {
    "orb": ("Opening range (ORB)", "35%"),
    "vwap": ("VWAP alignment", "25%"),
    "volume": ("Breakout volume (RVOL)", "20%"),
    "ema": ("EMA 9/20 stack", "10%"),
    "daily_trend": ("Daily trend (21 EMA)", "10%"),
}

INDICATOR_KEYS = {
    "ORB": "orb",
    "VWAP": "vwap",
    "RVOL": "volume",
    "EMA": "ema",
    "Daily": "daily_trend",
}


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"


@dataclass
class OpeningRange:
    high: float
    low: float
    mid: float
    avg_volume: float
    gap_pct: float


@dataclass
class OrbSetup:
    direction: Direction
    setup_type: str  # orb_breakout | orb_retest
    score: float
    breakout_rvol: float
    or_high: float
    or_low: float


@dataclass
class IndicatorSignal:
    name: str
    value: float | None
    signal: str
    score: float
    detail: str


@dataclass
class IntradayTradePlan:
    direction: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    stop_pct: float
    target_1_pct: float
    target_2_pct: float
    risk_reward: float
    hold_minutes: int
    expires_at: str


@dataclass
class IntradaySignal:
    symbol: str
    direction: Direction
    confidence: float
    price: float
    score: float
    indicators: list[IndicatorSignal]
    summary: str
    actionable: bool
    reasoning: list[str]
    why_headline: str = ""
    trade_reasons: list[dict] | None = None
    trade_plan: IntradayTradePlan | None = None
    vwap: float | None = None
    rvol: float | None = None
    daily_trend: str | None = None


def _bias_label(score: float) -> str:
    if score > 0.15:
        return "BULLISH"
    if score < -0.15:
        return "BEARISH"
    return "NEUTRAL"


def build_trade_reasons(
    indicators: list[IndicatorSignal],
    daily_trend: str,
    direction: Direction,
    score: float,
    confidence: float,
    actionable: bool,
    low_vol: bool,
    setup_type: str | None = None,
) -> tuple[str, list[dict], list[str]]:
    reasons: list[dict] = []

    if daily_trend != "unknown":
        dt_bias = "BULLISH" if daily_trend == "bullish" else "BEARISH" if daily_trend == "bearish" else "NEUTRAL"
        reasons.append({
            "factor": "Daily trend (21 EMA)",
            "weight": "10%",
            "bias": dt_bias,
            "detail": (
                f"Daily chart {daily_trend} vs 21-day EMA — "
                f"{'with' if (daily_trend == 'bullish' and direction == Direction.LONG) or (daily_trend == 'bearish' and direction == Direction.SHORT) else 'against' if daily_trend in ('bullish', 'bearish') else 'neutral to'} "
                f"this {direction.value.lower() if direction != Direction.HOLD else 'setup'}"
            ),
        })

    for ind in indicators:
        key = INDICATOR_KEYS.get(ind.name, ind.name.lower())
        factor, weight = FACTOR_LABELS.get(key, (ind.name, "—"))
        reasons.append({
            "factor": factor,
            "weight": weight,
            "bias": _bias_label(ind.score),
            "detail": ind.detail,
        })

    setup_label = setup_type.replace("_", " ").title() if setup_type else "ORB setup"
    if actionable:
        headline = (
            f"Why {direction.value}: {setup_label} — score {score:+.2f} ({confidence:.0f}% confidence). "
            "ORB + VWAP + volume playbook."
        )
    elif low_vol:
        headline = "Why no trade: volatility too low for a reliable intraday ORB setup."
    else:
        headline = (
            f"Why no trade: no valid ORB + VWAP setup yet (score {score:+.2f}). "
            "Wait for a 15m range break or retest with volume."
        )

    bullets = [f"{r['factor']} ({r['weight']}): {r['detail']}" for r in reasons if r["bias"] != "NEUTRAL"]
    if not bullets:
        bullets = [f"{r['factor']} ({r['weight']}): {r['detail']}" for r in reasons[:5]]

    return headline, reasons, bullets


def _session_bars(df: pd.DataFrame, session_date: date | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    if getattr(work.index, "tz", None) is None:
        work.index = work.index.tz_localize("UTC")
    work.index = work.index.tz_convert(US_EASTERN)
    target = session_date or datetime.now(US_EASTERN).date()
    return work[work.index.date == target]


def _calc_vwap(df: pd.DataFrame, session_date: date | None = None) -> float | None:
    session = _session_bars(df, session_date)
    if session.empty or session["Volume"].sum() == 0:
        if df.empty:
            return None
        session = df.tail(78)
    tp = (session["High"] + session["Low"] + session["Close"]) / 3
    vol = session["Volume"].replace(0, np.nan)
    if vol.sum() == 0 or vol.isna().all():
        return float(session["Close"].iloc[-1])
    return float((tp * vol).sum() / vol.sum())


def _gap_pct(df_1d: pd.DataFrame) -> float:
    if df_1d.empty or len(df_1d) < 2:
        return 0.0
    prev_close = float(df_1d["Close"].iloc[-2])
    today_open = float(df_1d["Open"].iloc[-1])
    return (today_open - prev_close) / prev_close * 100 if prev_close else 0.0


def _get_opening_range(df_5m: pd.DataFrame, df_1d: pd.DataFrame, session_date: date) -> OpeningRange | None:
    session = _session_bars(df_5m, session_date)
    if len(session) < OR_BARS_5M:
        return None
    opening = session.iloc[:OR_BARS_5M]
    high = float(opening["High"].max())
    low = float(opening["Low"].min())
    avg_vol = float(opening["Volume"].mean())
    return OpeningRange(
        high=high,
        low=low,
        mid=(high + low) / 2,
        avg_volume=avg_vol,
        gap_pct=_gap_pct(df_1d),
    )


def _daily_trend(df_1d: pd.DataFrame) -> str:
    if len(df_1d) < 21:
        return "unknown"
    close = df_1d["Close"]
    e21 = ta.trend.EMAIndicator(close, window=21).ema_indicator()
    if float(close.iloc[-1]) > float(e21.iloc[-1]):
        return "bullish"
    if float(close.iloc[-1]) < float(e21.iloc[-1]):
        return "bearish"
    return "neutral"


def _ema_signal(df: pd.DataFrame) -> IndicatorSignal:
    close = df["Close"]
    if len(close) < 20:
        return IndicatorSignal("EMA", None, "NEUTRAL", 0.0, "Not enough data for EMA")
    e9 = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    e20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    p, v9, v20 = float(close.iloc[-1]), float(e9.iloc[-1]), float(e20.iloc[-1])
    if p > v9 > v20:
        return IndicatorSignal("EMA", v9, "BUY", 0.9, "Bullish EMA stack (9>20, price above)")
    if p < v9 < v20:
        return IndicatorSignal("EMA", v9, "SELL", -0.9, "Bearish EMA stack (9<20, price below)")
    return IndicatorSignal("EMA", v9, "NEUTRAL", 0.0, "EMAs mixed — no clear micro-trend")


def _vwap_indicator(price: float, vwap: float | None, want_long: bool) -> IndicatorSignal:
    if vwap is None or vwap <= 0:
        return IndicatorSignal("VWAP", None, "NEUTRAL", 0.0, "VWAP unavailable")
    dist = (price - vwap) / vwap * 100
    if want_long:
        if dist >= 0 and dist <= CONTINUATION_VWAP_MAX_PCT:
            sc = 0.9 if dist <= 0.35 else 0.6
            return IndicatorSignal("VWAP", round(vwap, 2), "BUY", sc,
                                   f"Above VWAP (+{dist:.2f}%) — long bias OK")
        if dist > CONTINUATION_VWAP_MAX_PCT:
            return IndicatorSignal("VWAP", round(vwap, 2), "NEUTRAL", 0.1,
                                   f"Too far above VWAP (+{dist:.2f}%) — chase risk")
        return IndicatorSignal("VWAP", round(vwap, 2), "SELL", -0.5, f"Below VWAP ({dist:+.2f}%) — long blocked")
    if dist <= 0 and dist >= -CONTINUATION_VWAP_MAX_PCT:
        sc = -0.9 if dist >= -0.35 else -0.6
        return IndicatorSignal("VWAP", round(vwap, 2), "SELL", sc,
                               f"Below VWAP ({dist:.2f}%) — short bias OK")
    if dist < -CONTINUATION_VWAP_MAX_PCT:
        return IndicatorSignal("VWAP", round(vwap, 2), "NEUTRAL", -0.1,
                               f"Too far below VWAP ({dist:.2f}%) — dump risk")
    return IndicatorSignal("VWAP", round(vwap, 2), "BUY", 0.5, f"Above VWAP (+{dist:.2f}%) — short blocked")


def _volume_indicator(breakout_rvol: float, want_long: bool, bar_up: bool) -> IndicatorSignal:
    if breakout_rvol >= 2.0:
        sc = 0.95 if (want_long == bar_up) else -0.95 if (not want_long and not bar_up) else 0.4
        return IndicatorSignal("RVOL", round(breakout_rvol, 2), "BUY" if bar_up else "SELL", sc,
                              f"Strong volume {breakout_rvol:.1f}× 20-bar average")
    if breakout_rvol >= MIN_BREAKOUT_RVOL:
        sc = 0.75 if (want_long == bar_up) else -0.75 if (not want_long and not bar_up) else 0.3
        return IndicatorSignal("RVOL", round(breakout_rvol, 2), "BUY" if bar_up else "SELL", sc,
                              f"Volume {breakout_rvol:.1f}× 20-bar avg (≥{MIN_BREAKOUT_RVOL}× breakout)")
    if breakout_rvol >= MIN_RETEST_RVOL:
        return IndicatorSignal("RVOL", round(breakout_rvol, 2), "NEUTRAL", 0.2,
                               f"Moderate volume {breakout_rvol:.1f}× — OK for retest/continuation")
    return IndicatorSignal("RVOL", round(breakout_rvol, 2), "NEUTRAL", 0.0,
                           f"Weak volume {breakout_rvol:.1f}× — need ≥{MIN_RETEST_RVOL}×")


def _orb_indicator(setup: OrbSetup | None, orb: OpeningRange | None) -> IndicatorSignal:
    if setup is None or orb is None:
        detail = "No ORB setup — price inside 15m range or filters not met"
        if orb:
            detail = f"Inside 15m OR ({orb.low:.2f}–{orb.high:.2f}) — wait for break + VWAP align"
        return IndicatorSignal("ORB", None, "NEUTRAL", 0.0, detail)
    label = {
        "orb_breakout": "Breakout",
        "orb_retest": "Retest",
        "orb_continuation": "Continuation",
    }.get(setup.setup_type, setup.setup_type)
    if setup.direction == Direction.LONG:
        return IndicatorSignal(
            "ORB", setup.or_high, "BUY", 0.85 if setup.setup_type == "orb_breakout" else 0.7,
            f"ORB {label} long — close above OR high {setup.or_high:.2f}",
        )
    return IndicatorSignal(
        "ORB", setup.or_low, "SELL", -0.85 if setup.setup_type == "orb_breakout" else -0.7,
        f"ORB {label} short — close below OR low {setup.or_low:.2f}",
    )


def _session_rvol(df_5m: pd.DataFrame) -> float:
    vol = df_5m["Volume"]
    if len(vol) < 3:
        return 1.0
    if len(vol) >= 21:
        avg = float(vol.iloc[-21:-1].mean())
    else:
        avg = float(vol.iloc[:-1].mean())
    current = float(vol.iloc[-1])
    return current / avg if avg > 0 else 1.0


def _detect_orb_setup(
    df_5m: pd.DataFrame,
    orb: OpeningRange,
    session_date: date,
    vwap: float | None,
) -> OrbSetup | None:
    session = _session_bars(df_5m, session_date)
    if session.empty:
        return None

    last = session.iloc[-1]
    close = float(last["Close"])
    open_ = float(last["Open"])
    rvol20 = _session_rvol(df_5m)
    session_high = float(session["High"].max())
    session_low = float(session["Low"].min())

    # ORB breakout or continuation above range
    if close > orb.high and close > open_ and vwap is not None and close > vwap:
        dist = (close - vwap) / vwap * 100
        if dist > VWAP_MAX_CHASE_PCT:
            pass
        elif rvol20 >= MIN_BREAKOUT_RVOL:
            return OrbSetup(Direction.LONG, "orb_breakout", 0.55, rvol20, orb.high, orb.low)
        elif (
            session_high > orb.high * 1.002
            and rvol20 >= MIN_CONTINUATION_RVOL
            and CONTINUATION_VWAP_MIN_PCT <= dist <= CONTINUATION_VWAP_MAX_PCT
        ):
            return OrbSetup(Direction.LONG, "orb_continuation", 0.38, rvol20, orb.high, orb.low)

    if close < orb.low and close < open_ and vwap is not None and close < vwap:
        dist = (close - vwap) / vwap * 100
        if dist < -VWAP_MAX_DUMP_PCT:
            pass
        elif rvol20 >= MIN_BREAKOUT_RVOL:
            return OrbSetup(Direction.SHORT, "orb_breakout", -0.55, rvol20, orb.high, orb.low)
        elif (
            session_low < orb.low * 0.998
            and rvol20 >= MIN_CONTINUATION_RVOL
            and -CONTINUATION_VWAP_MAX_PCT <= dist <= -CONTINUATION_VWAP_MIN_PCT
        ):
            return OrbSetup(Direction.SHORT, "orb_continuation", -0.38, rvol20, orb.high, orb.low)

    # ORB retest — pullback to broken range edge
    if session_high > orb.high * 1.001:
        dist_to_or = (close - orb.high) / orb.high * 100
        if (
            -0.05 <= dist_to_or <= RETEST_TOLERANCE_PCT
            and close > open_
            and vwap is not None
            and close > vwap
            and rvol20 >= MIN_RETEST_RVOL
        ):
            return OrbSetup(Direction.LONG, "orb_retest", 0.42, rvol20, orb.high, orb.low)

    if session_low < orb.low * 0.999:
        dist_to_or = (orb.low - close) / orb.low * 100
        if (
            -0.05 <= dist_to_or <= RETEST_TOLERANCE_PCT
            and close < open_
            and vwap is not None
            and close < vwap
            and rvol20 >= MIN_RETEST_RVOL
        ):
            return OrbSetup(Direction.SHORT, "orb_retest", -0.42, rvol20, orb.high, orb.low)

    return None


def _daily_allows(direction: Direction, daily_trend: str) -> bool:
    if direction == Direction.LONG:
        return daily_trend != "bearish"
    if direction == Direction.SHORT:
        return daily_trend == "bearish"
    return False


def _market_close_on(session_date: date) -> datetime:
    close_et = datetime.combine(session_date, SESSION_CLOSE, tzinfo=US_EASTERN)
    return close_et.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def _too_late_for_entry(as_of_et: datetime | None = None) -> bool:
    now_et = as_of_et or datetime.now(US_EASTERN)
    cutoff = datetime.combine(now_et.date(), ENTRY_CUTOFF_ET, tzinfo=US_EASTERN)
    return now_et >= cutoff


def _too_early_for_entry(as_of_et: datetime | None = None) -> bool:
    now_et = as_of_et or datetime.now(US_EASTERN)
    earliest = datetime.combine(now_et.date(), ENTRY_EARLIEST_ET, tzinfo=US_EASTERN)
    return now_et < earliest


def _atr_ok(df_5m: pd.DataFrame, price: float) -> tuple[bool, float]:
    """Return (tradeable, atr_value). tradeable=False when volatility too low."""
    if len(df_5m) < 15:
        return False, 0.0
    atr = float(
        ta.volatility.AverageTrueRange(df_5m["High"], df_5m["Low"], df_5m["Close"], window=14)
        .average_true_range()
        .iloc[-1]
    )
    atr_pct = atr / price * 100 if price else 0
    return atr_pct >= 0.08, atr


def _build_trade_plan(
    direction: Direction,
    price: float,
    atr: float,
    score: float,
    or_high: float,
    or_low: float,
    setup_type: str,
    session_date: date | None = None,
) -> IntradayTradePlan:
    min_stop_dist = price * MIN_STOP_PCT / 100
    atr_stop = atr * STOP_ATR_MULT

    if direction == Direction.LONG:
        or_stop = price - or_low
        stop_dist = max(or_stop, atr_stop, min_stop_dist)
        stop = round(price - stop_dist, 2)
        t1 = round(price + stop_dist * 1.5, 2)
        t2 = round(price + stop_dist * 2.5, 2)
    else:
        or_stop = or_high - price
        stop_dist = max(or_stop, atr_stop, min_stop_dist)
        stop = round(price + stop_dist, 2)
        t1 = round(price - stop_dist * 1.5, 2)
        t2 = round(price - stop_dist * 2.5, 2)

    risk = abs(price - stop)
    reward = abs(t1 - price)
    rr = round(reward / risk, 2) if risk > 0 else 0
    hold = 60 if setup_type in ("orb_retest", "orb_continuation") else 90
    if abs(score) >= 0.5:
        hold = 120

    sd = session_date or datetime.now(US_EASTERN).date()
    return IntradayTradePlan(
        direction=direction.value,
        entry_price=round(price, 2),
        stop_loss=stop,
        target_1=t1,
        target_2=t2,
        stop_pct=round(abs(price - stop) / price * 100, 2),
        target_1_pct=round(abs(t1 - price) / price * 100, 2),
        target_2_pct=round(abs(t2 - price) / price * 100, 2),
        risk_reward=rr,
        hold_minutes=hold,
        expires_at=_market_close_on(sd).isoformat(),
    )


def trade_plan_to_dict(plan: IntradayTradePlan | None) -> dict | None:
    if not plan:
        return None
    return asdict(plan)


def _compute_score(setup: OrbSetup | None, indicators: list[IndicatorSignal], daily_trend: str) -> float:
    if setup is None:
        return 0.0
    score = setup.score
    for ind in indicators:
        key = INDICATOR_KEYS.get(ind.name)
        if not key:
            continue
        weight = WEIGHTS.get(key, 0.0)
        if setup.direction == Direction.LONG:
            score += ind.score * weight * 0.35
        else:
            score += ind.score * weight * 0.35
    if setup.direction == Direction.LONG and daily_trend == "bullish":
        score += 0.05
    elif setup.direction == Direction.SHORT and daily_trend == "bearish":
        score -= 0.05
    return score


def analyze_intraday(
    symbol: str,
    df_5m: pd.DataFrame,
    df_15m: pd.DataFrame,
    df_1d: pd.DataFrame,
    as_of_et: datetime | None = None,
) -> IntradaySignal:
    if len(df_5m) < 30:
        raise ValueError(f"Not enough 5m data for {symbol}")

    as_of_et = as_of_et or datetime.now(US_EASTERN)
    session_date = as_of_et.date()
    price = float(df_5m["Close"].iloc[-1])
    vwap = _calc_vwap(df_5m, session_date)
    daily_trend = _daily_trend(df_1d)
    orb = _get_opening_range(df_5m, df_1d, session_date)

    atr_tradeable, atr_val = _atr_ok(df_5m, price)
    low_vol = not atr_tradeable
    late_entry = _too_late_for_entry(as_of_et)
    early_entry = _too_early_for_entry(as_of_et)

    setup: OrbSetup | None = None
    block_reason: str | None = None

    if early_entry:
        block_reason = "Before 9:45 AM ET — 15-minute opening range not complete."
    elif late_entry:
        block_reason = "After 2:30 PM ET — late ORB entries have poor follow-through."
    elif low_vol:
        block_reason = "ATR too low — stock not moving enough for intraday ORB edge."
    elif orb is None:
        block_reason = "Opening range not available — need first 15 minutes of session data."
    else:
        setup = _detect_orb_setup(df_5m, orb, session_date, vwap)
        if setup and orb and vwap:
            vwap_dist = (price - vwap) / vwap * 100
            if (
                setup.direction == Direction.LONG
                and setup.setup_type == "orb_continuation"
                and orb.gap_pct >= 1.2
            ):
                block_reason = (
                    f"Gap-up (+{orb.gap_pct:.1f}%) — skip continuation longs; wait for OR retest near VWAP."
                )
                setup = None
            elif (
                setup.direction == Direction.LONG
                and setup.setup_type == "orb_breakout"
                and orb.gap_pct >= 1.0
                and vwap_dist > 0.18
            ):
                block_reason = (
                    f"Gap-up (+{orb.gap_pct:.1f}%) breakout without VWAP hold ({vwap_dist:+.2f}% above)."
                )
                setup = None
            elif setup.direction == Direction.SHORT and orb.gap_pct <= -1.4:
                block_reason = (
                    f"Severe gap-down ({orb.gap_pct:.1f}%) — skip shorts (bounce risk)."
                )
                setup = None
        if setup and not _daily_allows(setup.direction, daily_trend):
            block_reason = (
                f"ORB {setup.setup_type.replace('_', ' ')} blocked — daily trend is {daily_trend} "
                f"(longs need non-bearish, shorts need non-bullish daily)."
            )
            setup = None

    ema_df = df_15m if len(df_15m) >= 20 else df_5m
    want_long = setup.direction == Direction.LONG if setup else True
    bar_up = float(df_5m["Close"].iloc[-1]) >= float(df_5m["Open"].iloc[-1])
    breakout_rvol = setup.breakout_rvol if setup else (
        float(df_5m["Volume"].iloc[-1]) / orb.avg_volume if orb and orb.avg_volume > 0 else 1.0
    )

    indicators = [
        _orb_indicator(setup, orb),
        _vwap_indicator(price, vwap, want_long if setup else True),
        _volume_indicator(breakout_rvol, want_long if setup else bar_up, bar_up),
        _ema_signal(ema_df),
    ]

    score = _compute_score(setup, indicators, daily_trend)
    confidence = min(40 + abs(score) / 0.55 * 60, 100) if setup else min(abs(score) / 0.55 * 100, 50)

    direction = Direction.HOLD
    actionable = False
    plan = None
    setup_type: str | None = setup.setup_type if setup else None

    if setup and not block_reason:
        vwap_ind = indicators[1]
        vwap_ok = abs(vwap_ind.score) >= 0.5

        if abs(score) >= INTRADAY_MIN_SCORE and confidence >= INTRADAY_MIN_CONFIDENCE and vwap_ok:
            direction = setup.direction
            actionable = True
            plan = _build_trade_plan(
                setup.direction, price, atr_val, score,
                setup.or_high, setup.or_low, setup.setup_type, session_date,
            )
            kind = {"orb_breakout": "Breakout", "orb_retest": "Retest", "orb_continuation": "Continuation"}.get(
                setup.setup_type, "Setup"
            )
            summary = (
                f"{direction.value} — ORB {kind}, score {score:+.2f}, {confidence:.0f}% confidence. "
                f"Entry {plan.entry_price}, T1 {plan.target_1} ({'+' if direction == Direction.LONG else ''}{plan.target_1_pct}%), "
                f"stop {plan.stop_loss}, ~{plan.hold_minutes} min hold."
            )
        elif not vwap_ok:
            block_reason = "VWAP not aligned — longs need price above VWAP, shorts below."
        else:
            block_reason = (
                f"ORB setup weak — score {score:+.2f} or confidence below "
                f"{INTRADAY_MIN_CONFIDENCE:.0f}%."
            )

    if not actionable:
        if block_reason:
            summary = f"No trade — {block_reason}"
        elif orb:
            summary = (
                f"No ORB setup — range {orb.low:.2f}–{orb.high:.2f}. "
                "Wait for close beyond range + VWAP + volume ≥1.2× OR average."
            )
        else:
            summary = "No intraday ORB setup — wait for opening range to form."

    why_headline, trade_reasons, reasoning = build_trade_reasons(
        indicators, daily_trend, direction, score, confidence, actionable, low_vol, setup_type
    )

    return IntradaySignal(
        symbol=symbol.upper(),
        direction=direction,
        confidence=round(confidence, 1),
        price=round(price, 2),
        score=round(score, 3),
        indicators=indicators,
        summary=summary,
        actionable=actionable,
        reasoning=reasoning,
        why_headline=why_headline,
        trade_reasons=trade_reasons,
        trade_plan=plan,
        vwap=round(vwap, 2) if vwap else None,
        rvol=round(breakout_rvol, 2),
        daily_trend=daily_trend,
    )
