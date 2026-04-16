"""Trade recording API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import get_risk, make_portfolio
from trader_api.schemas import TradeIn, TradeOut
from trader_api.services.strategy import Strategy

router = APIRouter(prefix="/api/trades", tags=["trades"], dependencies=[Depends(require_auth)])


@router.post("/buy", response_model=TradeOut)
async def record_buy(trade: TradeIn, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    risk = get_risk()
    result = await portfolio.record_buy(
        trade.symbol.upper(), trade.quantity, trade.price, risk
    )
    # Portfolio changed — invalidate cached signals so they reflect new diversification
    Strategy.invalidate_recommendations_cache()
    return TradeOut(**result)


@router.post("/sell", response_model=TradeOut)
async def record_sell(trade: TradeIn, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    risk = get_risk()
    result = await portfolio.record_sell(
        trade.symbol.upper(), trade.quantity, trade.price, risk
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Insufficient holdings to sell")
    # Portfolio changed — invalidate cached signals so they reflect new diversification
    Strategy.invalidate_recommendations_cache()
    return TradeOut(**result)


@router.get("/history", response_model=list[TradeOut])
async def get_trade_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    trades = await portfolio.get_recent_trades(limit)
    return [TradeOut(**t) for t in trades]
