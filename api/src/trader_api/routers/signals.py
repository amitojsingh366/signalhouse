"""Signal and recommendation API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.auth import require_auth
from trader_api.database import get_db
from trader_api.deps import (
    get_commodity,
    get_config,
    get_market_data,
    get_notifier,
    get_sentiment,
    make_portfolio,
    make_strategy,
)
from trader_api.models import DeviceRegistration, SignalSnooze
from trader_api.schemas import (
    ActionOut,
    ActionPlanOut,
    ExitAlertOut,
    InsightsOut,
    RecommendationOut,
    SignalOut,
    SnoozeIn,
    SnoozeOut,
)
from trader_api.services.signals import extract_price_from_reasons
from trader_api.services.strategy import Strategy

router = APIRouter(prefix="/api/signals", tags=["signals"], dependencies=[Depends(require_auth)])


def _signal_to_out(strategy: Strategy, signal: Any) -> SignalOut:
    return SignalOut(
        symbol=signal.symbol,
        signal=signal.signal.value,
        strength=signal.strength,
        score=signal.score,
        technical_score=signal.technical_score,
        sentiment_score=signal.sentiment_score,
        commodity_score=signal.commodity_score,
        reasons=signal.reasons,
        price=extract_price_from_reasons(signal.reasons),
        sector=strategy.get_sector(signal.symbol),
    )


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

    price = extract_price_from_reasons(result.reasons)

    fundamentals = await strategy.market_data.get_fundamentals(result.symbol)

    trade_plan = None
    if price is not None and price > 0:
        risk_cfg = get_config().get("risk", {})
        stop_loss_pct = float(risk_cfg.get("stop_loss_pct", 0.05))
        take_profit_pct = float(risk_cfg.get("take_profit_pct", 0.08))
        atr = result.meta.get("atr") if result.meta else None
        atr_value = float(atr) if isinstance(atr, (int, float)) and atr > 0 else None

        entry_low = price * 0.995
        entry_high = price * 1.01

        base_stop_distance = price * stop_loss_pct
        atr_stop_distance = (atr_value * 1.2) if atr_value else 0.0
        stop_distance = max(base_stop_distance, atr_stop_distance)
        stop_loss = max(0.0, price - stop_distance)

        base_tp_distance = price * take_profit_pct
        atr_tp1_distance = (atr_value * 2.0) if atr_value else 0.0
        tp1_distance = max(base_tp_distance, atr_tp1_distance)
        take_profit_1 = price + tp1_distance

        base_tp2_distance = tp1_distance * 1.5
        atr_tp2_distance = (atr_value * 3.0) if atr_value else 0.0
        tp2_distance = max(base_tp2_distance, atr_tp2_distance)
        take_profit_2 = price + tp2_distance

        risk_per_share = max(0.0, price - stop_loss)
        reward_tp1 = max(0.0, take_profit_1 - price)
        reward_tp2 = max(0.0, take_profit_2 - price)
        # Use directional conviction so bearish signals do not inflate buy-side reward.
        conviction = max(0.0, min(1.0, float(result.score) / 9.0))
        # Conviction-aware expected reward between TP1 (conservative) and TP2 (stretch).
        reward_per_share = reward_tp1 + ((reward_tp2 - reward_tp1) * conviction)
        risk_reward_ratio = (
            reward_per_share / risk_per_share
            if risk_per_share > 0
            else None
        )
        risk_reward_tp1 = (
            reward_tp1 / risk_per_share
            if risk_per_share > 0
            else None
        )
        risk_reward_tp2 = (
            reward_tp2 / risk_per_share
            if risk_per_share > 0
            else None
        )

        trade_plan = {
            "entry_low": round(entry_low, 4),
            "entry_high": round(entry_high, 4),
            "stop_loss": round(stop_loss, 4),
            "take_profit_1": round(take_profit_1, 4),
            "take_profit_2": round(take_profit_2, 4),
            "risk_reward_ratio": round(risk_reward_ratio, 2)
            if risk_reward_ratio is not None
            else None,
            "risk_reward_tp1": round(risk_reward_tp1, 2)
            if risk_reward_tp1 is not None
            else None,
            "risk_reward_tp2": round(risk_reward_tp2, 2)
            if risk_reward_tp2 is not None
            else None,
            "atr": round(atr_value, 4) if atr_value is not None else None,
        }

    return SignalOut(
        symbol=result.symbol,
        signal=result.signal.value,
        strength=result.strength,
        score=result.score,
        technical_score=result.technical_score,
        sentiment_score=result.sentiment_score,
        commodity_score=result.commodity_score,
        reasons=result.reasons,
        price=price,
        sector=strategy.get_sector(result.symbol),
        fundamentals=fundamentals,
        trade_plan=trade_plan,
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
                pnl=a.get("pnl"),
                quantity=a.get("quantity"),
                days_held=a.get("days_held"),
                entry_date=a.get("entry_date"),
                action=a.get("action"),
                action_detail=a.get("action_detail"),
            )
            for a in raw_alerts
        ]

    buys = [_signal_to_out(strategy, s) for s in recs["buys"]]
    sells = [_signal_to_out(strategy, s) for s in recs["sells"]]
    watchlist_sells = [
        _signal_to_out(strategy, s) for s in recs.get("watchlist_sells", [])
    ]
    suppressed_signals = [
        _signal_to_out(strategy, s) for s in recs.get("suppressed_signals", [])
    ]

    return RecommendationOut(
        exit_alerts=exit_alerts,
        buys=buys,
        sells=sells,
        watchlist_sells=watchlist_sells,
        suppressed_signals=suppressed_signals,
        funding=recs.get("funding", []),
        sector_exposure=recs.get("sector_exposure", {}),
    )


@router.post("/snooze", response_model=SnoozeOut)
async def snooze_signal(body: SnoozeIn, db: AsyncSession = Depends(get_db)):
    """Snooze a sell signal for a symbol."""
    symbol = body.symbol.upper().strip()
    now = datetime.now(UTC)
    # Indefinite: set expiry far in the future (10 years)
    if body.indefinite:
        expires = now + timedelta(days=3650)
    else:
        expires = now + timedelta(hours=body.hours)

    # Get current P&L for this symbol
    portfolio = make_portfolio(db)
    holdings = await portfolio.get_holdings_dict()
    pnl_pct = 0.0
    if symbol in holdings:
        h = holdings[symbol]
        md = get_market_data()
        price = await md.get_current_price(symbol)
        if price and h["avg_cost"] > 0:
            pnl_pct = (price - h["avg_cost"]) / h["avg_cost"] * 100

    # Upsert
    existing = await db.execute(
        select(SignalSnooze).where(SignalSnooze.symbol == symbol)
    )
    snooze = existing.scalar_one_or_none()
    if snooze:
        snooze.expires_at = expires
        snooze.snoozed_at = now
        snooze.pnl_pct_at_snooze = pnl_pct
        snooze.indefinite = body.indefinite
        snooze.phantom_trailing_stop = body.phantom_trailing_stop
    else:
        snooze = SignalSnooze(
            symbol=symbol,
            snoozed_at=now,
            expires_at=expires,
            pnl_pct_at_snooze=pnl_pct,
            indefinite=body.indefinite,
            phantom_trailing_stop=body.phantom_trailing_stop,
        )
        db.add(snooze)
    await db.commit()
    await db.refresh(snooze)
    return snooze


@router.delete("/snooze/{symbol}")
async def unsnooze_signal(symbol: str, db: AsyncSession = Depends(get_db)):
    """Remove a snooze for a symbol."""
    symbol = symbol.upper().strip()
    await db.execute(delete(SignalSnooze).where(SignalSnooze.symbol == symbol))
    await db.commit()
    return {"status": "ok", "symbol": symbol}


@router.get("/snoozed", response_model=list[SnoozeOut])
async def get_snoozed(db: AsyncSession = Depends(get_db)):
    """List all active (non-expired) snoozes."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(SignalSnooze).where(SignalSnooze.expires_at > now)
    )
    return list(result.scalars().all())


@router.get("/actions", response_model=ActionPlanOut)
async def get_action_plan(db: AsyncSession = Depends(get_db)):
    """Get today's prioritized, position-sized action plan."""
    portfolio = make_portfolio(db)
    strategy = make_strategy(portfolio)

    plan = await strategy.get_action_plan()

    # Filter snoozed sells (auto-unsnooze if phantom trailing stop triggers)
    now = datetime.now(UTC)
    result = await db.execute(
        select(SignalSnooze).where(SignalSnooze.expires_at > now)
    )
    snoozed = {s.symbol: s for s in result.scalars().all()}

    filtered_actions = []
    snoozed_actions = []
    auto_unsnoozed: list[tuple[str, float, float]] = []  # (symbol, current, at_snooze)
    for a in plan["actions"]:
        sym = a.get("symbol") or a.get("sell_symbol")
        if sym and sym in snoozed and a["type"] in ("SELL", "SWAP"):
            snz = snoozed[sym]
            current_pnl = a.get("pnl_pct") or a.get("sell_pnl_pct") or 0.0
            # Phantom trailing stop: auto-unsnooze if loss worsened by 3%+
            if snz.phantom_trailing_stop and current_pnl < snz.pnl_pct_at_snooze - 3.0:
                await db.execute(
                    delete(SignalSnooze).where(SignalSnooze.symbol == sym)
                )
                snz_pnl = snz.pnl_pct_at_snooze
                a["reason"] = (
                    f"AUTO-UNSNOOZED: loss worsened "
                    f"({current_pnl:+.1f}% vs {snz_pnl:+.1f}%)"
                )
                filtered_actions.append(a)
                auto_unsnoozed.append((sym, current_pnl, snz_pnl))
            else:
                a["snoozed"] = True
                snoozed_actions.append(a)
        else:
            filtered_actions.append(a)
    await db.commit()

    # Send push notification for auto-unsnoozed symbols
    if auto_unsnoozed:
        notifier = get_notifier()
        if notifier is not None and notifier.is_configured:
            for sym, cur_pnl, snz_pnl in auto_unsnoozed:
                title = f"Auto-Unsnoozed: {sym}"
                body_text = (
                    f"Loss worsened from {snz_pnl:+.1f}% to {cur_pnl:+.1f}% "
                    f"since snooze. Review action plan."
                )
                result2 = await db.execute(
                    select(DeviceRegistration).where(
                        DeviceRegistration.push_token.is_not(None)
                    )
                )
                for dev in result2.scalars().all():
                    if dev.push_token:
                        await notifier.send_alert_push(
                            dev.push_token,
                            title=title,
                            body=body_text,
                            data={"type": "auto_unsnooze", "symbol": sym},
                        )

    all_actions = filtered_actions + snoozed_actions

    return ActionPlanOut(
        actions=[ActionOut(**a) for a in all_actions],
        portfolio_value=plan["portfolio_value"],
        cash=plan["cash"],
        num_positions=plan["num_positions"],
        max_positions=plan["max_positions"],
        sells_count=sum(1 for a in filtered_actions if a["type"] == "SELL"),
        buys_count=sum(1 for a in filtered_actions if a["type"] == "BUY"),
        swaps_count=sum(1 for a in filtered_actions if a["type"] == "SWAP"),
        suppressed_signals=[
            _signal_to_out(strategy, s) for s in plan.get("suppressed_signals", [])
        ],
        sector_exposure=plan.get("sector_exposure", {}),
    )


@router.post("/scan-now", response_model=ActionPlanOut)
async def run_scan_now(db: AsyncSession = Depends(get_db)):
    """Force a fresh scan and invalidate in-memory caches."""
    get_market_data().clear_caches()
    get_sentiment().clear_cache()
    get_commodity().clear_cache()
    Strategy.invalidate_recommendations_cache()
    return await get_action_plan(db)


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
