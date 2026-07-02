"""Per-user holdings profiles — password auth and JWT sessions."""

from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_data_dir, get_db
from app.models import HoldingProfile

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
MIN_PASSWORD_LEN = 8
TOKEN_TTL_DAYS = 30
_bearer = HTTPBearer(auto_error=False)


def _jwt_secret() -> str:
    env = os.environ.get("HOLDINGS_JWT_SECRET", "").strip()
    if env:
        return env
    secret_path = get_data_dir() / ".holdings_jwt_secret"
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()
    generated = secrets.token_urlsafe(48)
    secret_path.write_text(generated, encoding="utf-8")
    try:
        os.chmod(secret_path, 0o600)
    except OSError:
        pass
    return generated


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def validate_username(username: str) -> str:
    username = username.strip()
    if not USERNAME_RE.match(username):
        raise ValueError("Username must be 3–32 characters: letters, numbers, underscore only")
    return username


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LEN} characters")


def create_access_token(profile: HoldingProfile) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=TOKEN_TTL_DAYS)
    payload = {
        "sub": profile.id,
        "usr": profile.username,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "typ": "holdings",
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm="HS256")
    return token if isinstance(token, str) else token.decode("utf-8")


def _profile_id_from_token(payload: dict) -> int | None:
    raw = payload.get("sub")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(401, "Invalid or expired session — please sign in again") from e
    if payload.get("typ") != "holdings":
        raise HTTPException(401, "Invalid session token")
    return payload


def get_current_holding_profile(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> HoldingProfile:
    if credentials is None or not credentials.credentials:
        raise HTTPException(401, "Sign in to access your holdings")
    payload = decode_access_token(credentials.credentials)
    profile_id = _profile_id_from_token(payload)
    if profile_id is None:
        raise HTTPException(401, "Invalid session")
    profile = db.query(HoldingProfile).filter(HoldingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(401, "Profile not found — please sign in again")
    return profile


def reset_profile_password(db: Session, username: str, new_password: str) -> HoldingProfile:
    username = validate_username(username)
    validate_password(new_password)
    profile = db.query(HoldingProfile).filter(HoldingProfile.username == username).first()
    if not profile:
        raise ValueError(f"No holdings profile named '{username}'")
    profile.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(profile)
    return profile
