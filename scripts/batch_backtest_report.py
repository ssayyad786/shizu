#!/usr/bin/env python3
"""Batch ORB backtest report for all watchlist symbols over recent trading days."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

BASE = "https://shizu.space"
ET = ZoneInfo("America/New_York")


def _get_json(path: str) -> dict | list:
    req = urllib.request.Request(f"{BASE}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def _trading_days(count: int, end: date | None = None) -> list[date]:
    end = end or datetime.now(ET).date()
    days: list[date] = []
    d = end
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def _fetch_backtest(symbol: str, day: date) -> dict:
    ds = day.isoformat()
    url = f"{BASE}/api/intraday/backtest?symbol={symbol}&date={ds}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
        return {"symbol": symbol, "date": ds, "ok": True, **data}
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else str(e)
        return {"symbol": symbol, "date": ds, "ok": False, "error": body[:200]}
    except Exception as e:
        return {"symbol": symbol, "date": ds, "ok": False, "error": str(e)}


def build_report(days: int = 5, workers: int = 6) -> dict:
    watchlist = _get_json("/api/intraday/watchlist")
    symbols = [w["symbol"] for w in watchlist]
    trade_days = _trading_days(days)

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_fetch_backtest, sym, d) for sym in symbols for d in trade_days]
        for i, fut in enumerate(as_completed(futures), 1):
            results.append(fut.result())
            if i % 20 == 0:
                print(f"  {i}/{len(futures)} backtests done...", file=sys.stderr)

    traded = [r for r in results if r.get("ok") and r.get("traded")]
    no_trade = [r for r in results if r.get("ok") and not r.get("traded")]
    errors = [r for r in results if not r.get("ok")]

    wins = [r for r in traded if r.get("outcome", {}).get("success")]
    losses = [r for r in traded if r.get("traded") and not r.get("outcome", {}).get("success")]

    total_pct = sum(r.get("outcome", {}).get("result_pct", 0) for r in traded)
    avg_pct = round(total_pct / len(traded), 3) if traded else 0.0

    by_day: dict[str, dict] = {}
    for d in trade_days:
        ds = d.isoformat()
        day_rows = [r for r in traded if r["date"] == ds]
        day_wins = [r for r in day_rows if r.get("outcome", {}).get("success")]
        by_day[ds] = {
            "trades": len(day_rows),
            "wins": len(day_wins),
            "win_rate": round(len(day_wins) / len(day_rows) * 100, 1) if day_rows else 0,
            "avg_result_pct": round(
                sum(r["outcome"]["result_pct"] for r in day_rows) / len(day_rows), 3
            ) if day_rows else 0,
            "symbols_traded": [r["symbol"] for r in day_rows],
        }

    by_symbol: dict[str, dict] = {}
    for sym in symbols:
        sym_rows = [r for r in traded if r["symbol"] == sym]
        sym_wins = [r for r in sym_rows if r.get("outcome", {}).get("success")]
        by_symbol[sym] = {
            "trades": len(sym_rows),
            "wins": len(sym_wins),
            "win_rate": round(len(sym_wins) / len(sym_rows) * 100, 1) if sym_rows else 0,
            "total_result_pct": round(sum(r["outcome"]["result_pct"] for r in sym_rows), 3),
            "details": [
                {
                    "date": r["date"],
                    "direction": r.get("signal", {}).get("direction"),
                    "entry": r.get("trade_plan", {}).get("entry_price"),
                    "status": r.get("outcome", {}).get("status"),
                    "result_pct": r.get("outcome", {}).get("result_pct"),
                    "summary": (r.get("signal", {}).get("summary") or "")[:100],
                }
                for r in sorted(sym_rows, key=lambda x: x["date"])
            ],
        }

    top_winners = sorted(traded, key=lambda r: r.get("outcome", {}).get("result_pct", 0), reverse=True)[:15]
    top_losers = sorted(traded, key=lambda r: r.get("outcome", {}).get("result_pct", 0))[:15]

    app_version = traded[0].get("app_version") if traded else (results[0].get("app_version") if results else "?")

    return {
        "report_type": "shizu_orb_batch_backtest",
        "generated_at": datetime.now(ET).isoformat(),
        "server": BASE,
        "app_version": app_version,
        "model": "ORB + VWAP playbook (v1.6.2)",
        "watchlist_count": len(symbols),
        "symbols": symbols,
        "trading_days": [d.isoformat() for d in trade_days],
        "summary": {
            "backtests_run": len(results),
            "errors": len(errors),
            "traded": len(traded),
            "no_trade": len(no_trade),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(traded) * 100, 1) if traded else 0,
            "avg_result_pct": avg_pct,
            "total_result_pct": round(total_pct, 3),
        },
        "by_day": by_day,
        "by_symbol": by_symbol,
        "top_winners": [
            {
                "symbol": r["symbol"],
                "date": r["date"],
                "result_pct": r["outcome"]["result_pct"],
                "status": r["outcome"]["status"],
                "direction": r.get("signal", {}).get("direction"),
            }
            for r in top_winners
        ],
        "top_losers": [
            {
                "symbol": r["symbol"],
                "date": r["date"],
                "result_pct": r["outcome"]["result_pct"],
                "status": r["outcome"]["status"],
                "direction": r.get("signal", {}).get("direction"),
            }
            for r in top_losers
        ],
        "errors_sample": errors[:10],
        "raw_trades": [
            {
                "symbol": r["symbol"],
                "date": r["date"],
                "direction": r.get("signal", {}).get("direction"),
                "entry_time": r.get("entry_time_et", "")[11:16] if r.get("entry_time_et") else None,
                "entry_price": r.get("trade_plan", {}).get("entry_price"),
                "stop_loss": r.get("trade_plan", {}).get("stop_loss"),
                "target_1": r.get("trade_plan", {}).get("target_1"),
                "outcome": r.get("outcome", {}).get("status"),
                "result_pct": r.get("outcome", {}).get("result_pct"),
                "recorded": r.get("recorded_trade") is not None,
            }
            for r in sorted(traded, key=lambda x: (x["date"], x["symbol"]))
        ],
    }


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    report = build_report(days=days)
    out = sys.argv[2] if len(sys.argv) > 2 else "orb_batch_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    s = report["summary"]
    print(json.dumps({"summary": s, "by_day": report["by_day"], "output": out}, indent=2))
