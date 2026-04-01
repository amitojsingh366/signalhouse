"""Notification endpoints — device registration, preferences, history."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.models import DeviceRegistration, NotificationLog
from trader_api.schemas import (
    DeviceRegisterIn,
    NotificationLogOut,
    NotificationPrefsIn,
    NotificationPrefsOut,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"], dependencies=[Depends(require_auth)])


@router.post("/register")
async def register_device(
    data: DeviceRegisterIn, db: AsyncSession = Depends(get_db)
):
    """Register or update a device token for push notifications."""
    result = await db.execute(
        select(DeviceRegistration).where(
            DeviceRegistration.device_token == data.device_token
        )
    )
    device = result.scalar_one_or_none()

    if device:
        device.platform = data.platform
        if data.push_token is not None:
            device.push_token = data.push_token
    else:
        device = DeviceRegistration(
            device_token=data.device_token,
            push_token=data.push_token,
            platform=data.platform,
        )
        db.add(device)

    await db.commit()
    return {"status": "registered", "device_token": data.device_token}


@router.get("/preferences", response_model=NotificationPrefsOut)
async def get_preferences(
    device_token: str, db: AsyncSession = Depends(get_db)
):
    """Get notification preferences for a device."""
    result = await db.execute(
        select(DeviceRegistration).where(
            DeviceRegistration.device_token == device_token
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not registered")
    return device


@router.put("/preferences", response_model=NotificationPrefsOut)
async def update_preferences(
    device_token: str,
    data: NotificationPrefsIn,
    db: AsyncSession = Depends(get_db),
):
    """Toggle notification preferences (enabled, daily disable)."""
    result = await db.execute(
        select(DeviceRegistration).where(
            DeviceRegistration.device_token == device_token
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not registered")

    if data.enabled is not None:
        device.enabled = data.enabled
    if data.daily_disabled is not None:
        if data.daily_disabled:
            device.daily_disabled_date = datetime.now(timezone.utc).strftime(
                "%Y-%m-%d"
            )
        else:
            device.daily_disabled_date = None

    await db.commit()
    await db.refresh(device)
    return device


@router.get("/history", response_model=list[NotificationLogOut])
async def get_history(
    device_token: str, limit: int = 20, db: AsyncSession = Depends(get_db)
):
    """Get recent notification history for a device."""
    result = await db.execute(
        select(NotificationLog)
        .where(NotificationLog.device_token == device_token)
        .order_by(NotificationLog.sent_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/acknowledge/{notification_id}")
async def acknowledge_notification(
    notification_id: int, db: AsyncSession = Depends(get_db)
):
    """Mark a notification as acknowledged (user answered the call)."""
    log = await db.get(NotificationLog, notification_id)
    if not log:
        raise HTTPException(status_code=404, detail="Notification not found")

    log.acknowledged = True
    await db.commit()
    return {"status": "acknowledged", "id": notification_id}
