"""Trade recording API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import get_market_data, get_risk, make_portfolio
from trader_api.schemas import TradeIn, TradeOut, TradeUpdate
from trader_api.services.portfolio import Portfolio, PortfolioReplayError
from trader_api.services.strategy import Strategy

router = APIRouter(prefix="/api/trades", tags=["trades"], dependencies=[Depends(require_auth)])


async def _live_prices_for_replay(
    portfolio: Portfolio, extra_symbols: set[str] | None = None
) -> dict[str, float]:
    holdings = await portfolio.get_holdings_dict()
    trades = await portfolio._get_trades_chronological()
    symbols = set(holdings)
    symbols.update(t.symbol for t in trades)
    if extra_symbols:
        symbols.update(sym.upper() for sym in extra_symbols if sym)
    return await get_market_data().get_batch_prices(list(symbols)) if symbols else {}


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


@router.put("/{trade_id}", response_model=TradeOut)
async def update_trade(
    trade_id: int,
    data: TradeUpdate,
    db: AsyncSession = Depends(get_db),
):
    portfolio = make_portfolio(db)
    risk = get_risk()
    prices = await _live_prices_for_replay(
        portfolio,
        {data.symbol} if data.symbol else None,
    )
    try:
        result = await portfolio.update_trade(
            trade_id,
            action=data.action,
            symbol=data.symbol.upper() if data.symbol else None,
            quantity=data.quantity,
            price=data.price,
            risk=risk,
            live_prices=prices,
        )
    except PortfolioReplayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    Strategy.invalidate_recommendations_cache()
    return TradeOut(**result)


@router.delete("/{trade_id}")
async def delete_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    risk = get_risk()
    prices = await _live_prices_for_replay(portfolio)
    try:
        deleted = await portfolio.delete_trade(
            trade_id,
            risk=risk,
            live_prices=prices,
        )
    except PortfolioReplayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    Strategy.invalidate_recommendations_cache()
    return {"status": "deleted", "id": trade_id}
