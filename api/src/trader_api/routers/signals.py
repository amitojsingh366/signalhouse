"""Signal and recommendation API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.database import get_db
from trader_api.deps import make_portfolio, make_strategy
from trader_api.schemas import InsightsOut, RecommendationOut, SignalOut

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/check/{symbol}", response_model=SignalOut)
async def check_signal(symbol: str, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)

    symbol = symbol.upper().strip()
    if "." not in symbol:
        resolved = await strategy.market_data.resolve_symbol(symbol)
        if resolved:
            symbol = resolved

    result = await strategy.analyze_symbol(symbol)

    price = None
    for r in result.reasons:
        if r.startswith("Price: $"):
            try:
                price = float(r.split("$")[1])
            except (ValueError, IndexError):
                pass

    return SignalOut(
        symbol=result.symbol,
        signal=result.signal.value,
        strength=result.strength,
        reasons=result.reasons,
        price=price,
        sector=strategy.get_sector(result.symbol),
    )


@router.get("/recommend", response_model=RecommendationOut)
async def get_recommendations(n: int = 5, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)

    recs = await strategy.get_top_recommendations(n=n)

    buys = [
        SignalOut(
            symbol=s.symbol,
            signal=s.signal.value,
            strength=s.strength,
            reasons=s.reasons,
            sector=strategy.get_sector(s.symbol),
        )
        for s in recs["buys"]
    ]
    sells = [
        SignalOut(
            symbol=s.symbol,
            signal=s.signal.value,
            strength=s.strength,
            reasons=s.reasons,
            sector=strategy.get_sector(s.symbol),
        )
        for s in recs["sells"]
    ]

    return RecommendationOut(
        buys=buys,
        sells=sells,
        funding=recs.get("funding", []),
        sector_exposure=recs.get("sector_exposure", {}),
    )


@router.get("/insights", response_model=InsightsOut)
async def get_insights(db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)
    insights = await strategy.get_daily_insights()
    return InsightsOut(**insights)
