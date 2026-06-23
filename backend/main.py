import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_data_dir, get_db_path, init_db
from app.routes import history, stocks, wishlist
from app.services.monitor import scan_wishlist

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCAN_INTERVAL_MINUTES = 5
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_dir = get_data_dir()
    db_path = get_db_path()
    init_db()
    logger.info("Data directory: %s", data_dir)
    logger.info("Database file: %s", db_path)
    scheduler.add_job(scan_wishlist, "interval", minutes=SCAN_INTERVAL_MINUTES, id="wishlist_scan")
    scheduler.start()
    logger.info("Market monitor started — scanning every %d minutes", SCAN_INTERVAL_MINUTES)
    scan_wishlist()
    yield
    scheduler.shutdown()


app = FastAPI(title="Market Monitor", version="1.0.0", lifespan=lifespan)

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


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "data_dir": str(get_data_dir()),
        "database": str(get_db_path()),
    }
