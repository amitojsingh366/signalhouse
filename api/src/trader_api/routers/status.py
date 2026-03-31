"""Status and upload API endpoints."""

from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import get_config, get_market_data, get_risk, make_portfolio, make_strategy
from trader_api.schemas import StatusOut, UploadConfirm, UploadHolding
from trader_api.services.vision import parse_holdings_screenshot

router = APIRouter(prefix="/api", tags=["status"], dependencies=[Depends(require_auth)])

ET = ZoneInfo("America/New_York")
_start_time = time.time()


def _is_market_hours(config: dict) -> bool:
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    market_open = datetime.strptime(config["schedule"]["market_open"], "%H:%M").time()
    market_close = datetime.strptime(config["schedule"]["market_close"], "%H:%M").time()
    return market_open <= now.time() <= market_close


@router.get("/status", response_model=StatusOut)
async def get_status(db: AsyncSession = Depends(get_db)):
    config = get_config()
    risk = get_risk()
    portfolio = make_portfolio(db)
    holdings = await portfolio.get_holdings_dict()

    return StatusOut(
        symbols_tracked=len(get_market_data().symbols),
        holdings_count=len(holdings),
        market_open=_is_market_hours(config),
        uptime_seconds=time.time() - _start_time,
        scan_interval_minutes=config["schedule"]["scan_interval_minutes"],
        risk_halted=risk.halted,
        risk_halt_reason=risk.halt_reason,
    )


@router.post("/upload/parse", response_model=list[UploadHolding])
async def parse_upload(file: UploadFile = File(...)):
    config = get_config()
    api_key = config.get("anthropic", {}).get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")

    image_data = await file.read()
    media_type = file.content_type or "image/png"

    parsed = await parse_holdings_screenshot(image_data, api_key, media_type)
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not parse holdings from image")

    # Resolve symbols
    market_data = get_market_data()
    resolved = []
    for h in parsed:
        raw = h["symbol"]
        if "." not in raw:
            sym = await market_data.resolve_symbol(raw)
            if sym:
                h["symbol"] = sym
        resolved.append(UploadHolding(**h))

    return resolved


@router.post("/upload/confirm")
async def confirm_upload(data: UploadConfirm, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    risk = get_risk()

    holdings = [h.model_dump() for h in data.holdings]
    await portfolio.sync_from_snapshot(holdings, risk)
    return {"status": "ok", "count": len(holdings)}


@router.get("/symbols")
async def get_symbols():
    """Return the full symbol universe with sector info."""
    config = get_config()
    sectors = config["strategy"].get("sectors", {})
    result = []
    for sector_name, entries in sectors.items():
        for entry in entries:
            sym = entry if isinstance(entry, str) else entry["symbol"]
            name = entry.get("name", sym) if isinstance(entry, dict) else sym
            result.append({"symbol": sym, "name": name, "sector": sector_name})
    return result
