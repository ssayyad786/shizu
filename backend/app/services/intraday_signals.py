"""US intraday signal engine — VWAP, structure, volume, multi-timeframe."""

from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import ta

US_EASTERN = ZoneInfo("America/New_York")
INTRADAY_MIN_CONFIDENCE = 45.0
INTRADAY_MIN_SCORE = 0.38
STOP_ATR_MULT = 1.25
MIN_STOP_PCT = 0.30
ENTRY_CUTOFF_ET = time(15, 0)  # no new trades after 3:00 PM ET
MIN_CORE_CONFLUENCE = 3  # of Structure, VWAP, EMA, RVOL must align

WEIGHTS = {
    "market_structure": 0.25,
    "vwap": 0.20,
    "volume": 0.15,
    "ema": 0.10,
    "opening_context": 0.10,
    "atr": 0.05,
    "rsi": 0.05,
    "candlestick": 0.05,
    "macd": 0.05,
}

FACTOR_LABELS = {
    "market_structure": ("Market structure", "25%"),
    "vwap": ("VWAP", "20%"),
    "volume": ("Relative volume (RVOL)", "15%"),
    "ema": ("EMA alignment (9/20/50)", "10%"),
    "opening_context": ("Opening range & gap", "10%"),
    "atr": ("ATR volatility", "5%"),
    "rsi": ("RSI exhaustion / divergence", "5%"),
    "candlestick": ("Candlestick pattern", "5%"),
    "macd": ("MACD confirmation", "5%"),
}

INDICATOR_KEYS = {
    "Structure": "market_structure",
    "VWAP": "vwap",
    "RVOL": "volume",
    "EMA": "ema",
    "Open/Gap": "opening_context",
    "ATR": "atr",
    "RSI": "rsi",
    "Candle": "candlestick",
    "MACD": "macd",
}


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"


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
) -> tuple[str, list[dict], list[str]]:
    """Headline, structured reasons, and plain-text bullets for each trade."""
    reasons: list[dict] = []

    if daily_trend != "unknown":
        dt_bias = "BULLISH" if daily_trend == "bullish" else "BEARISH" if daily_trend == "bearish" else "NEUTRAL"
        detail = (
            f"Daily chart: price is {daily_trend} vs 21-day EMA — "
            f"{'favors long setups' if daily_trend == 'bullish' else 'favors short setups' if daily_trend == 'bearish' else 'no clear daily bias'}"
        )
        reasons.append({
            "factor": "Daily trend (context)",
            "weight": "—",
            "bias": dt_bias,
            "detail": detail,
        })

    for ind in indicators:
        key = INDICATOR_KEYS.get(ind.name, ind.name.lower())
        factor, weight = FACTOR_LABELS.get(key, (ind.name, "—"))
        bias = _bias_label(ind.score)
        reasons.append({
            "factor": factor,
            "weight": weight,
            "bias": bias,
            "detail": ind.detail,
        })

    if actionable:
        headline = (
            f"Why {direction.value}: combined score {score:+.2f} ({confidence:.0f}% confidence). "
            f"The weighted factors below align for a same-day {direction.value.lower()}."
        )
    elif low_vol:
        headline = "Why no trade: ATR volatility filter blocked this setup — price movement too small for a reliable intraday edge."
    else:
        headline = (
            f"Why no trade: score {score:+.2f} did not reach the {INTRADAY_MIN_SCORE} threshold "
            f"or confidence is below {INTRADAY_MIN_CONFIDENCE:.0f}% — wait for VWAP + structure to align."
        )

    bullets = [f"{r['factor']} ({r['weight']}): {r['detail']}" for r in reasons if r["bias"] != "NEUTRAL"]
    if not bullets:
        bullets = [f"{r['factor']} ({r['weight']}): {r['detail']}" for r in reasons[:5]]

    return headline, reasons, bullets


def _session_bars(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    if getattr(work.index, "tz", None) is None:
        work.index = work.index.tz_localize("UTC")
    work.index = work.index.tz_convert(US_EASTERN)
    today = datetime.now(US_EASTERN).date()
    return work[work.index.date == today]


def _calc_vwap(df: pd.DataFrame) -> float | None:
    session = _session_bars(df)
    if session.empty or session["Volume"].sum() == 0:
        if df.empty:
            return None
        session = df.tail(78)
    tp = (session["High"] + session["Low"] + session["Close"]) / 3
    vol = session["Volume"].replace(0, np.nan)
    if vol.sum() == 0 or vol.isna().all():
        return float(session["Close"].iloc[-1])
    return float((tp * vol).sum() / vol.sum())


def _vwap_signal(price: float, vwap: float | None) -> IndicatorSignal:
    if vwap is None or vwap <= 0:
        return IndicatorSignal("VWAP", None, "NEUTRAL", 0.0, "VWAP unavailable")
    dist_pct = (price - vwap) / vwap * 100
    if dist_pct > 0.5:
        return IndicatorSignal("VWAP", round(vwap, 2), "BUY", 0.7, f"Price {dist_pct:.1f}% above VWAP — bullish")
    if dist_pct < -0.5:
        return IndicatorSignal("VWAP", round(vwap, 2), "SELL", -0.7, f"Price {dist_pct:.1f}% below VWAP — bearish")
    return IndicatorSignal("VWAP", round(vwap, 2), "NEUTRAL", 0.0, f"Price near VWAP ({dist_pct:+.1f}%)")


def _swing_structure(df: pd.DataFrame, lookback: int = 30) -> IndicatorSignal:
    if len(df) < lookback:
        return IndicatorSignal("Structure", None, "NEUTRAL", 0.0, "Not enough bars for structure")
    window = df.tail(lookback)
    highs = window["High"].values
    lows = window["Low"].values
    mid = lookback // 2
    h1, h2 = float(highs[:mid].max()), float(highs[mid:].max())
    l1, l2 = float(lows[:mid].min()), float(lows[mid:].min())

    if h2 > h1 and l2 > l1:
        return IndicatorSignal("Structure", h2 - l2, "BUY", 0.85, "Higher high + higher low — uptrend")
    if h2 < h1 and l2 < l1:
        return IndicatorSignal("Structure", h2 - l2, "SELL", -0.85, "Lower high + lower low — downtrend")
    if h2 > h1 and l2 <= l1:
        return IndicatorSignal("Structure", h2 - l2, "NEUTRAL", 0.0, "Higher high only — mixed structure (no trade)")
    if h2 < h1 and l2 >= l1:
        return IndicatorSignal("Structure", h2 - l2, "NEUTRAL", 0.0, "Lower high only — mixed structure (no trade)")
    return IndicatorSignal("Structure", h2 - l2, "NEUTRAL", 0.0, "Choppy / range-bound structure")


def _volume_signal(df: pd.DataFrame) -> IndicatorSignal:
    if len(df) < 21:
        return IndicatorSignal("Volume", None, "NEUTRAL", 0.0, "Insufficient volume history")
    vol = df["Volume"]
    avg = float(vol.iloc[-21:-1].mean())
    current = float(vol.iloc[-1])
    rvol = current / avg if avg > 0 else 1.0
    close_up = float(df["Close"].iloc[-1]) >= float(df["Open"].iloc[-1])
    if rvol >= 1.5 and close_up:
        return IndicatorSignal("RVOL", round(rvol, 2), "BUY", 0.8, f"RVOL {rvol:.1f}× on up bar — buying pressure")
    if rvol >= 1.5 and not close_up:
        return IndicatorSignal("RVOL", round(rvol, 2), "SELL", -0.8, f"RVOL {rvol:.1f}× on down bar — selling pressure")
    if rvol >= 1.2:
        return IndicatorSignal("RVOL", round(rvol, 2), "NEUTRAL", 0.15 if close_up else -0.15, f"Elevated RVOL {rvol:.1f}×")
    return IndicatorSignal("RVOL", round(rvol, 2), "NEUTRAL", 0.0, f"Normal volume (RVOL {rvol:.1f}×)")


def _ema_alignment_signal(df: pd.DataFrame) -> IndicatorSignal:
    close = df["Close"]
    if len(close) < 50:
        return IndicatorSignal("EMA", None, "NEUTRAL", 0.0, "Not enough data for EMA stack")
    e9 = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    e20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    e50 = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    p, v9, v20, v50 = float(close.iloc[-1]), float(e9.iloc[-1]), float(e20.iloc[-1]), float(e50.iloc[-1])
    if p > v9 > v20 > v50:
        return IndicatorSignal("EMA", v9, "BUY", 0.9, "Bullish EMA stack (9>20>50)")
    if p < v9 < v20 < v50:
        return IndicatorSignal("EMA", v9, "SELL", -0.9, "Bearish EMA stack (9<20<50)")
    if p > v9 > v20:
        return IndicatorSignal("EMA", v9, "BUY", 0.45, "Price above 9/20 EMA")
    if p < v9 < v20:
        return IndicatorSignal("EMA", v9, "SELL", -0.45, "Price below 9/20 EMA")
    return IndicatorSignal("EMA", v9, "NEUTRAL", 0.0, "EMAs mixed")


def _opening_context_signal(df_5m: pd.DataFrame, df_1d: pd.DataFrame) -> IndicatorSignal:
    if df_1d.empty or len(df_1d) < 2:
        return IndicatorSignal("Open/Gap", None, "NEUTRAL", 0.0, "No daily context")
    prev_close = float(df_1d["Close"].iloc[-2])
    today_open = float(df_1d["Open"].iloc[-1])
    gap_pct = (today_open - prev_close) / prev_close * 100 if prev_close else 0

    session = _session_bars(df_5m)
    or_high = or_low = None
    if len(session) >= 3:
        opening = session.head(3)
        or_high = float(opening["High"].max())
        or_low = float(opening["Low"].min())
    price = float(df_5m["Close"].iloc[-1])

    parts = []
    score = 0.0
    if gap_pct > 0.3:
        score += 0.4
        parts.append(f"Gap up {gap_pct:.1f}%")
    elif gap_pct < -0.3:
        score -= 0.4
        parts.append(f"Gap down {gap_pct:.1f}%")

    if or_high and or_low:
        if price > or_high:
            score += 0.5
            parts.append("Above opening range high")
        elif price < or_low:
            score -= 0.5
            parts.append("Below opening range low")
        else:
            parts.append("Inside opening range")

    if not parts:
        return IndicatorSignal("Open/Gap", gap_pct, "NEUTRAL", 0.0, "Flat open")
    sig = "BUY" if score > 0.2 else "SELL" if score < -0.2 else "NEUTRAL"
    return IndicatorSignal("Open/Gap", round(gap_pct, 2), sig, max(-1.0, min(1.0, score)), "; ".join(parts))


def _atr_volatility_signal(df: pd.DataFrame, price: float) -> IndicatorSignal:
    if len(df) < 15:
        return IndicatorSignal("ATR", None, "NEUTRAL", 0.0, "ATR unavailable")
    atr = float(ta.volatility.AverageTrueRange(df["High"], df["Low"], df["Close"], window=14).average_true_range().iloc[-1])
    atr_pct = atr / price * 100 if price else 0
    if atr_pct < 0.15:
        return IndicatorSignal("ATR", round(atr, 2), "NEUTRAL", -0.3, f"Low volatility ({atr_pct:.2f}%) — skip marginal setups")
    if atr_pct > 0.8:
        return IndicatorSignal("ATR", round(atr, 2), "NEUTRAL", -0.2, f"High volatility ({atr_pct:.2f}%) — wider stops needed")
    return IndicatorSignal("ATR", round(atr, 2), "NEUTRAL", 0.2, f"Tradeable volatility (ATR {atr_pct:.2f}%)")


def _rsi_exhaustion_signal(df: pd.DataFrame) -> IndicatorSignal:
    if len(df) < 20:
        return IndicatorSignal("RSI", None, "NEUTRAL", 0.0, "RSI unavailable")
    rsi = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
    value = float(rsi.iloc[-1])
    price_now = float(df["Close"].iloc[-1])
    price_prev = float(df["Close"].iloc[-8])
    rsi_prev = float(rsi.iloc[-8])
    if price_now > price_prev and value < rsi_prev - 5:
        return IndicatorSignal("RSI", value, "SELL", -0.6, f"Bearish RSI divergence ({value:.0f})")
    if price_now < price_prev and value > rsi_prev + 5:
        return IndicatorSignal("RSI", value, "BUY", 0.6, f"Bullish RSI divergence ({value:.0f})")
    if value > 75:
        return IndicatorSignal("RSI", value, "SELL", -0.4, f"Exhaustion overbought ({value:.0f})")
    if value < 25:
        return IndicatorSignal("RSI", value, "BUY", 0.4, f"Exhaustion oversold ({value:.0f})")
    return IndicatorSignal("RSI", value, "NEUTRAL", 0.0, f"RSI neutral ({value:.0f})")


def _candlestick_signal(df: pd.DataFrame) -> IndicatorSignal:
    if len(df) < 3:
        return IndicatorSignal("Candle", None, "NEUTRAL", 0.0, "No pattern")
    o, h, l, c = [float(df[col].iloc[-1]) for col in ("Open", "High", "Low", "Close")]
    body = abs(c - o)
    rng = h - l if h > l else 0.0001
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)

    po, ph, pl, pc = [float(df[col].iloc[-2]) for col in ("Open", "High", "Low", "Close")]

    if lower_wick > body * 2 and upper_wick < body and c > o:
        return IndicatorSignal("Candle", c, "BUY", 0.65, "Hammer — bullish rejection")
    if upper_wick > body * 2 and lower_wick < body and c < o:
        return IndicatorSignal("Candle", c, "SELL", -0.65, "Shooting star — bearish rejection")
    if c > o and pc < po and c > po and o < pc:
        return IndicatorSignal("Candle", c, "BUY", 0.75, "Bullish engulfing")
    if c < o and pc > po and c < po and o > pc:
        return IndicatorSignal("Candle", c, "SELL", -0.75, "Bearish engulfing")
    if body / rng > 0.85:
        sig = "BUY" if c > o else "SELL"
        sc = 0.4 if c > o else -0.4
        return IndicatorSignal("Candle", c, sig, sc, "Marubozu momentum bar")
    return IndicatorSignal("Candle", c, "NEUTRAL", 0.0, "No key candle pattern")


def _macd_confirm_signal(df: pd.DataFrame) -> IndicatorSignal:
    if len(df) < 26:
        return IndicatorSignal("MACD", None, "NEUTRAL", 0.0, "MACD unavailable")
    macd_ind = ta.trend.MACD(df["Close"])
    hist = float(macd_ind.macd_diff().iloc[-1])
    prev = float(macd_ind.macd_diff().iloc[-2])
    if prev < 0 < hist:
        return IndicatorSignal("MACD", hist, "BUY", 0.5, "MACD histogram turning up")
    if prev > 0 > hist:
        return IndicatorSignal("MACD", hist, "SELL", -0.5, "MACD histogram turning down")
    return IndicatorSignal("MACD", hist, "NEUTRAL", 0.0, "MACD neutral")


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


def _market_close_today() -> datetime:
    now_et = datetime.now(US_EASTERN)
    close_et = datetime.combine(now_et.date(), time(16, 0), tzinfo=US_EASTERN)
    if now_et >= close_et:
        close_et += timedelta(days=1)
        while close_et.weekday() >= 5:
            close_et += timedelta(days=1)
    return close_et.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def _too_late_for_entry() -> bool:
    now_et = datetime.now(US_EASTERN)
    cutoff = datetime.combine(now_et.date(), ENTRY_CUTOFF_ET, tzinfo=US_EASTERN)
    return now_et >= cutoff


def _factor_aligns_direction(ind: IndicatorSignal, want_long: bool) -> bool:
    if want_long:
        return ind.score >= 0.15
    return ind.score <= -0.15


def _has_core_confluence(indicators: list[IndicatorSignal], want_long: bool) -> bool:
    core = {"Structure", "VWAP", "EMA", "RVOL"}
    aligned = sum(
        1 for ind in indicators
        if ind.name in core and _factor_aligns_direction(ind, want_long)
    )
    return aligned >= MIN_CORE_CONFLUENCE


def _build_trade_plan(direction: Direction, price: float, atr: float, score: float) -> IntradayTradePlan:
    min_stop_dist = price * MIN_STOP_PCT / 100
    stop_dist = max(atr * STOP_ATR_MULT, min_stop_dist)
    if direction == Direction.LONG:
        stop = round(price - stop_dist, 2)
        t1 = round(price + stop_dist * 1.5, 2)
        t2 = round(price + stop_dist * 2.5, 2)
    else:
        stop = round(price + stop_dist, 2)
        t1 = round(price - stop_dist * 1.5, 2)
        t2 = round(price - stop_dist * 2.5, 2)

    risk = abs(price - stop)
    reward = abs(t1 - price)
    rr = round(reward / risk, 2) if risk > 0 else 0
    hold = 45 if abs(score) < 0.5 else 90
    if abs(score) >= 0.6:
        hold = 120

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
        expires_at=_market_close_today().isoformat(),
    )


def trade_plan_to_dict(plan: IntradayTradePlan | None) -> dict | None:
    if not plan:
        return None
    return asdict(plan)


def analyze_intraday(symbol: str, df_5m: pd.DataFrame, df_15m: pd.DataFrame, df_1d: pd.DataFrame) -> IntradaySignal:
    if len(df_5m) < 30:
        raise ValueError(f"Not enough 5m data for {symbol}")

    price = float(df_5m["Close"].iloc[-1])
    vwap = _calc_vwap(df_5m)
    daily_trend = _daily_trend(df_1d)

    indicators = [
        _swing_structure(df_15m if len(df_15m) >= 30 else df_5m),
        _vwap_signal(price, vwap),
        _volume_signal(df_5m),
        _ema_alignment_signal(df_15m if len(df_15m) >= 50 else df_5m),
        _opening_context_signal(df_5m, df_1d),
        _atr_volatility_signal(df_5m, price),
        _rsi_exhaustion_signal(df_5m),
        _candlestick_signal(df_5m),
        _macd_confirm_signal(df_5m),
    ]

    name_map = INDICATOR_KEYS

    score = 0.0
    for ind in indicators:
        key = name_map.get(ind.name, ind.name.lower())
        weight = WEIGHTS.get(key, 0.05)
        score += ind.score * weight

    if daily_trend == "bullish":
        score += 0.05
    elif daily_trend == "bearish":
        score -= 0.05

    atr_val = float(
        ta.volatility.AverageTrueRange(df_5m["High"], df_5m["Low"], df_5m["Close"], window=14)
        .average_true_range()
        .iloc[-1]
    )
    rvol_ind = next((i for i in indicators if i.name == "RVOL"), None)
    rvol = rvol_ind.value if rvol_ind else None

    confidence = min(abs(score) / 0.55 * 100, 100)

    direction = Direction.HOLD
    actionable = False
    plan = None

    atr_ind = next((i for i in indicators if i.name == "ATR"), None)
    low_vol = bool(atr_ind and atr_ind.score < 0)
    late_entry = _too_late_for_entry()

    long_ok = (
        score >= INTRADAY_MIN_SCORE
        and confidence >= INTRADAY_MIN_CONFIDENCE
        and not low_vol
        and not late_entry
        and daily_trend != "bearish"
        and _has_core_confluence(indicators, want_long=True)
    )
    short_ok = (
        score <= -INTRADAY_MIN_SCORE
        and confidence >= INTRADAY_MIN_CONFIDENCE
        and not low_vol
        and not late_entry
        and daily_trend != "bullish"
        and _has_core_confluence(indicators, want_long=False)
    )

    if long_ok:
        direction = Direction.LONG
        actionable = True
        plan = _build_trade_plan(Direction.LONG, price, atr_val, score)
        summary = (
            f"LONG — score {score:.2f}, {confidence:.0f}% confidence. "
            f"Entry {plan.entry_price}, T1 {plan.target_1} (+{plan.target_1_pct}%), "
            f"stop {plan.stop_loss} (−{plan.stop_pct}%), ~{plan.hold_minutes} min hold."
        )
    elif short_ok:
        direction = Direction.SHORT
        actionable = True
        plan = _build_trade_plan(Direction.SHORT, price, atr_val, score)
        summary = (
            f"SHORT — score {score:.2f}, {confidence:.0f}% confidence. "
            f"Entry {plan.entry_price}, T1 {plan.target_1} ({plan.target_1_pct}%), "
            f"stop {plan.stop_loss}, ~{plan.hold_minutes} min hold."
        )
    elif late_entry:
        summary = "No new intraday entries after 3:00 PM ET — not enough time to reach targets."
    elif daily_trend == "bearish" and score >= INTRADAY_MIN_SCORE:
        summary = "Long setup blocked — daily trend is bearish (trade with the higher timeframe)."
    elif daily_trend == "bullish" and score <= -INTRADAY_MIN_SCORE:
        summary = "Short setup blocked — daily trend is bullish (trade with the higher timeframe)."
    elif score >= INTRADAY_MIN_SCORE or score <= -INTRADAY_MIN_SCORE:
        summary = (
            "Score reached threshold but core factors lack confluence — "
            "need 3+ of structure, VWAP, EMA, and RVOL aligned."
        )
    else:
        summary = "No high-probability intraday setup — wait for VWAP + structure alignment."

    why_headline, trade_reasons, reasoning = build_trade_reasons(
        indicators, daily_trend, direction, score, confidence, actionable, low_vol
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
        rvol=rvol,
        daily_trend=daily_trend,
    )
