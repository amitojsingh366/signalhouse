"""Notification endpoints — device registration, preferences, history."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.models import DeviceRegistration
from trader_api.schemas import (
    DeviceRegisterIn,
    NotificationLogOut,
    NotificationPrefsIn,
    NotificationPrefsOut,
)

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_auth)],
)


async def _notification_log_columns(db: AsyncSession) -> set[str]:
    result = await db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'notification_log'
            """
        )
    )
    return {str(row[0]) for row in result}


@router.post("/register")
async def register_device(
    data: DeviceRegisterIn, db: AsyncSession = Depends(get_db)
):
    """Register or update a device token for push notifications."""
    try:
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
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Notification device schema unavailable; run latest API migrations",
        ) from exc


@router.get("/preferences", response_model=NotificationPrefsOut)
async def get_preferences(
    device_token: str, db: AsyncSession = Depends(get_db)
):
    """Get notification preferences for a device."""
    try:
        result = await db.execute(
            select(DeviceRegistration).where(
                DeviceRegistration.device_token == device_token
            )
        )
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(status_code=404, detail="Device not registered")
        return device
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Notification device schema unavailable; run latest API migrations",
        ) from exc


@router.put("/preferences", response_model=NotificationPrefsOut)
async def update_preferences(
    device_token: str,
    data: NotificationPrefsIn,
    db: AsyncSession = Depends(get_db),
):
    """Toggle notification preferences (enabled + per-channel daily mute)."""
    try:
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

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        mute_preferences_updated = False

        # Legacy combined mute toggle: keep backward compatibility by applying to both channels.
        if data.daily_disabled is not None:
            mute_preferences_updated = True
            if data.daily_disabled:
                device.daily_disabled_date = today
                device.daily_disabled_notifications_date = today
                device.daily_disabled_calls_date = today
            else:
                device.daily_disabled_date = None
                device.daily_disabled_notifications_date = None
                device.daily_disabled_calls_date = None

        # Channel-specific mutes: override legacy value when explicitly provided.
        if data.daily_disabled_notifications is not None:
            mute_preferences_updated = True
            if data.daily_disabled_notifications:
                device.daily_disabled_notifications_date = today
            else:
                device.daily_disabled_notifications_date = None

        if data.daily_disabled_calls is not None:
            mute_preferences_updated = True
            if data.daily_disabled_calls:
                device.daily_disabled_calls_date = today
            else:
                device.daily_disabled_calls_date = None

        # Keep legacy response field tied to alert-notification mute for old clients.
        # Avoid touching legacy state on unrelated updates (e.g. enabled only).
        if mute_preferences_updated:
            device.daily_disabled_date = device.daily_disabled_notifications_date

        await db.commit()
        await db.refresh(device)
        return device
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Notification preferences unavailable; run latest API migrations",
        ) from exc


@router.get("/history", response_model=list[NotificationLogOut])
async def get_history(
    device_token: str, limit: int = 20, db: AsyncSession = Depends(get_db)
):
    """Get recent notification history for a device."""
    columns = await _notification_log_columns(db)
    if not columns or "device_token" not in columns:
        return []

    safe_limit = max(1, min(limit, 200))
    select_parts = [
        "id" if "id" in columns else "0::INTEGER AS id",
        (
            "notification_type"
            if "notification_type" in columns
            else "'signal'::VARCHAR AS notification_type"
        ),
        "symbol" if "symbol" in columns else "''::VARCHAR AS symbol",
        "signal" if "signal" in columns else "''::VARCHAR AS signal",
        (
            "strength"
            if "strength" in columns
            else "0.0::DOUBLE PRECISION AS strength"
        ),
        "caller_name" if "caller_name" in columns else "''::VARCHAR AS caller_name",
        "sent_at" if "sent_at" in columns else "NOW() AS sent_at",
        "COALESCE(delivered, FALSE) AS delivered"
        if "delivered" in columns
        else "FALSE AS delivered",
        "COALESCE(acknowledged, FALSE) AS acknowledged"
        if "acknowledged" in columns
        else "FALSE AS acknowledged",
    ]
    order_by = "sent_at DESC" if "sent_at" in columns else "id DESC"
    result = await db.execute(
        text(
            f"""
            SELECT {", ".join(select_parts)}
            FROM notification_log
            WHERE device_token = :device_token
            ORDER BY {order_by}
            LIMIT :limit
            """
        ),
        {"device_token": device_token, "limit": safe_limit},
    )
    rows = result.mappings().all()
    return [
        NotificationLogOut(
            id=int(row["id"]),
            notification_type=str(row["notification_type"]),
            symbol=str(row["symbol"]),
            signal=str(row["signal"]),
            strength=float(row["strength"]),
            caller_name=str(row["caller_name"]),
            sent_at=row["sent_at"],
            delivered=bool(row["delivered"]),
            acknowledged=bool(row["acknowledged"]),
        )
        for row in rows
    ]


@router.post("/acknowledge/{notification_id}")
async def acknowledge_notification(
    notification_id: int, db: AsyncSession = Depends(get_db)
):
    """Mark a notification as acknowledged (user answered the call)."""
    columns = await _notification_log_columns(db)
    if not columns or "id" not in columns:
        raise HTTPException(status_code=404, detail="Notification log unavailable")
    if "acknowledged" not in columns:
        return {"status": "acknowledge_unavailable", "id": notification_id}

    result = await db.execute(
        text(
            """
            UPDATE notification_log
            SET acknowledged = TRUE
            WHERE id = :notification_id
            """
        ),
        {"notification_id": notification_id},
    )
    if (result.rowcount or 0) == 0:
        raise HTTPException(status_code=404, detail="Notification not found")

    await db.commit()
    return {"status": "acknowledged", "id": notification_id}
