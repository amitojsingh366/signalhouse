"""Debug endpoints — test push notifications and VoIP calls."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import async_session, get_db
from trader_api.deps import get_notifier
from trader_api.models import DeviceRegistration

router = APIRouter(
    prefix="/api/debug",
    tags=["debug"],
    dependencies=[Depends(require_auth)],
)


class DeviceOut(BaseModel):
    device_token: str
    push_token: str | None
    platform: str
    enabled: bool

    model_config = {"from_attributes": True}


class TestPushRequest(BaseModel):
    push_type: Literal["call", "notification"]
    device_token: str | None = None  # None = all devices
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


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(db: AsyncSession = Depends(get_db)):
    """List all registered devices."""
    # Build response explicitly so old rows with nulls don't fail response validation.
    result = await db.execute(
        select(
            DeviceRegistration.device_token,
            DeviceRegistration.push_token,
            DeviceRegistration.platform,
            DeviceRegistration.enabled,
        )
    )
    rows = result.all()
    return [
        DeviceOut(
            device_token=row.device_token,
            push_token=row.push_token,
            platform=row.platform or "ios",
            enabled=True if row.enabled is None else bool(row.enabled),
        )
        for row in rows
    ]


@router.post("/test-push", response_model=TestPushResult)
async def test_push(req: TestPushRequest, db: AsyncSession = Depends(get_db)):
    """Send a test push notification or VoIP call for the given signal."""
    notifier = get_notifier()
    if notifier is None or not notifier.is_configured:
        raise HTTPException(status_code=503, detail="APNs notifier not configured")

    # Resolve target devices
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    query = select(DeviceRegistration).where(
        DeviceRegistration.enabled.is_(True),
    )
    if req.device_token:
        query = query.where(DeviceRegistration.device_token == req.device_token)

    result = await db.execute(query)
    devices = result.scalars().all()
    if req.push_type == "call":
        devices = [device for device in devices if not device.calls_muted_on(today)]
    else:
        devices = [
            device
            for device in devices
            if device.push_token and not device.notifications_muted_on(today)
        ]

    if not devices:
        raise HTTPException(status_code=404, detail="No matching devices found")

    sent = 0
    for device in devices:
        if req.push_type == "call":
            await notifier.notify_signal(
                db_session_factory=async_session,
                symbol=req.symbol,
                signal=req.signal,
                strength=req.strength,
                score=req.score,
                device_token=device.device_token,
                push_token=device.push_token,
                send_alert=False,
            )
            sent += 1
        else:
            token = device.push_token
            if token is None:
                continue
            strength_pct = int(req.strength * 100)
            delivered = await notifier.send_alert_push(
                token,
                title=f"{req.signal} {req.symbol} {strength_pct}%",
                body=f"Score: {req.score}/9 | Strength: {strength_pct}%",
                category="debug_test",
                data={"symbol": req.symbol, "signal": req.signal},
            )
            if delivered:
                sent += 1

    return TestPushResult(
        sent_to=sent,
        symbol=req.symbol,
        signal=req.signal,
        strength=req.strength,
        score=req.score,
    )
