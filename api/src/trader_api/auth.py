"""Authentication middleware — passkey-based, token-gated API access."""

from __future__ import annotations

import os
import time

import jwt
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.database import get_db
from trader_api.models import WebAuthnCredential

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 30 * 24 * 3600  # 30 days

# Cache: (has_credential, timestamp)
_credential_cache: tuple[bool, float] = (False, 0.0)
_CACHE_TTL = 60.0  # seconds


def invalidate_credential_cache() -> None:
    """Call after registering a new credential."""
    global _credential_cache
    _credential_cache = (False, 0.0)


async def has_any_credential(db: AsyncSession) -> bool:
    """Check if any passkey is registered. Cached for 60s."""
    global _credential_cache
    cached, ts = _credential_cache
    if time.time() - ts < _CACHE_TTL:
        return cached

    result = await db.execute(select(WebAuthnCredential.id).limit(1))
    exists = result.scalar_one_or_none() is not None
    _credential_cache = (exists, time.time())
    return exists


def issue_token() -> str:
    """Issue a JWT for the single owner."""
    now = int(time.time())
    payload = {"sub": "owner", "iat": now, "exp": now + JWT_EXPIRY_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify and decode a JWT. Raises on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


async def require_auth(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """If any passkey is registered, require a valid Bearer token. Otherwise skip."""
    if not await has_any_credential(db):
        return  # No passkey registered — open access

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization.removeprefix("Bearer ")
    try:
        verify_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
