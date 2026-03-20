"""
core/security.py
----------------
Password hashing (bcrypt) and JWT token creation / verification.
All crypto lives here; nothing else imports jose or passlib directly.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# bcrypt is intentionally slow — ideal for password hashing
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return a bcrypt-hashed string suitable for DB storage."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison — safe against timing attacks."""
    return _pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    """
    Internal factory.  Adds 'exp' claim and signs with the secret key.
    We always use UTC-aware datetimes to avoid subtle DST bugs.
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str | int, extra: dict | None = None) -> str:
    """
    Short-lived token (default 30 min).
    'sub' claim stores the user's ID as a string (JWT spec recommends strings).
    """
    data: dict[str, Any] = {"sub": str(subject), "type": "access"}
    if extra:
        data.update(extra)
    delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(data, delta)


def create_refresh_token(subject: str | int) -> str:
    """
    Long-lived token (default 7 days).
    Refresh tokens carry minimal claims — they are only used to obtain new
    access tokens, never to authorise resource access directly.
    """
    data: dict[str, Any] = {"sub": str(subject), "type": "refresh"}
    delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(data, delta)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT.  Raises JWTError on any failure (expired,
    tampered, wrong algo).  Callers should catch JWTError.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
