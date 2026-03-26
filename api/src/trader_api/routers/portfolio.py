"""Portfolio & holdings API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.database import get_db
from trader_api.deps import get_market_data, get_risk, make_portfolio, make_strategy
from trader_api.schemas import HoldingAdvice, PnlSummary, PortfolioSummary, SnapshotOut, TradeOut

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


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
    total_value += meta.cash
    total_pnl = total_value - total_cost - meta.cash  # P&L on positions only
    # Total portfolio P&L vs initial capital
    initial = meta.initial_capital or total_value
    portfolio_pnl = total_value - initial

    return PortfolioSummary(
        holdings=items,
        total_value=total_value,
        cash=meta.cash,
        total_cost=total_cost,
        total_pnl=portfolio_pnl,
        total_pnl_pct=(portfolio_pnl / initial * 100) if initial > 0 else 0.0,
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
    return await portfolio.get_all_snapshots()
