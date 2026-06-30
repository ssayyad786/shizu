"""Build ML train/test datasets from intraday trade history."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import IntradaySignalHistory
from app.services.intraday_report import _trade_row
from app.services.intraday_signals import INTRADAY_MIN_CONFIDENCE, INTRADAY_MIN_SCORE, WEIGHTS
from app.version import __version__

FACTOR_COLUMNS = [
    "factor_structure",
    "factor_vwap",
    "factor_rvol",
    "factor_ema",
    "factor_open_gap",
    "factor_atr",
    "factor_rsi",
    "factor_candle",
    "factor_macd",
    "factor_daily_trend",
]

FACTOR_NAME_MAP = {
    "Market structure": "factor_structure",
    "VWAP": "factor_vwap",
    "Relative volume (RVOL)": "factor_rvol",
    "EMA alignment (9/20/50)": "factor_ema",
    "Opening range & gap": "factor_open_gap",
    "ATR volatility": "factor_atr",
    "RSI exhaustion / divergence": "factor_rsi",
    "Candlestick pattern": "factor_candle",
    "MACD confirmation": "factor_macd",
    "Daily trend (context)": "factor_daily_trend",
}

FEATURE_COLUMNS = [
    "id",
    "symbol",
    "trade_date",
    "created_at",
    "direction",
    "direction_long",
    "score",
    "confidence",
    "entry_price",
    "stop_pct",
    "target_1_pct",
    "target_2_pct",
    "risk_reward",
    "hold_minutes",
    "mfe_pct",
    "mae_pct",
    *FACTOR_COLUMNS,
]

LABEL_COLUMNS = ["label_win", "label_result_pct", "status"]


def _parse_date_param(value: str) -> datetime:
    if "T" in value:
        return datetime.fromisoformat(value.replace("Z", ""))
    return datetime.strptime(value, "%Y-%m-%d")


def _day_start(d: datetime) -> datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def list_trade_dates(db: Session) -> list[dict]:
    rows = (
        db.query(IntradaySignalHistory.trade_date)
        .distinct()
        .order_by(IntradaySignalHistory.trade_date.desc())
        .all()
    )
    out = []
    for (trade_date,) in rows:
        day = _day_start(trade_date)
        count = (
            db.query(IntradaySignalHistory)
            .filter(
                IntradaySignalHistory.trade_date >= day,
                IntradaySignalHistory.trade_date < day + timedelta(days=1),
            )
            .count()
        )
        closed = (
            db.query(IntradaySignalHistory)
            .filter(
                IntradaySignalHistory.trade_date >= day,
                IntradaySignalHistory.trade_date < day + timedelta(days=1),
                IntradaySignalHistory.status != "open",
            )
            .count()
        )
        out.append({
            "date": day.strftime("%Y-%m-%d"),
            "trades": count,
            "closed": closed,
        })
    return out


def _filter_rows(
    rows: list[IntradaySignalHistory],
    from_date: str | None,
    to_date: str | None,
) -> list[IntradaySignalHistory]:
    if from_date:
        start = _day_start(_parse_date_param(from_date))
        rows = [r for r in rows if _day_start(r.trade_date) >= start]
    if to_date:
        end = _day_start(_parse_date_param(to_date)) + timedelta(days=1)
        rows = [r for r in rows if _day_start(r.trade_date) < end]
    return rows


def _bias_to_score(bias: str) -> int:
    if bias == "BULLISH":
        return 1
    if bias == "BEARISH":
        return -1
    return 0


def _ml_row(trade: dict, split: str | None = None) -> dict:
    row: dict = {col: None for col in FEATURE_COLUMNS + LABEL_COLUMNS}
    row["id"] = trade.get("id")
    row["symbol"] = trade.get("symbol")
    row["trade_date"] = trade.get("trade_date")
    row["created_at"] = trade.get("created_at")
    row["direction"] = trade.get("direction")
    row["direction_long"] = 1 if trade.get("direction") == "LONG" else 0
    row["score"] = trade.get("score")
    row["confidence"] = trade.get("confidence")
    row["entry_price"] = trade.get("entry_price")
    row["stop_pct"] = trade.get("stop_pct")
    row["target_1_pct"] = trade.get("target_1_pct")
    row["target_2_pct"] = trade.get("target_2_pct")
    row["risk_reward"] = trade.get("risk_reward")
    row["hold_minutes"] = trade.get("hold_minutes")
    row["mfe_pct"] = trade.get("mfe_pct")
    row["mae_pct"] = trade.get("mae_pct")

    for col in FACTOR_COLUMNS:
        row[col] = 0

    for reason in trade.get("trade_reasons") or []:
        col = FACTOR_NAME_MAP.get(reason.get("factor", ""))
        if col:
            row[col] = _bias_to_score(reason.get("bias", "NEUTRAL"))

    status = trade.get("status", "open")
    row["status"] = status
    row["label_win"] = 1 if trade.get("success") else 0 if status != "open" else None
    row["label_result_pct"] = trade.get("result_pct")
    if split:
        row["split"] = split
    return row


def _split_train_test(
    closed_rows: list[IntradaySignalHistory],
    train_ratio: float,
) -> tuple[list[IntradaySignalHistory], list[IntradaySignalHistory]]:
    ordered = sorted(closed_rows, key=lambda r: r.created_at)
    if len(ordered) < 2:
        return ordered, []
    n_train = max(1, int(len(ordered) * train_ratio))
    if n_train >= len(ordered):
        n_train = len(ordered) - 1
    return ordered[:n_train], ordered[n_train:]


def _win_rate(rows: list[dict]) -> float | None:
    labeled = [r for r in rows if r.get("label_win") is not None]
    if not labeled:
        return None
    wins = sum(1 for r in labeled if r["label_win"] == 1)
    return round(wins / len(labeled) * 100, 1)


def build_intraday_dataset(
    db: Session,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    train_ratio: float = 0.8,
    include_split: bool = True,
) -> dict:
    all_rows = (
        db.query(IntradaySignalHistory)
        .order_by(IntradaySignalHistory.created_at.asc())
        .all()
    )
    filtered = _filter_rows(all_rows, from_date, to_date)
    trades = [_trade_row(r) for r in filtered]
    open_trades = [t for t in trades if t["status"] == "open"]
    closed_records = [r for r in filtered if r.status != "open"]

    train_records: list[IntradaySignalHistory] = []
    test_records: list[IntradaySignalHistory] = []
    if include_split:
        train_records, test_records = _split_train_test(closed_records, train_ratio)
    else:
        train_records = closed_records

    train_trade_map = {t["id"]: t for t in trades}
    train_rows = [_ml_row(train_trade_map[r.id], "train") for r in train_records]
    test_rows = [_ml_row(train_trade_map[r.id], "test") for r in test_records]
    open_rows = [_ml_row(t) for t in open_trades]

    return {
        "dataset_type": "shizu_intraday_train_test",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_version": __version__,
        "date_range": {
            "from": from_date,
            "to": to_date,
            "trades_in_range": len(trades),
        },
        "model": {
            "min_confidence": INTRADAY_MIN_CONFIDENCE,
            "min_score": INTRADAY_MIN_SCORE,
            "factor_weights": WEIGHTS,
        },
        "split": {
            "enabled": include_split,
            "method": "chronological",
            "train_ratio": train_ratio,
            "train_size": len(train_rows),
            "test_size": len(test_rows),
            "train_win_rate": _win_rate(train_rows),
            "test_win_rate": _win_rate(test_rows),
        },
        "feature_columns": FEATURE_COLUMNS,
        "label_columns": LABEL_COLUMNS,
        "factor_encoding": {
            "factor_columns": FACTOR_COLUMNS,
            "values": {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1},
        },
        "usage_notes": [
            "Use feature_columns as X and label_win (binary) or label_result_pct (regression) as y.",
            "Train on split=train rows; evaluate on split=test rows without peeking.",
            "Factor columns are -1/0/1 bearish/neutral/bullish at signal time.",
            "Open trades are included separately — no outcome label yet.",
        ],
        "train": train_rows,
        "test": test_rows,
        "open": open_rows,
        "all_closed": [_ml_row(t) for t in trades if t["status"] != "open"],
    }


def dataset_to_csv(dataset: dict) -> str:
    buf = io.StringIO()
    columns = FEATURE_COLUMNS + LABEL_COLUMNS + ["split"]
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()

    for section, default_split in (("train", "train"), ("test", "test"), ("open", "")):
        for row in dataset.get(section, []):
            out = dict(row)
            if not out.get("split") and default_split:
                out["split"] = default_split
            writer.writerow(out)

    return buf.getvalue()


def dataset_filename(fmt: str, from_date: str | None, to_date: str | None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = "csv" if fmt == "csv" else "json"
    if from_date and to_date and from_date != to_date:
        range_part = f"{from_date}_to_{to_date}"
    elif from_date or to_date:
        range_part = from_date or to_date or "all"
    else:
        range_part = "all"
    return f"shizu_intraday_dataset_{range_part}_{stamp}.{ext}"
