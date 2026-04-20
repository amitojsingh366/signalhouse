"""Portfolio & holdings API endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import get_market_data, get_risk, make_portfolio, make_strategy
from trader_api.schemas import (
    CashUpdate,
    HoldingAdvice,
    HoldingOut,
    HoldingSparklineOut,
    HoldingsSparkOut,
    HoldingUpdate,
    PnlSummary,
    PortfolioSummary,
    SnapshotOut,
    SparkPoint,
    TradeOut,
)

router = APIRouter(
    prefix="/api/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(require_auth)],
)


@router.get("/holdings", response_model=PortfolioSummary)
async def get_holdings(db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)

    holdings = await portfolio.get_holdings_dict()
    symbols = list(holdings.keys())
    prices = await get_market_data().get_batch_prices(symbols) if symbols else {}

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
            technical_score=advice["technical_score"],
            sentiment_score=advice["sentiment_score"],
            commodity_score=advice["commodity_score"],
            action=advice["action"],
            action_detail=advice["action_detail"],
            reasons=advice["reasons"],
            alternative=advice.get("alternative"),
            entry_date=h.get("entry_date") or None,
        ))

    meta = await portfolio._get_meta()
    total_value += meta.cash

    # Total PnL should match trade history + current holdings.
    realized_pnl = await portfolio.get_realized_pnl()
    unrealized_pnl = (total_value - meta.cash) - total_cost
    total_pnl = unrealized_pnl + realized_pnl
    initial = max(0.0, total_value - total_pnl)

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


@router.get("/holdings/spark", response_model=HoldingsSparkOut)
async def get_holdings_spark(days: int = 7, db: AsyncSession = Depends(get_db)):
    if days < 2 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 2 and 90")

    portfolio = make_portfolio(db)
    holdings = await portfolio.get_holdings_dict()
    symbols = list(holdings.keys())
    if not symbols:
        return HoldingsSparkOut(days=days, series=[])

    market_data = get_market_data()
    period = "3mo" if days <= 30 else "1y"

    async def _series_for(symbol: str) -> HoldingSparklineOut:
        df = await market_data.get_historical_data(symbol, period=period)
        if df is None or df.empty:
            return HoldingSparklineOut(symbol=symbol, points=[])
        points: list[SparkPoint] = []
        for date, row in df.tail(days).iterrows():
            close = row.get("close")
            if close != close:  # NaN
                continue
            points.append(
                SparkPoint(
                    date=date.strftime("%Y-%m-%d"),
                    close=round(float(close), 2),
                )
            )
        return HoldingSparklineOut(symbol=symbol, points=points)

    series = await asyncio.gather(*[_series_for(symbol) for symbol in symbols])
    return HoldingsSparkOut(days=days, series=series)


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
    risk = get_risk()
    symbol = data.symbol.upper()
    prices = await get_market_data().get_batch_prices([symbol])
    result = await portfolio.update_holding(
        symbol, data.quantity, data.avg_cost, market_price=prices.get(symbol)
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Holding {data.symbol} not found")
    holdings = await portfolio.get_holdings_dict()
    meta = await portfolio._get_meta()
    portfolio.sync_risk_manager(
        risk,
        holdings,
        meta.initial_capital,
        preserve_existing_state=True,
    )
    return HoldingOut(**result)


@router.delete("/holding/{symbol}")
async def delete_holding(symbol: str, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    risk = get_risk()
    symbol = symbol.upper()
    prices = await get_market_data().get_batch_prices([symbol])
    deleted = await portfolio.delete_holding(symbol, market_price=prices.get(symbol))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Holding {symbol} not found")
    holdings = await portfolio.get_holdings_dict()
    meta = await portfolio._get_meta()
    portfolio.sync_risk_manager(
        risk,
        holdings,
        meta.initial_capital,
        preserve_existing_state=True,
    )
    return {"status": "deleted", "symbol": symbol.upper()}


@router.put("/cash")
async def update_cash(data: CashUpdate, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    new_cash = await portfolio.update_cash(data.cash)
    return {"cash": new_cash}
