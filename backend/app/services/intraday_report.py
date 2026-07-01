"""Build downloadable intraday reports for algo review and tuning."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import IntradaySignalHistory, IntradayWatchlistItem
from app.services.intraday_history import (
    _parse_reasoning,
    get_intraday_stats,
    intraday_to_dict,
)
from app.services.intraday_monitor import get_cached_intraday_signals
from app.services.intraday_signals import INTRADAY_MIN_CONFIDENCE, INTRADAY_MIN_SCORE, WEIGHTS
from app.services.us_market_hours import market_status_to_dict
from app.version import __version__


def _trade_row(record: IntradaySignalHistory) -> dict:
    why_headline, trade_reasons, bullets = _parse_reasoning(record)
    base = intraday_to_dict(record)
    base.update({
        "why_headline": why_headline,
        "trade_reasons": trade_reasons,
        "reasoning": bullets,
        "highest_since": record.highest_since,
        "lowest_since": record.lowest_since,
        "mfe_pct": _mfe_pct(record),
        "mae_pct": _mae_pct(record),
    })
    return base


def _mfe_pct(record: IntradaySignalHistory) -> float | None:
    """Max favorable excursion (%)."""
    entry = record.entry_price
    if not entry:
        return None
    if record.direction == "LONG" and record.highest_since is not None:
        return round((record.highest_since - entry) / entry * 100, 2)
    if record.direction == "SHORT" and record.lowest_since is not None:
        return round((entry - record.lowest_since) / entry * 100, 2)
    return None


def _mae_pct(record: IntradaySignalHistory) -> float | None:
    """Max adverse excursion (%)."""
    entry = record.entry_price
    if not entry:
        return None
    if record.direction == "LONG" and record.lowest_since is not None:
        return round((record.lowest_since - entry) / entry * 100, 2)
    if record.direction == "SHORT" and record.highest_since is not None:
        return round((entry - record.highest_since) / entry * 100, 2)
    return None


def _is_win(record: IntradaySignalHistory) -> bool:
    return record.status in ("target_hit", "target_2_hit")


def _factor_aligns(direction: str, bias: str) -> bool:
    if bias == "NEUTRAL":
        return False
    return (direction == "LONG" and bias == "BULLISH") or (direction == "SHORT" and bias == "BEARISH")


def _bucket_confidence(c: float) -> str:
    if c < 45:
        return "35-44%"
    if c < 60:
        return "45-59%"
    return "60%+"


def _bucket_score(s: float) -> str:
    abs_s = abs(s)
    if abs_s < 0.35:
        return "0.30-0.34"
    if abs_s < 0.50:
        return "0.35-0.49"
    return "0.50+"


def _analyze_closed_trades(rows: list[IntradaySignalHistory]) -> dict:
    closed = [r for r in rows if r.status != "open"]
    if not closed:
        return {
            "sample_size": 0,
            "by_direction": {},
            "by_confidence": {},
            "by_score": {},
            "by_status": {},
            "by_factor_alignment": {},
            "avg_mfe_pct": None,
            "avg_mae_pct": None,
            "insights": ["No closed intraday trades yet — run the model during market hours to build data."],
        }

    by_dir: dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "avg_result_pct": 0.0})
    by_conf: dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0})
    by_score: dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0})
    by_status: dict[str, int] = defaultdict(int)
    factor_stats: dict[str, dict] = defaultdict(lambda: {"aligned_wins": 0, "aligned_losses": 0, "misaligned_wins": 0, "misaligned_losses": 0})

    mfe_vals: list[float] = []
    mae_vals: list[float] = []

    for r in closed:
        win = _is_win(r)
        by_dir[r.direction]["trades"] += 1
        by_dir[r.direction]["wins"] += int(win)
        by_dir[r.direction]["avg_result_pct"] += r.result_pct or 0
        by_conf[_bucket_confidence(r.confidence)]["trades"] += 1
        by_conf[_bucket_confidence(r.confidence)]["wins"] += int(win)
        by_score[_bucket_score(r.score)]["trades"] += 1
        by_score[_bucket_score(r.score)]["wins"] += int(win)
        by_status[r.status] += 1

        mfe = _mfe_pct(r)
        mae = _mae_pct(r)
        if mfe is not None:
            mfe_vals.append(mfe)
        if mae is not None:
            mae_vals.append(mae)

        _, reasons, _ = _parse_reasoning(r)
        for reason in reasons:
            factor = reason.get("factor", "Unknown")
            bias = reason.get("bias", "NEUTRAL")
            aligned = _factor_aligns(r.direction, bias)
            key = "aligned" if aligned else "misaligned"
            sub = "wins" if win else "losses"
            factor_stats[factor][f"{key}_{sub}"] += 1

    for d in by_dir.values():
        if d["trades"]:
            d["win_rate"] = round(d["wins"] / d["trades"] * 100, 1)
            d["avg_result_pct"] = round(d["avg_result_pct"] / d["trades"], 2)
        else:
            d["win_rate"] = 0.0

    for bucket in by_conf.values():
        bucket["win_rate"] = round(bucket["wins"] / bucket["trades"] * 100, 1) if bucket["trades"] else 0.0

    for bucket in by_score.values():
        bucket["win_rate"] = round(bucket["wins"] / bucket["trades"] * 100, 1) if bucket["trades"] else 0.0

    factor_alignment = {}
    for factor, stats in sorted(factor_stats.items()):
        aligned_total = stats["aligned_wins"] + stats["aligned_losses"]
        misaligned_total = stats["misaligned_wins"] + stats["misaligned_losses"]
        factor_alignment[factor] = {
            **stats,
            "aligned_win_rate": round(stats["aligned_wins"] / aligned_total * 100, 1) if aligned_total else None,
            "misaligned_win_rate": round(stats["misaligned_wins"] / misaligned_total * 100, 1) if misaligned_total else None,
        }

    insights = _build_insights(closed, by_dir, by_conf, by_status, factor_alignment, mfe_vals, mae_vals)

    return {
        "sample_size": len(closed),
        "by_direction": dict(by_dir),
        "by_confidence": dict(by_conf),
        "by_score": dict(by_score),
        "by_status": dict(by_status),
        "by_factor_alignment": factor_alignment,
        "avg_mfe_pct": round(sum(mfe_vals) / len(mfe_vals), 2) if mfe_vals else None,
        "avg_mae_pct": round(sum(mae_vals) / len(mae_vals), 2) if mae_vals else None,
        "insights": insights,
    }


def _build_insights(
    closed: list[IntradaySignalHistory],
    by_dir: dict,
    by_conf: dict,
    by_status: dict,
    factor_alignment: dict,
    mfe_vals: list[float],
    mae_vals: list[float],
) -> list[str]:
    insights: list[str] = []
    n = len(closed)
    wins = sum(1 for r in closed if _is_win(r))
    overall_wr = wins / n * 100

    insights.append(f"Closed sample: {n} trades, {overall_wr:.1f}% hit target 1 or 2.")

    long = by_dir.get("LONG", {})
    short = by_dir.get("SHORT", {})
    if long.get("trades", 0) >= 3 and short.get("trades", 0) >= 3:
        if long.get("win_rate", 0) - short.get("win_rate", 0) >= 15:
            insights.append(
                f"LONG win rate ({long['win_rate']}%) beats SHORT ({short['win_rate']}%) — "
                "consider stricter SHORT filters or lower short-side weight in scoring."
            )
        elif short.get("win_rate", 0) - long.get("win_rate", 0) >= 15:
            insights.append(
                f"SHORT win rate ({short['win_rate']}%) beats LONG ({long['win_rate']}%) — "
                "review long entry criteria (VWAP / structure alignment)."
            )

    low_conf = by_conf.get("35-44%", {})
    high_conf = by_conf.get("60%+", {})
    if low_conf.get("trades", 0) >= 3 and high_conf.get("trades", 0) >= 2:
        if low_conf.get("win_rate", 0) < high_conf.get("win_rate", 0) - 10:
            insights.append(
                f"Low-confidence band (35-44%) win rate is {low_conf['win_rate']}% vs "
                f"{high_conf.get('win_rate', 0)}% for 60%+ — raising INTRADAY_MIN_CONFIDENCE may help."
            )

    stops = by_status.get("stop_hit", 0)
    if n >= 5 and stops / n >= 0.45:
        insights.append(
            f"{stops}/{n} trades stopped out ({round(stops/n*100)}%) — "
            "review ATR stop multiplier (currently 1× ATR) or require stronger structure before entry."
        )

    expired = by_status.get("expired_loss", 0) + by_status.get("expired_win", 0)
    if n >= 5 and expired / n >= 0.35:
        insights.append(
            f"{expired}/{n} trades expired at session close — "
            "targets may be too far or entries too late; consider tighter T1 or earlier-session filter."
        )

    if mfe_vals and mae_vals:
        avg_mfe = sum(mfe_vals) / len(mfe_vals)
        avg_mae = abs(sum(mae_vals) / len(mae_vals))
        if avg_mfe > 1.0 and stops / max(n, 1) >= 0.3:
            insights.append(
                f"Avg max favorable move was +{avg_mfe:.2f}% but many stops hit — "
                "trades often go right before reversing; trailing stop or partial at T1 could be tested."
            )
        if avg_mae > avg_mfe * 0.8 and wins / max(n, 1) < 0.5:
            insights.append(
                f"Avg max adverse excursion ({avg_mae:.2f}%) is large relative to favorable move — "
                "entries may be chasing; tighten VWAP/EMA confluence requirements."
            )

    best_factor = None
    best_wr = -1.0
    worst_factor = None
    worst_wr = 101.0
    for factor, stats in factor_alignment.items():
        if factor == "Daily trend (context)":
            continue
        total = stats["aligned_wins"] + stats["aligned_losses"]
        if total < 3:
            continue
        wr = stats["aligned_win_rate"] or 0
        if wr > best_wr:
            best_wr = wr
            best_factor = factor
        if wr < worst_wr:
            worst_wr = wr
            worst_factor = factor

    if best_factor:
        insights.append(f"Strongest aligned factor: {best_factor} ({best_wr}% win rate when aligned with trade direction).")
    if worst_factor and worst_wr < 40:
        insights.append(
            f"Weakest aligned factor: {worst_factor} ({worst_wr}% win rate) — "
            "consider lowering its weight or requiring confirmation from other factors."
        )

    if len(insights) == 1:
        insights.append(
            "More closed trades needed for deeper factor analysis — keep the watchlist active during US market hours."
        )

    return insights


def build_intraday_report(db: Session) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    all_rows = (
        db.query(IntradaySignalHistory)
        .order_by(IntradaySignalHistory.created_at.desc())
        .all()
    )
    watchlist = db.query(IntradayWatchlistItem).order_by(IntradayWatchlistItem.symbol).all()
    live_signals, last_scan = get_cached_intraday_signals()
    stats = get_intraday_stats(db)

    trades = [_trade_row(r) for r in all_rows]
    open_trades = [t for t in trades if t["status"] == "open"]
    closed_trades = [t for t in trades if t["status"] != "open"]

    return {
        "report_type": "shizu_intraday_algo_review",
        "generated_at": now,
        "app_version": __version__,
        "market": market_status_to_dict(),
        "model": {
            "name": "US intraday ORB + VWAP playbook",
            "min_confidence": INTRADAY_MIN_CONFIDENCE,
            "min_score": INTRADAY_MIN_SCORE,
            "factor_weights": WEIGHTS,
            "scan_interval_minutes": 2,
            "session": "US regular 9:30-16:00 ET",
        },
        "watchlist": [
            {"symbol": w.symbol, "name": w.name, "created_at": w.created_at.isoformat()}
            for w in watchlist
        ],
        "summary": stats,
        "live_signals": {
            "last_scan": last_scan.isoformat() if last_scan else None,
            "signals": live_signals,
            "actionable_count": sum(1 for s in live_signals if s.get("actionable")),
        },
        "trades": {
            "total": len(trades),
            "open": open_trades,
            "closed": closed_trades,
        },
        "analysis": _analyze_closed_trades(all_rows),
        "tuning_notes": [
            "Share this JSON with an analyst or AI to review factor weights and entry rules.",
            "Compare by_direction and by_confidence win rates before changing thresholds.",
            "Use mfe_pct / mae_pct per trade to see if stops are too tight or targets too wide.",
            "Factor alignment stats show which indicators correlate with wins when they agree with trade direction.",
        ],
    }


def report_to_csv(report: dict) -> str:
    """Flat trade log for spreadsheets."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "symbol", "name", "direction", "status", "success",
        "entry_price", "exit_price", "stop_loss", "target_1", "target_2",
        "result_pct", "mfe_pct", "mae_pct", "confidence", "score",
        "risk_reward", "hold_minutes", "trade_date", "created_at", "closed_at",
        "why_headline", "aligned_factors", "summary",
    ])

    for section in ("open", "closed"):
        for t in report["trades"].get(section, []):
            aligned = [
                r["factor"]
                for r in (t.get("trade_reasons") or [])
                if _factor_aligns(t["direction"], r.get("bias", "NEUTRAL"))
            ]
            writer.writerow([
                t.get("id"),
                t.get("symbol"),
                t.get("name") or "",
                t.get("direction"),
                t.get("status"),
                t.get("success"),
                t.get("entry_price"),
                t.get("exit_price"),
                t.get("stop_loss"),
                t.get("target_1"),
                t.get("target_2"),
                t.get("result_pct"),
                t.get("mfe_pct"),
                t.get("mae_pct"),
                t.get("confidence"),
                t.get("score"),
                t.get("risk_reward"),
                t.get("hold_minutes"),
                t.get("trade_date"),
                t.get("created_at"),
                t.get("closed_at") or "",
                t.get("why_headline") or "",
                "; ".join(aligned),
                t.get("summary") or "",
            ])

    writer.writerow([])
    writer.writerow(["# Analysis insights"])
    for line in report.get("analysis", {}).get("insights", []):
        writer.writerow([line])

    return buf.getvalue()


def report_filename(fmt: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = "csv" if fmt == "csv" else "json"
    return f"shizu_intraday_report_{stamp}.{ext}"
