"""Runtime settings loader — applies persisted overrides to the in-memory config."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.services.editable_settings import load_all_overrides


async def load_runtime_settings(db: AsyncSession, config: dict[str, Any]) -> None:
    """Load persisted overrides from `app_settings` into the live config."""
    await load_all_overrides(db, config)
