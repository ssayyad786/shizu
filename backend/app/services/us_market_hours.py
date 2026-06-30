"""US equity regular session hours (NYSE/NASDAQ, Eastern Time)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

US_EASTERN = ZoneInfo("America/New_York")
SESSION_OPEN = time(9, 30)
SESSION_CLOSE = time(16, 0)

# NYSE full-day closures (extend annually).
NYSE_HOLIDAYS: frozenset[date] = frozenset({
    date(2025, 1, 1),
    date(2025, 1, 20),
    date(2025, 2, 17),
    date(2025, 4, 18),
    date(2025, 5, 26),
    date(2025, 6, 19),
    date(2025, 7, 4),
    date(2025, 9, 1),
    date(2025, 11, 27),
    date(2025, 12, 25),
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
})


def is_us_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in NYSE_HOLIDAYS


def _session_bounds_for_day(d: date) -> tuple[datetime, datetime]:
    open_dt = datetime.combine(d, SESSION_OPEN, tzinfo=US_EASTERN)
    close_dt = datetime.combine(d, SESSION_CLOSE, tzinfo=US_EASTERN)
    return open_dt, close_dt


def _next_trading_day(start: date) -> date:
    d = start
    for _ in range(14):
        if is_us_trading_day(d):
            return d
        d += timedelta(days=1)
    return start


def _next_session_open(after: datetime) -> datetime:
    d = after.date()
    if is_us_trading_day(d):
        open_dt, _ = _session_bounds_for_day(d)
        if after < open_dt:
            return open_dt
    d = _next_trading_day(d + timedelta(days=1))
    return _session_bounds_for_day(d)[0]


def get_us_market_status(now: datetime | None = None) -> dict:
    now = now or datetime.now(US_EASTERN)
    if now.tzinfo is None:
        now = now.replace(tzinfo=US_EASTERN)
    else:
        now = now.astimezone(US_EASTERN)

    today = now.date()
    is_open = False
    seconds_to_close: int | None = None
    seconds_to_open: int | None = None
    session_open_at: datetime | None = None
    session_close_at: datetime | None = None
    next_session_open_at: datetime | None = None
    status_label = "closed"
    message = ""

    if is_us_trading_day(today):
        session_open_at, session_close_at = _session_bounds_for_day(today)
        if session_open_at <= now < session_close_at:
            is_open = True
            status_label = "open"
            seconds_to_close = int((session_close_at - now).total_seconds())
            message = "US market is open — intraday scans active."
        elif now < session_open_at:
            status_label = "pre_open"
            seconds_to_open = int((session_open_at - now).total_seconds())
            next_session_open_at = session_open_at
            message = "US market opens at 9:30 AM ET — intraday scans start then."
        else:
            status_label = "after_close"
            nxt = _next_session_open(now)
            seconds_to_open = int((nxt - now).total_seconds())
            next_session_open_at = nxt
            message = "US market closed for today — intraday scans resume at next open."
    else:
        if today.weekday() >= 5:
            status_label = "weekend"
            message = "Weekend — US market closed. Intraday scans resume Monday."
        else:
            status_label = "holiday"
            message = "NYSE holiday — US market closed."
        nxt = _next_session_open(now)
        seconds_to_open = int((nxt - now).total_seconds())
        next_session_open_at = nxt

    return {
        "is_open": is_open,
        "timezone": "America/New_York",
        "open_time": SESSION_OPEN.strftime("%H:%M"),
        "close_time": SESSION_CLOSE.strftime("%H:%M"),
        "session_open_at": session_open_at.isoformat() if session_open_at else None,
        "session_close_at": session_close_at.isoformat() if session_close_at else None,
        "next_session_open_at": next_session_open_at.isoformat() if next_session_open_at else None,
        "seconds_to_close": seconds_to_close,
        "seconds_to_open": seconds_to_open,
        "status_label": status_label,
        "message": message,
    }


def market_status_to_dict() -> dict:
    return get_us_market_status()
