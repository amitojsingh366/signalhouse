"""Debug endpoints — test push notifications and VoIP calls."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import async_session, get_db
from trader_api.deps import (
    get_notifier,
    make_portfolio,
    make_strategy,
)
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


class TestPushResult(BaseModel):
    sent_to: int
    symbol: str
    signal: str
    strength: float
    score: float


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(db: AsyncSession = Depends(get_db)):
    """List all registered devices."""
    result = await db.execute(select(DeviceRegistration))
    return result.scalars().all()


@router.get("/top-signal")
async def get_top_signal(db: AsyncSession = Depends(get_db)):
    """Fetch the current highest-confidence signal."""
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)
    try:
        recs = await strategy.get_top_recommendations(n=5)
    finally:
        await portfolio.close()

    best = None
    for sig in [*recs.get("buys", []), *recs.get("sells", [])]:
        s = sig if isinstance(sig, dict) else sig.__dict__
        strength = s.get("strength", 0)
        if best is None or strength > best["strength"]:
            signal_type = "BUY" if sig in recs.get("buys", []) else "SELL"
            best = {
                "symbol": s.get("symbol", ""),
                "signal": signal_type,
                "strength": strength,
                "score": s.get("score", 0),
                "reasons": s.get("reasons", []),
                "price": s.get("price"),
            }
    if not best:
        return {"symbol": None, "signal": None, "strength": 0, "score": 0}
    return best


@router.post("/test-push", response_model=TestPushResult)
async def test_push(req: TestPushRequest, db: AsyncSession = Depends(get_db)):
    """Send a test push notification or VoIP call for the top signal."""
    notifier = get_notifier()
    if notifier is None or not notifier.is_configured:
        raise HTTPException(status_code=503, detail="APNs notifier not configured")

    # Get top signal
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)
    try:
        recs = await strategy.get_top_recommendations(n=5)
    finally:
        await portfolio.close()

    best = None
    for sig in [*recs.get("buys", []), *recs.get("sells", [])]:
        s = sig if isinstance(sig, dict) else sig.__dict__
        strength = s.get("strength", 0)
        if best is None or strength > best.get("strength", 0):
            signal_type = "BUY" if sig in recs.get("buys", []) else "SELL"
            best = {
                "symbol": s.get("symbol", ""),
                "signal": signal_type,
                "strength": strength,
                "score": s.get("score", 0),
            }

    if not best or not best["symbol"]:
        raise HTTPException(status_code=404, detail="No signals available")

    # Resolve target devices
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    query = select(DeviceRegistration).where(
        DeviceRegistration.enabled.is_(True),
        or_(
            DeviceRegistration.daily_disabled_date.is_(None),
            DeviceRegistration.daily_disabled_date != today,
        ),
    )
    if req.device_token:
        query = query.where(DeviceRegistration.device_token == req.device_token)

    result = await db.execute(query)
    devices = result.scalars().all()

    if not devices:
        raise HTTPException(status_code=404, detail="No matching devices found")

    sent = 0
    for device in devices:
        if req.push_type == "call":
            # VoIP push — uses device_token (PushKit token)
            await notifier.notify_signal(
                db_session_factory=async_session,
                symbol=best["symbol"],
                signal=best["signal"],
                strength=best["strength"],
                score=best["score"],
                device_token=device.device_token,
            )
            sent += 1
        else:
            # Standard alert push — uses push_token (APNs standard token)
            token = device.push_token
            if not token:
                continue
            strength_pct = int(best["strength"] * 100)
            delivered = await notifier.send_alert_push(
                token,
                title=f"{best['signal']} {best['symbol']} {strength_pct}%",
                body=f"Score: {best['score']}/9 | Strength: {strength_pct}%",
                category="debug_test",
                data={"symbol": best["symbol"], "signal": best["signal"]},
            )
            if delivered:
                sent += 1

    return TestPushResult(
        sent_to=sent,
        symbol=best["symbol"],
        signal=best["signal"],
        strength=best["strength"],
        score=best["score"],
    )
