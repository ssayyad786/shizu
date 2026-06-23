import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Persistent data location on server installs (set in /etc/market-monitor/config).
# Default for local dev: ./market.db in the backend folder.
DEFAULT_DATA_DIR = "/var/lib/market-monitor"


def get_data_dir() -> Path:
    return Path(os.environ.get("MARKET_DATA_DIR", ".")).resolve()


def get_db_path() -> Path:
    return get_data_dir() / "market.db"


_data_dir = get_data_dir()
_data_dir.mkdir(parents=True, exist_ok=True)
(_data_dir / "backups").mkdir(parents=True, exist_ok=True)
_db_path = get_db_path()

DATABASE_URL = f"sqlite:///{_db_path.as_posix()}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import SignalHistory, WishlistItem  # noqa: F401

    Base.metadata.create_all(bind=engine)
