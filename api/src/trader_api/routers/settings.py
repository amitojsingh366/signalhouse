"""Runtime settings API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import get_config
from trader_api.schemas import ProfitTakingSettingsIn, ProfitTakingSettingsOut
from trader_api.services.settings import (
    get_hybrid_take_profit_enabled,
    set_hybrid_take_profit_enabled,
)

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_auth)],
)


def _hybrid_min_buy_strength(config: dict) -> float:
    raw = config.get("risk", {}).get("hybrid_take_profit_min_buy_strength", 0.5)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.5


@router.get("/profit-taking", response_model=ProfitTakingSettingsOut)
async def get_profit_taking_settings(db: AsyncSession = Depends(get_db)):
    config = get_config()
    enabled = await get_hybrid_take_profit_enabled(db, config)
    return ProfitTakingSettingsOut(
        hybrid_take_profit_enabled=enabled,
        hybrid_take_profit_min_buy_strength=_hybrid_min_buy_strength(config),
    )


@router.put("/profit-taking", response_model=ProfitTakingSettingsOut)
async def update_profit_taking_settings(
    body: ProfitTakingSettingsIn,
    db: AsyncSession = Depends(get_db),
):
    config = get_config()
    enabled = await set_hybrid_take_profit_enabled(
        db,
        config,
        body.hybrid_take_profit_enabled,
    )
    return ProfitTakingSettingsOut(
        hybrid_take_profit_enabled=enabled,
        hybrid_take_profit_min_buy_strength=_hybrid_min_buy_strength(config),
    )
