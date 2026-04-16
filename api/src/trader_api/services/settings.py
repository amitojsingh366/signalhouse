"""Runtime settings stored in the database."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.models import AppSetting

HYBRID_TAKE_PROFIT_KEY = "risk.hybrid_take_profit_enabled"


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _serialize_bool(value: bool) -> str:
    return "true" if value else "false"


def _default_hybrid_enabled(config: dict[str, Any]) -> bool:
    risk_cfg = config.get("risk", {})
    return bool(risk_cfg.get("hybrid_take_profit_enabled", False))


async def get_hybrid_take_profit_enabled(
    db: AsyncSession, config: dict[str, Any]
) -> bool:
    """Return persisted hybrid take-profit toggle, or config default."""
    default = _default_hybrid_enabled(config)
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == HYBRID_TAKE_PROFIT_KEY)
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        return default
    return _parse_bool(setting.value, default=default)


async def set_hybrid_take_profit_enabled(
    db: AsyncSession, config: dict[str, Any], enabled: bool
) -> bool:
    """Persist hybrid toggle and apply it to the in-memory config."""
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == HYBRID_TAKE_PROFIT_KEY)
    )
    setting = result.scalar_one_or_none()
    serialized = _serialize_bool(enabled)

    if setting is None:
        db.add(AppSetting(key=HYBRID_TAKE_PROFIT_KEY, value=serialized))
    else:
        setting.value = serialized

    await db.commit()
    config.setdefault("risk", {})["hybrid_take_profit_enabled"] = enabled
    return enabled


async def load_runtime_settings(db: AsyncSession, config: dict[str, Any]) -> None:
    """Load persisted runtime settings into the active in-memory config."""
    enabled = await get_hybrid_take_profit_enabled(db, config)
    config.setdefault("risk", {})["hybrid_take_profit_enabled"] = enabled
