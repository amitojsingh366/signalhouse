"""Signal and recommendation API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import get_commodity, get_market_data, get_risk, make_portfolio, make_strategy
from trader_api.schemas import ExitAlertOut, InsightsOut, RecommendationOut, SignalOut

router = APIRouter(prefix="/api/signals", tags=["signals"], dependencies=[Depends(require_auth)])


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
        score=result.score,
        reasons=result.reasons,
        price=price,
        sector=strategy.get_sector(result.symbol),
    )


@router.get("/recommend", response_model=RecommendationOut)
async def get_recommendations(n: int = 5, db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)

    recs = await strategy.get_top_recommendations(n=n)

    # Fetch exit alerts (stop losses, max hold time, sell signals for holdings)
    holdings = await portfolio.get_holdings_dict()
    exit_alerts: list[ExitAlertOut] = []
    if holdings:
        held_symbols = list(holdings.keys())
        prices = await strategy.market_data.get_batch_prices(held_symbols)
        raw_alerts = await strategy.get_exit_alerts(prices)
        exit_alerts = [
            ExitAlertOut(
                symbol=a["symbol"],
                reason=a["reason"],
                detail=a["detail"],
                severity=a["severity"],
                current_price=a["current_price"],
                entry_price=a["entry_price"],
                pnl_pct=a["pnl_pct"],
            )
            for a in raw_alerts
        ]

    def _to_signal_out(s):
        return SignalOut(
            symbol=s.symbol,
            signal=s.signal.value,
            strength=s.strength,
            score=s.score,
            reasons=s.reasons,
            sector=strategy.get_sector(s.symbol),
        )

    buys = [_to_signal_out(s) for s in recs["buys"]]
    sells = [_to_signal_out(s) for s in recs["sells"]]
    watchlist_sells = [_to_signal_out(s) for s in recs.get("watchlist_sells", [])]

    return RecommendationOut(
        exit_alerts=exit_alerts,
        buys=buys,
        sells=sells,
        watchlist_sells=watchlist_sells,
        funding=recs.get("funding", []),
        sector_exposure=recs.get("sector_exposure", {}),
    )


@router.get("/price/{symbol}")
async def get_price(symbol: str):
    """Get current market price for a symbol."""
    symbol = symbol.upper().strip()
    md = get_market_data()
    if "." not in symbol:
        resolved = await md.resolve_symbol(symbol)
        if resolved:
            symbol = resolved
    price = await md.get_current_price(symbol)
    return {"symbol": symbol, "price": price}


@router.get("/history/{symbol}")
async def get_price_history(symbol: str, period: str = "60d"):
    """Get OHLCV price history for a symbol."""
    symbol = symbol.upper().strip()
    md = get_market_data()
    if "." not in symbol:
        resolved = await md.resolve_symbol(symbol)
        if resolved:
            symbol = resolved
    df = await md.get_historical_data(symbol, period=period)
    if df is None or df.empty:
        return {"symbol": symbol, "bars": []}
    bars = []
    for date, row in df.iterrows():
        bars.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(float(row.get("open", 0)), 2),
            "high": round(float(row.get("high", 0)), 2),
            "low": round(float(row.get("low", 0)), 2),
            "close": round(float(row.get("close", 0)), 2),
            "volume": int(row.get("volume", 0)),
        })
    return {"symbol": symbol, "bars": bars}


@router.get("/commodities")
async def get_commodities():
    """Get current commodity/crypto prices and overnight moves."""
    from trader_api.services.commodity import COMMODITY_SECTORS

    correlator = get_commodity()
    results = []
    for ticker, (name, _) in COMMODITY_SECTORS.items():
        data = await correlator._get_overnight_change(ticker)
        if data:
            price, change_pct = data
            results.append({
                "ticker": ticker,
                "name": name,
                "price": round(price, 2),
                "change_pct": round(change_pct * 100, 2),
            })
        else:
            results.append({
                "ticker": ticker,
                "name": name,
                "price": None,
                "change_pct": None,
            })
    return {"commodities": results}


@router.get("/premarket")
async def get_premarket_movers(db: AsyncSession = Depends(get_db)):
    """Get pre-market movers for CDR counterpart stocks."""
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)
    movers = await strategy.get_premarket_movers()
    return {"movers": movers}


@router.get("/insights", response_model=InsightsOut)
async def get_insights(db: AsyncSession = Depends(get_db)):
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)
    insights = await strategy.get_daily_insights()
    return InsightsOut(**insights)
