import logging
from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import SessionLocal, get_data_dir, get_db_path, init_db
from app.routes import history, holdings, intraday, stocks, wishlist
from app.services.history import purge_old_history
from app.services.intraday_monitor import scan_intraday_watchlist
from app.services.monitor import scan_holdings, scan_wishlist
from app.version import __version__

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCAN_INTERVAL_MINUTES = 5
INTRADAY_SCAN_MINUTES = 2
PURGE_INTERVAL_HOURS = 24
scheduler = BackgroundScheduler()


def _run_scheduled_scan() -> None:
    try:
        scan_wishlist()
        scan_holdings()
    except Exception as e:
        logger.warning("Scheduled scan failed: %s", e)


def _run_intraday_scan() -> None:
    try:
        scan_intraday_watchlist()
    except Exception as e:
        logger.warning("Intraday scan failed: %s", e)


def _run_history_purge() -> None:
    db = SessionLocal()
    try:
        n = purge_old_history(db)
        if n:
            logger.info("Retention purge removed %d closed trade(s)", n)
    except Exception as e:
        logger.warning("History retention purge failed: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_dir = get_data_dir()
    db_path = get_db_path()
    init_db()
    logger.info("Data directory: %s", data_dir)
    logger.info("Database file: %s", db_path)
    scheduler.add_job(
        _run_scheduled_scan,
        "interval",
        minutes=SCAN_INTERVAL_MINUTES,
        id="market_scan",
        next_run_time=datetime.utcnow(),
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_intraday_scan,
        "interval",
        minutes=INTRADAY_SCAN_MINUTES,
        id="intraday_scan",
        next_run_time=datetime.utcnow(),
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_history_purge,
        "interval",
        hours=PURGE_INTERVAL_HOURS,
        id="history_purge",
        next_run_time=datetime.utcnow(),
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Market monitor started — scanning every %d minutes", SCAN_INTERVAL_MINUTES)
    yield
    scheduler.shutdown()


app = FastAPI(title="Market Monitor", version=__version__, lifespan=lifespan)


class NoCacheApiMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(NoCacheApiMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wishlist.router)
app.include_router(stocks.router)
app.include_router(history.router)
app.include_router(holdings.router)
app.include_router(intraday.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": __version__,
        "data_dir": str(get_data_dir()),
        "database": str(get_db_path()),
    }
