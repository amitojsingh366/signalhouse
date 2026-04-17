"""Runtime settings API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import get_config
from trader_api.schemas import ProfitTakingSettingsIn, ProfitTakingSettingsOut
from trader_api.services.strategy import Strategy
from trader_api.services.settings import (
    get_hybrid_take_profit_enabled,
    get_oversold_fastlane_enabled,
    set_hybrid_take_profit_enabled,
    set_oversold_fastlane_enabled,
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
    oversold_enabled = await get_oversold_fastlane_enabled(db, config)
    return ProfitTakingSettingsOut(
        hybrid_take_profit_enabled=enabled,
        hybrid_take_profit_min_buy_strength=_hybrid_min_buy_strength(config),
        oversold_fastlane_enabled=oversold_enabled,
    )


@router.put("/profit-taking", response_model=ProfitTakingSettingsOut)
async def update_profit_taking_settings(
    body: ProfitTakingSettingsIn,
    db: AsyncSession = Depends(get_db),
):
    config = get_config()
    if (
        body.hybrid_take_profit_enabled is None
        and body.oversold_fastlane_enabled is None
    ):
        raise HTTPException(status_code=400, detail="No settings provided")

    enabled = await get_hybrid_take_profit_enabled(db, config)
    if body.hybrid_take_profit_enabled is not None:
        enabled = await set_hybrid_take_profit_enabled(
            db,
            config,
            body.hybrid_take_profit_enabled,
        )

    oversold_enabled = await get_oversold_fastlane_enabled(db, config)
    if body.oversold_fastlane_enabled is not None:
        oversold_enabled = await set_oversold_fastlane_enabled(
            db,
            config,
            body.oversold_fastlane_enabled,
        )

    # Settings toggles change recommendation behavior; clear shared strategy cache
    # so next signal/action fetch recomputes with updated strategy switches.
    Strategy.invalidate_recommendations_cache()

    return ProfitTakingSettingsOut(
        hybrid_take_profit_enabled=enabled,
        hybrid_take_profit_min_buy_strength=_hybrid_min_buy_strength(config),
        oversold_fastlane_enabled=oversold_enabled,
    )
