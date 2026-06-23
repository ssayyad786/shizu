"""Multi-indicator signal engine for short-term swing trading."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

import numpy as np
import pandas as pd
import ta

SHORT_TERM_HOLD_DAYS = 10


class Action(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class IndicatorSignal:
    name: str
    value: float | None
    signal: str
    score: float
    detail: str


@dataclass
class TradePlan:
    entry_price: float
    sell_target: float
    stop_loss: float
    target_pct: float
    stop_pct: float
    atr: float
    hold_days: int
    expires_at: str


@dataclass
class TradeSignal:
    symbol: str
    action: Action
    confidence: float
    price: float
    score: float
    indicators: list[IndicatorSignal]
    summary: str
    can_earn: bool
    trade_plan: TradePlan | None = None


def _rsi_signal(df: pd.DataFrame) -> IndicatorSignal:
    rsi = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
    value = float(rsi.iloc[-1])
    if value < 30:
        return IndicatorSignal("RSI", value, "BUY", 0.8, f"Oversold at {value:.1f}")
    if value < 40:
        return IndicatorSignal("RSI", value, "BUY", 0.4, f"Approaching oversold at {value:.1f}")
    if value > 70:
        return IndicatorSignal("RSI", value, "SELL", -0.8, f"Overbought at {value:.1f}")
    if value > 60:
        return IndicatorSignal("RSI", value, "SELL", -0.4, f"Approaching overbought at {value:.1f}")
    return IndicatorSignal("RSI", value, "NEUTRAL", 0.0, f"Neutral at {value:.1f}")


def _macd_signal(df: pd.DataFrame) -> IndicatorSignal:
    macd_ind = ta.trend.MACD(df["Close"])
    macd = macd_ind.macd()
    signal_line = macd_ind.macd_signal()
    hist = macd_ind.macd_diff()

    curr_hist = float(hist.iloc[-1])
    prev_hist = float(hist.iloc[-2])
    curr_macd = float(macd.iloc[-1])
    curr_signal = float(signal_line.iloc[-1])

    if prev_hist < 0 and curr_hist > 0:
        return IndicatorSignal("MACD", curr_hist, "BUY", 0.9, "Bullish crossover — momentum turning up")
    if prev_hist > 0 and curr_hist < 0:
        return IndicatorSignal("MACD", curr_hist, "SELL", -0.9, "Bearish crossover — momentum turning down")
    if curr_macd > curr_signal and curr_hist > 0:
        return IndicatorSignal("MACD", curr_hist, "BUY", 0.5, "MACD above signal line")
    if curr_macd < curr_signal and curr_hist < 0:
        return IndicatorSignal("MACD", curr_hist, "SELL", -0.5, "MACD below signal line")
    return IndicatorSignal("MACD", curr_hist, "NEUTRAL", 0.0, "No clear MACD trend")


def _ema_crossover_signal(df: pd.DataFrame) -> IndicatorSignal:
    ema9 = ta.trend.EMAIndicator(df["Close"], window=9).ema_indicator()
    ema21 = ta.trend.EMAIndicator(df["Close"], window=21).ema_indicator()

    curr9, curr21 = float(ema9.iloc[-1]), float(ema21.iloc[-1])
    prev9, prev21 = float(ema9.iloc[-2]), float(ema21.iloc[-2])

    if prev9 <= prev21 and curr9 > curr21:
        return IndicatorSignal("EMA 9/21", curr9 - curr21, "BUY", 0.85, "Golden cross — short EMA crossed above long EMA")
    if prev9 >= prev21 and curr9 < curr21:
        return IndicatorSignal("EMA 9/21", curr9 - curr21, "SELL", -0.85, "Death cross — short EMA crossed below long EMA")
    if curr9 > curr21:
        return IndicatorSignal("EMA 9/21", curr9 - curr21, "BUY", 0.3, "Price in uptrend (EMA9 > EMA21)")
    if curr9 < curr21:
        return IndicatorSignal("EMA 9/21", curr9 - curr21, "SELL", -0.3, "Price in downtrend (EMA9 < EMA21)")
    return IndicatorSignal("EMA 9/21", 0.0, "NEUTRAL", 0.0, "EMAs converging")


def _bollinger_signal(df: pd.DataFrame) -> IndicatorSignal:
    bb = ta.volatility.BollingerBands(df["Close"], window=20, window_dev=2)
    upper = float(bb.bollinger_hband().iloc[-1])
    lower = float(bb.bollinger_lband().iloc[-1])
    mid = float(bb.bollinger_mavg().iloc[-1])
    price = float(df["Close"].iloc[-1])

    band_width = (upper - lower) / mid if mid else 0
    position = (price - lower) / (upper - lower) if upper != lower else 0.5

    if position < 0.1:
        return IndicatorSignal("Bollinger", position, "BUY", 0.7, f"Price near lower band — potential bounce (width {band_width:.2%})")
    if position > 0.9:
        return IndicatorSignal("Bollinger", position, "SELL", -0.7, f"Price near upper band — potential pullback")
    return IndicatorSignal("Bollinger", position, "NEUTRAL", 0.0, "Price within normal band range")


def _volume_signal(df: pd.DataFrame) -> IndicatorSignal:
    vol = df["Volume"].astype(float)
    avg_vol = vol.rolling(20).mean()
    curr_vol = float(vol.iloc[-1])
    avg = float(avg_vol.iloc[-1]) if not np.isnan(avg_vol.iloc[-1]) else curr_vol
    ratio = curr_vol / avg if avg > 0 else 1.0
    price_change = float(df["Close"].iloc[-1]) - float(df["Close"].iloc[-2])

    if ratio > 1.5 and price_change > 0:
        return IndicatorSignal("Volume", ratio, "BUY", 0.6, f"High volume on up day ({ratio:.1f}x avg)")
    if ratio > 1.5 and price_change < 0:
        return IndicatorSignal("Volume", ratio, "SELL", -0.6, f"High volume on down day ({ratio:.1f}x avg)")
    return IndicatorSignal("Volume", ratio, "NEUTRAL", 0.0, "Normal volume")


def _stochastic_signal(df: pd.DataFrame) -> IndicatorSignal:
    stoch = ta.momentum.StochasticOscillator(df["High"], df["Low"], df["Close"], window=14, smooth_window=3)
    k = float(stoch.stoch().iloc[-1])
    d = float(stoch.stoch_signal().iloc[-1])

    if k < 20 and k > d:
        return IndicatorSignal("Stochastic", k, "BUY", 0.75, f"Oversold at {k:.1f} and turning up")
    if k < 20:
        return IndicatorSignal("Stochastic", k, "BUY", 0.5, f"Oversold at {k:.1f}")
    if k > 80 and k < d:
        return IndicatorSignal("Stochastic", k, "SELL", -0.75, f"Overbought at {k:.1f} and turning down")
    if k > 80:
        return IndicatorSignal("Stochastic", k, "SELL", -0.5, f"Overbought at {k:.1f}")
    return IndicatorSignal("Stochastic", k, "NEUTRAL", 0.0, f"Neutral at {k:.1f}")


def _adx_signal(df: pd.DataFrame) -> IndicatorSignal:
    adx_ind = ta.trend.ADXIndicator(df["High"], df["Low"], df["Close"], window=14)
    adx = float(adx_ind.adx().iloc[-1])
    plus_di = float(adx_ind.adx_pos().iloc[-1])
    minus_di = float(adx_ind.adx_neg().iloc[-1])

    if adx > 25 and plus_di > minus_di:
        return IndicatorSignal("ADX", adx, "BUY", 0.7, f"Strong uptrend (ADX {adx:.1f}, +DI > -DI)")
    if adx > 25 and minus_di > plus_di:
        return IndicatorSignal("ADX", adx, "SELL", -0.7, f"Strong downtrend (ADX {adx:.1f}, -DI > +DI)")
    if adx < 20:
        return IndicatorSignal("ADX", adx, "NEUTRAL", 0.0, f"Weak trend (ADX {adx:.1f}) — wait for clarity")
    if plus_di > minus_di:
        return IndicatorSignal("ADX", adx, "BUY", 0.3, f"Mild bullish bias (ADX {adx:.1f})")
    return IndicatorSignal("ADX", adx, "SELL", -0.3, f"Mild bearish bias (ADX {adx:.1f})")


WEIGHTS = {
    "RSI": 0.14,
    "MACD": 0.18,
    "EMA 9/21": 0.18,
    "Bollinger": 0.12,
    "Volume": 0.12,
    "Stochastic": 0.14,
    "ADX": 0.12,
}


def calculate_trade_plan(df: pd.DataFrame, entry_price: float, action: Action) -> TradePlan:
    """ATR-based short-term targets: sell target and stop loss."""
    atr_ind = ta.volatility.AverageTrueRange(df["High"], df["Low"], df["Close"], window=14)
    atr_val = float(atr_ind.average_true_range().iloc[-1])
    if np.isnan(atr_val) or atr_val <= 0:
        atr_val = entry_price * 0.02

    reward_mult = 2.0 if action == Action.STRONG_BUY else 1.5
    sell_target = round(entry_price + reward_mult * atr_val, 2)
    stop_loss = round(entry_price - 1.0 * atr_val, 2)
    target_pct = round((sell_target - entry_price) / entry_price * 100, 2)
    stop_pct = round((entry_price - stop_loss) / entry_price * 100, 2)

    expires = datetime.utcnow() + timedelta(days=SHORT_TERM_HOLD_DAYS)
    return TradePlan(
        entry_price=round(entry_price, 2),
        sell_target=sell_target,
        stop_loss=stop_loss,
        target_pct=target_pct,
        stop_pct=stop_pct,
        atr=round(atr_val, 2),
        hold_days=SHORT_TERM_HOLD_DAYS,
        expires_at=expires.isoformat(),
    )


def trade_plan_to_dict(plan: TradePlan) -> dict:
    return {
        "entry_price": plan.entry_price,
        "sell_target": plan.sell_target,
        "stop_loss": plan.stop_loss,
        "target_pct": plan.target_pct,
        "stop_pct": plan.stop_pct,
        "atr": plan.atr,
        "hold_days": plan.hold_days,
        "expires_at": plan.expires_at,
    }


def analyze(symbol: str, df: pd.DataFrame) -> TradeSignal:
    if len(df) < 30:
        raise ValueError(f"Not enough data for {symbol} (need at least 30 bars)")

    indicators = [
        _rsi_signal(df),
        _macd_signal(df),
        _ema_crossover_signal(df),
        _bollinger_signal(df),
        _volume_signal(df),
        _stochastic_signal(df),
        _adx_signal(df),
    ]

    score = sum(ind.score * WEIGHTS[ind.name] for ind in indicators)
    price = float(df["Close"].iloc[-1])

    if score >= 0.45:
        action = Action.STRONG_BUY
    elif score >= 0.20:
        action = Action.BUY
    elif score <= -0.45:
        action = Action.STRONG_SELL
    elif score <= -0.20:
        action = Action.SELL
    else:
        action = Action.HOLD

    confidence = min(abs(score) / 0.6 * 100, 100)
    can_earn = action in (Action.STRONG_BUY, Action.BUY)

    bullish = [i for i in indicators if i.score > 0]
    bearish = [i for i in indicators if i.score < 0]

    plan = None
    if can_earn:
        plan = calculate_trade_plan(df, price, action)
        reasons = ", ".join(i.name for i in bullish[:3])
        summary = (
            f"BUY signal — {len(bullish)} bullish indicators ({reasons}). "
            f"Target +{plan.target_pct}% at {plan.sell_target}, stop −{plan.stop_pct}% at {plan.stop_loss}."
        )
    elif action in (Action.SELL, Action.STRONG_SELL):
        reasons = ", ".join(i.name for i in bearish[:3])
        summary = f"Caution — {len(bearish)} bearish signals ({reasons}). Consider reducing exposure."
    else:
        summary = "No clear opportunity — hold and wait for stronger signals."

    return TradeSignal(
        symbol=symbol,
        action=action,
        confidence=round(confidence, 1),
        price=round(price, 2),
        score=round(score, 3),
        indicators=indicators,
        summary=summary,
        can_earn=can_earn,
        trade_plan=plan,
    )


def compute_chart_indicators(df: pd.DataFrame) -> dict:
    close = df["Close"]
    ema9 = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    ema21 = ta.trend.EMAIndicator(close, window=21).ema_indicator()
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    macd_ind = ta.trend.MACD(close)
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    stoch = ta.momentum.StochasticOscillator(df["High"], df["Low"], close, window=14, smooth_window=3)

    def series_to_list(s: pd.Series) -> list[float | None]:
        return [None if np.isnan(v) else round(float(v), 4) for v in s]

    return {
        "ema9": series_to_list(ema9),
        "ema21": series_to_list(ema21),
        "rsi": series_to_list(rsi),
        "macd": series_to_list(macd_ind.macd()),
        "macd_signal": series_to_list(macd_ind.macd_signal()),
        "macd_hist": series_to_list(macd_ind.macd_diff()),
        "bb_upper": series_to_list(bb.bollinger_hband()),
        "bb_lower": series_to_list(bb.bollinger_lband()),
        "bb_mid": series_to_list(bb.bollinger_mavg()),
        "stoch_k": series_to_list(stoch.stoch()),
        "stoch_d": series_to_list(stoch.stoch_signal()),
    }
