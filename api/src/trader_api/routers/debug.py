"""Debug endpoints — test push notifications and VoIP calls."""

from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import get_notifier

router = APIRouter(
    prefix="/api/debug",
    tags=["debug"],
    dependencies=[Depends(require_auth)],
)
logger = logging.getLogger(__name__)


class DeviceOut(BaseModel):
    device_token: str
    push_token: str | None
    platform: str
    enabled: bool

    model_config = {"from_attributes": True}


class TestPushRequest(BaseModel):
    push_type: Literal["call", "notification"]
    device_token: str | None = None  # None = all devices
    respect_mutes: bool = False
    symbol: str
    signal: str
    strength: float
    score: float


class TestPushResult(BaseModel):
    sent_to: int
    symbol: str
    signal: str
    strength: float
    score: float


class NotificationStatusOut(BaseModel):
    notifier_configured: bool
    total_devices: int
    enabled_devices: int
    devices_with_push_token: int
    calls_muted_today: int
    notifications_muted_today: int
    call_eligible_devices: int
    alert_eligible_devices: int
    utc_now: str


async def _load_debug_devices(
    db: AsyncSession,
    *,
    device_token: str | None = None,
    only_enabled: bool = False,
) -> list[dict[str, Any]]:
    """Load device rows safely across old/new table shapes."""
    result = await db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'device_registrations'
            """
        )
    )
    columns = {str(row[0]) for row in result}
    if "device_token" not in columns:
        raise HTTPException(
            status_code=500,
            detail="device_registrations.device_token column is missing",
        )

    select_parts = ["device_token"]
    select_parts.append(
        "push_token"
        if "push_token" in columns
        else "NULL::VARCHAR AS push_token"
    )
    select_parts.append(
        "platform" if "platform" in columns else "'ios'::VARCHAR AS platform"
    )
    select_parts.append(
        "COALESCE(enabled, TRUE) AS enabled"
        if "enabled" in columns
        else "TRUE AS enabled"
    )
    select_parts.append(
        "daily_disabled_date"
        if "daily_disabled_date" in columns
        else "NULL::VARCHAR AS daily_disabled_date"
    )
    select_parts.append(
        "daily_disabled_notifications_date"
        if "daily_disabled_notifications_date" in columns
        else "NULL::VARCHAR AS daily_disabled_notifications_date"
    )
    select_parts.append(
        "daily_disabled_calls_date"
        if "daily_disabled_calls_date" in columns
        else "NULL::VARCHAR AS daily_disabled_calls_date"
    )

    where_parts: list[str] = []
    params: dict[str, Any] = {}
    if only_enabled and "enabled" in columns:
        where_parts.append("COALESCE(enabled, TRUE) = TRUE")
    if device_token:
        where_parts.append("device_token = :device_token")
        params["device_token"] = device_token

    sql = f"SELECT {', '.join(select_parts)} FROM device_registrations"
    if where_parts:
        sql += f" WHERE {' AND '.join(where_parts)}"

    rows = await db.execute(text(sql), params)
    return [dict(row) for row in rows.mappings().all()]


def _is_muted(
    primary_mute_date: str | None,
    legacy_mute_date: str | None,
    *,
    today: str,
) -> bool:
    if primary_mute_date is not None:
        return primary_mute_date == today
    return legacy_mute_date == today


@router.get("/notification-status", response_model=NotificationStatusOut)
async def notification_status(db: AsyncSession = Depends(get_db)):
    """Quick diagnostics for push/call notification readiness."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    rows = await _load_debug_devices(db)
    enabled_rows = [row for row in rows if bool(row["enabled"])]
    with_push = [row for row in enabled_rows if row["push_token"]]
    calls_muted = [
        row
        for row in enabled_rows
        if _is_muted(
            row["daily_disabled_calls_date"],
            row["daily_disabled_date"],
            today=today,
        )
    ]
    notifications_muted = [
        row
        for row in enabled_rows
        if _is_muted(
            row["daily_disabled_notifications_date"],
            row["daily_disabled_date"],
            today=today,
        )
    ]
    call_eligible = [
        row
        for row in enabled_rows
        if not _is_muted(
            row["daily_disabled_calls_date"],
            row["daily_disabled_date"],
            today=today,
        )
    ]
    alert_eligible = [
        row
        for row in enabled_rows
        if row["push_token"]
        and not _is_muted(
            row["daily_disabled_notifications_date"],
            row["daily_disabled_date"],
            today=today,
        )
    ]

    notifier = get_notifier()
    return NotificationStatusOut(
        notifier_configured=bool(notifier and notifier.is_configured),
        total_devices=len(rows),
        enabled_devices=len(enabled_rows),
        devices_with_push_token=len(with_push),
        calls_muted_today=len(calls_muted),
        notifications_muted_today=len(notifications_muted),
        call_eligible_devices=len(call_eligible),
        alert_eligible_devices=len(alert_eligible),
        utc_now=datetime.now(UTC).isoformat(),
    )


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(db: AsyncSession = Depends(get_db)):
    """List all registered devices."""
    rows = await _load_debug_devices(db)
    return [
        DeviceOut(
            device_token=str(row["device_token"]),
            push_token=row["push_token"],
            platform=(str(row["platform"]) if row["platform"] else "ios"),
            enabled=bool(row["enabled"]),
        )
        for row in rows
    ]


@router.post("/test-push", response_model=TestPushResult)
async def test_push(req: TestPushRequest, db: AsyncSession = Depends(get_db)):
    """Send a test push notification or VoIP call for the given signal."""
    notifier = get_notifier()
    if notifier is None or not notifier.is_configured:
        raise HTTPException(status_code=503, detail="APNs notifier not configured")
    if not math.isfinite(req.strength) or not math.isfinite(req.score):
        raise HTTPException(
            status_code=400,
            detail="strength and score must be finite numbers",
        )

    # Resolve target devices
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    all_devices = await _load_debug_devices(
        db,
        device_token=req.device_token,
        only_enabled=True,
    )
    if req.push_type == "call" and req.respect_mutes:
        devices = [
            row
            for row in all_devices
            if not _is_muted(
                row["daily_disabled_calls_date"],
                row["daily_disabled_date"],
                today=today,
            )
        ]
    elif req.push_type == "notification" and req.respect_mutes:
        devices = [
            row
            for row in all_devices
            if row["push_token"]
            and not _is_muted(
                row["daily_disabled_notifications_date"],
                row["daily_disabled_date"],
                today=today,
            )
        ]
    elif req.push_type == "notification":
        devices = [row for row in all_devices if row["push_token"]]
    else:
        devices = all_devices

    if not devices:
        raise HTTPException(status_code=404, detail="No matching devices found")

    sent = 0
    strength_pct = int(req.strength * 100)
    for device in devices:
        try:
            if req.push_type == "call":
                delivered = await notifier.send_voip_push(
                    str(device["device_token"]),
                    {
                        "aps": {},
                        "uuid": str(uuid.uuid4()),
                        "caller_name": f"{req.signal} {req.symbol} {strength_pct}%",
                        "symbol": req.symbol,
                        "signal": req.signal,
                        "strength": req.strength,
                        "score": f"{req.score}/9",
                        "handle": "trader-debug",
                    },
                )
            else:
                token = device["push_token"]
                if token is None:
                    continue
                delivered = await notifier.send_alert_push(
                    str(token),
                    title=f"{req.signal} {req.symbol} {strength_pct}%",
                    body=f"Score: {req.score}/9 | Strength: {strength_pct}%",
                    category="debug_test",
                    data={"symbol": req.symbol, "signal": req.signal},
                )
            if delivered:
                sent += 1
        except Exception:
            token = str(device.get("device_token", ""))
            logger.exception("Debug test push failed for device %s", token[:8])

    return TestPushResult(
        sent_to=sent,
        symbol=req.symbol,
        signal=req.signal,
        strength=req.strength,
        score=req.score,
    )
