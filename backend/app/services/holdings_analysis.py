"""Sell/hold advice for stocks the user already owns."""

from dataclasses import asdict
from datetime import datetime

from app.models import HoldingItem
from app.services.signals import Action, TradeSignal, signal_outlook_to_dict, trade_plan_to_dict


def holding_to_dict(holding: HoldingItem) -> dict:
    return {
        "id": holding.id,
        "symbol": holding.symbol,
        "market": holding.market,
        "name": holding.name,
        "avg_cost": holding.avg_cost,
        "shares": holding.shares,
        "purchase_date": holding.purchase_date.isoformat() if holding.purchase_date else None,
        "created_at": holding.created_at.isoformat() if holding.created_at else None,
    }


def build_holding_advice(signal: TradeSignal, holding: HoldingItem) -> dict:
    price = signal.price
    avg_cost = holding.avg_cost
    shares = holding.shares

    pnl_pct = round((price - avg_cost) / avg_cost * 100, 2) if avg_cost > 0 else None
    pnl_amount = round((price - avg_cost) * shares, 2) if shares and avg_cost > 0 else None

    action = signal.action
    outlook = signal.outlook

    if action == Action.STRONG_SELL:
        recommendation = "SELL"
        strength = "STRONG"
    elif action == Action.SELL:
        recommendation = "SELL"
        strength = "MODERATE"
    elif action in (Action.STRONG_BUY, Action.BUY):
        recommendation = "HOLD"
        strength = "BULLISH"
    else:
        recommendation = "HOLD"
        strength = "NEUTRAL"

    if recommendation == "SELL":
        if pnl_pct is not None and pnl_pct > 0:
            headline = f"Bearish signals — consider selling to lock in +{pnl_pct}% gain"
        elif pnl_pct is not None and pnl_pct < 0:
            headline = f"Bearish signals — consider selling to limit loss ({pnl_pct}%)"
        else:
            headline = "Bearish signals — consider reducing exposure"
    elif strength == "BULLISH":
        headline = "Bullish signals — hold for upside; no sell signal"
    else:
        headline = "Mixed signals — hold and wait for clearer direction"

    upper = outlook.upper_target if outlook else None
    lower = outlook.lower_target if outlook else None
    upper_pct = outlook.upper_pct if outlook else None
    lower_pct = outlook.lower_pct if outlook else None

    return {
        "recommendation": recommendation,
        "strength": strength,
        "headline": headline,
        "summary": signal.summary,
        "avg_cost": avg_cost,
        "current_price": price,
        "shares": shares,
        "unrealized_pnl_pct": pnl_pct,
        "unrealized_pnl": pnl_amount,
        "upper_target": upper,
        "lower_target": lower,
        "upper_pct": upper_pct,
        "lower_pct": lower_pct,
        "mid_level": outlook.mid_level if outlook else None,
        "range_note": outlook.range_note if outlook else None,
        "reasoning": outlook.reasoning if outlook else [],
        "confidence": signal.confidence,
        "score": signal.score,
    }


def signal_to_holding_payload(signal: TradeSignal, holding: HoldingItem) -> dict:
    return {
        "symbol": signal.symbol,
        "market": holding.market,
        "action": signal.action.value,
        "confidence": signal.confidence,
        "price": signal.price,
        "score": signal.score,
        "summary": signal.summary,
        "can_earn": signal.can_earn,
        "indicators": [asdict(i) for i in signal.indicators],
        "trade_plan": trade_plan_to_dict(signal.trade_plan) if signal.trade_plan else None,
        "outlook": signal_outlook_to_dict(signal.outlook) if signal.outlook else None,
        "holding": holding_to_dict(holding),
        "advice": build_holding_advice(signal, holding),
        "scanned_at": datetime.utcnow().isoformat(),
    }
