import os
import sqlite3
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


def _column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def migrate_db() -> None:
    """Apply lightweight SQLite migrations for existing installs."""
    if not _db_path.exists():
        return

    conn = sqlite3.connect(_db_path)
    cur = conn.cursor()

    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='wishlist'")
        if not cur.fetchone():
            return

        if not _column_exists(cur, "wishlist", "market"):
            cur.execute("ALTER TABLE wishlist ADD COLUMN market TEXT NOT NULL DEFAULT 'US'")
            cur.execute(
                "UPDATE wishlist SET market = 'IN' "
                "WHERE UPPER(symbol) LIKE '%.NS' OR UPPER(symbol) LIKE '%.BO'"
            )

        if not _column_exists(cur, "signal_history", "market"):
            cur.execute("ALTER TABLE signal_history ADD COLUMN market TEXT NOT NULL DEFAULT 'US'")
            cur.execute(
                "UPDATE signal_history SET market = 'IN' "
                "WHERE UPPER(symbol) LIKE '%.NS' OR UPPER(symbol) LIKE '%.BO'"
            )

        if not _column_exists(cur, "signal_history", "target_hit_at"):
            cur.execute("ALTER TABLE signal_history ADD COLUMN target_hit_at TEXT")

        if not _column_exists(cur, "signal_history", "days_to_target"):
            cur.execute("ALTER TABLE signal_history ADD COLUMN days_to_target INTEGER")

        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_wishlist_symbol_market "
            "ON wishlist (symbol, market)"
        )

        conn.commit()
    finally:
        conn.close()


def init_db():
    from app.models import SignalHistory, WishlistItem  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_db()
