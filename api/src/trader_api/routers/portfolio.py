"""Portfolio & holdings API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from trader_api.auth import require_auth
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.database import get_db
from trader_api.deps import get_market_data, get_risk, make_portfolio, make_strategy
from trader_api.schemas import (
    CashUpdate,
    HoldingAdvice,
    HoldingOut,
    HoldingUpdate,
    PnlSummary,
    PortfolioSummary,
    SnapshotOut,
    TradeOut,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], dependencies=[Depends(require_auth)])


@router.get("/holdings", response_model=PortfolioSummary)
async def get_holdings(db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)

    holdings = await portfolio.get_holdings_dict()
    if not holdings:
        meta = await portfolio._get_meta()
        return PortfolioSummary(
            holdings=[],
            total_value=meta.cash,
            cash=meta.cash,
            total_cost=0.0,
            total_pnl=0.0,
            total_pnl_pct=0.0,
        )

    symbols = list(holdings.keys())
    prices = await get_market_data().get_batch_prices(symbols)

    total_value = 0.0
    total_cost = 0.0
    items: list[HoldingAdvice] = []

    for sym, h in holdings.items():
        price = prices.get(sym, h["avg_cost"])
        value = h["quantity"] * price
        cost = h["quantity"] * h["avg_cost"]
        total_value += value
        total_cost += cost

        advice = await strategy.get_holding_advice(sym, price, find_alternatives=False)

        items.append(HoldingAdvice(
            symbol=sym,
            quantity=h["quantity"],
            avg_cost=h["avg_cost"],
            current_price=price,
            market_value=value,
            pnl=value - cost,
            pnl_pct=advice["pnl_pct"],
            signal=advice["signal"],
            strength=advice["strength"],
            action=advice["action"],
            action_detail=advice["action_detail"],
            reasons=advice["reasons"],
            alternative=advice.get("alternative"),
        ))

    meta = await portfolio._get_meta()
    positions_value = total_value  # sum of market values (before adding cash)
    total_value += meta.cash

    # Total P&L = unrealized (current positions) + realized (completed trades)
    unrealized_pnl = positions_value - total_cost
    realized_pnl = await portfolio.get_realized_pnl()
    total_pnl = unrealized_pnl + realized_pnl
    initial = meta.initial_capital or total_value

    return PortfolioSummary(
        holdings=items,
        total_value=total_value,
        cash=meta.cash,
        total_cost=total_cost,
        total_pnl=total_pnl,
        total_pnl_pct=(total_pnl / initial * 100) if initial > 0 else 0.0,
    )


@router.get("/pnl", response_model=PnlSummary)
async def get_pnl(db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    holdings = await portfolio.get_holdings_dict()
    symbols = list(holdings.keys())
    prices = await get_market_data().get_batch_prices(symbols) if symbols else {}

    pnl_data = await portfolio.get_daily_pnl(prices)
    recent = await portfolio.get_recent_trades(5)

    return PnlSummary(
        current_value=pnl_data["current_value"],
        initial_capital=pnl_data["initial_capital"],
        cash=pnl_data["cash"],
        daily_pnl=pnl_data["daily_pnl"],
        daily_pnl_pct=pnl_data["daily_pnl_pct"],
        total_pnl=pnl_data["total_pnl"],
        total_pnl_pct=pnl_data["total_pnl_pct"],
        recent_trades=[TradeOut(**t) for t in recent],
    )


@router.get("/snapshots", response_model=list[SnapshotOut])
async def get_snapshots(db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    # Ensure today's snapshot exists so the equity chart has current data
    holdings = await portfolio.get_holdings_dict()
    if holdings:
        symbols = list(holdings.keys())
        prices = await get_market_data().get_batch_prices(symbols)
        await portfolio.record_daily_snapshot(prices)
    return await portfolio.get_all_snapshots()


@router.put("/holding", response_model=HoldingOut)
async def update_holding(data: HoldingUpdate, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    result = await portfolio.update_holding(data.symbol.upper(), data.quantity, data.avg_cost)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Holding {data.symbol} not found")
    return HoldingOut(**result)


@router.delete("/holding/{symbol}")
async def delete_holding(symbol: str, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    deleted = await portfolio.delete_holding(symbol.upper())
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Holding {symbol} not found")
    return {"status": "deleted", "symbol": symbol.upper()}


@router.put("/cash")
async def update_cash(data: CashUpdate, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    new_cash = await portfolio.update_cash(data.cash)
    return {"cash": new_cash}
