"""Runtime settings API — generic editable config via registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import get_config
from trader_api.schemas import (
    SettingGroup,
    SettingItem,
    SettingsConfigOut,
    SettingsUpdateIn,
)
from trader_api.services.editable_settings import (
    GROUPS,
    REGISTRY,
    REGISTRY_BY_KEY,
    get_setting_value,
    set_setting_value,
)
from trader_api.services.strategy import Strategy

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_auth)],
)


def _serialize_config(config: dict) -> SettingsConfigOut:
    items_by_group: dict[str, list[SettingItem]] = {g["id"]: [] for g in GROUPS}
    for setting in REGISTRY:
        items_by_group.setdefault(setting.group, []).append(
            SettingItem(
                key=setting.key,
                type=setting.type,
                group=setting.group,
                label=setting.label,
                description=setting.description,
                value=get_setting_value(config, setting),
                min=setting.min,
                max=setting.max,
                step=setting.step,
            )
        )
    groups = [
        SettingGroup(id=g["id"], label=g["label"], items=items_by_group.get(g["id"], []))
        for g in GROUPS
    ]
    return SettingsConfigOut(groups=groups)


@router.get("/config", response_model=SettingsConfigOut)
async def get_settings_config():
    return _serialize_config(get_config())


@router.put("/config", response_model=SettingsConfigOut)
async def update_settings_config(
    body: SettingsUpdateIn,
    db: AsyncSession = Depends(get_db),
):
    if not body.updates:
        raise HTTPException(status_code=400, detail="No settings provided")

    config = get_config()
    unknown = [k for k in body.updates if k not in REGISTRY_BY_KEY]
    if unknown:
        raise HTTPException(
            status_code=400, detail=f"Unknown setting keys: {', '.join(unknown)}"
        )

    try:
        for key, value in body.updates.items():
            await set_setting_value(db, config, REGISTRY_BY_KEY[key], value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    Strategy.invalidate_recommendations_cache()
    return _serialize_config(config)
