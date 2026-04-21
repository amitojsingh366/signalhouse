"""Shared datetime parsing helpers used across strategy/risk services."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def parse_entry_datetime(raw: Any) -> datetime | None:
    """Parse an entry datetime from DB/API payloads.

    Accepts already-constructed datetime objects and ISO8601 strings.
    Supports trailing `Z` UTC suffix.
    """
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str) or not raw:
        return None
    candidate = raw.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None

