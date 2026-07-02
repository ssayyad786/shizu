#!/usr/bin/env python3
"""Reset a holdings profile password — run on the server only (not exposed via API)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root: python scripts/reset_holding_password.py user newpass
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.database import SessionLocal, init_db  # noqa: E402
from app.services.holding_auth import reset_profile_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset password for a holdings profile (server admin CLI only)."
    )
    parser.add_argument("username", help="Holdings profile username")
    parser.add_argument("new_password", help="New password (min 8 characters)")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        reset_profile_password(db, args.username, args.new_password)
        print(f"Password reset for holdings profile '{args.username}'.")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
