"""Recommendation engine — scans universe, generates signals, checks exits.

Sector-aware: tracks portfolio diversification and suggests sell-to-fund
when cash is zero. No execution — recommendations only.
"""

from __future__ import annotations

import logging
from typing import Any

from trader.market_data import MarketData
from trader.portfolio import Portfolio
from trader.risk import RiskManager
from trader.signals import Signal, SignalResult, compute_indicators, generate_signal

logger = logging.getLogger(__name__)


class Strategy:
    def __init__(
        self,
        market_data: MarketData,
        risk: RiskManager,
        portfolio: Portfolio,
        config: dict[str, Any],
    ) -> None:
        self.market_data = market_data
        self.risk = risk
        self.portfolio = portfolio
        self.config = config
        self.max_sector_pct: float = config["strategy"].get("max_sector_pct", 0.40)

        # Build flat symbol list + sector lookup from config
        self.symbol_to_sector: dict[str, str] = {}
        self.symbols: list[str] = []

        sectors = config["strategy"].get("sectors")
        if sectors and isinstance(sectors, dict):
            for sector_name, entries in sectors.items():
                for entry in entries:
                    sym = entry if isinstance(entry, str) else entry["symbol"]
                    self.symbols.append(sym)
                    self.symbol_to_sector[sym] = sector_name
        else:
            # Fallback: flat list (no sector info)
            self.symbols = config["strategy"].get("symbols", [])

    def get_sector(self, symbol: str) -> str:
        """Return sector for a symbol, or 'unknown'."""
        return self.symbol_to_sector.get(symbol, "unknown")

    def get_sector_exposure(
        self, live_prices: dict[str, float]
    ) -> dict[str, dict[str, Any]]:
        """Calculate current portfolio exposure by sector.

        Returns dict of sector -> {value, pct, symbols}.
        """
        total_value = self.portfolio.get_portfolio_value(live_prices)
        if total_value <= 0:
            return {}

        exposure: dict[str, dict[str, Any]] = {}
        for symbol, h in self.portfolio.holdings.items():
            price = live_prices.get(symbol, h["avg_cost"])
            value = h["quantity"] * price
            sector = self.get_sector(symbol)

            if sector not in exposure:
                exposure[sector] = {"value": 0.0, "pct": 0.0, "symbols": []}
            exposure[sector]["value"] += value
            exposure[sector]["symbols"].append(symbol)

        for sector_data in exposure.values():
            sector_data["pct"] = sector_data["value"] / total_value

        return exposure

    async def analyze_symbol(self, symbol: str) -> SignalResult:
        """Run full signal analysis on a single symbol (used by recheck button)."""
        df = await self.market_data.get_historical_data(symbol, period="60d")
        if df is None or len(df) < 35:
            return SignalResult(
                symbol=symbol,
                signal=Signal.HOLD,
                strength=0.0,
                reasons=["Insufficient data"],
            )

        df = compute_indicators(df, self.config)
        result = generate_signal(df, self.config)
        result.symbol = symbol

        # Attach current price and ATR for context
        result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
        atr = df["atr"].iloc[-1]
        if atr == atr:  # not NaN
            result.reasons.append(f"ATR: ${atr:.2f}")

        sector = self.get_sector(symbol)
        if sector != "unknown":
            result.reasons.append(f"Sector: {sector}")

        return result

    async def scan_universe(self) -> list[SignalResult]:
        """Scan all symbols and return BUY/SELL signals sorted by strength."""
        logger.info("Scanning %d symbols...", len(self.symbols))
        results: list[SignalResult] = []
        errors = 0

        for symbol in self.symbols:
            try:
                df = await self.market_data.get_historical_data(symbol, period="60d")
                if df is None or len(df) < 35:
                    continue

                df = compute_indicators(df, self.config)
                result = generate_signal(df, self.config)
                result.symbol = symbol

                # Only include actionable signals
                if result.signal == Signal.BUY and result.strength >= 0.4:
                    result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
                    results.append(result)
                elif result.signal == Signal.SELL and result.strength >= 0.3:
                    result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
                    results.append(result)

            except Exception:
                errors += 1
                logger.exception("Error scanning %s", symbol)

        results.sort(key=lambda r: r.strength, reverse=True)
        logger.info(
            "Scan complete: %d actionable signals, %d errors", len(results), errors
        )
        return results

    async def get_exit_alerts(
        self, live_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Check current holdings for exit conditions."""
        alerts: list[dict[str, Any]] = []

        for symbol, h in self.portfolio.holdings.items():
            current_price = live_prices.get(symbol)
            if current_price is None:
                continue

            # Check trailing stop
            stop_hit = self.risk.update_stops(symbol, current_price)
            if stop_hit is not None:
                alerts.append({
                    "symbol": symbol,
                    "reason": "Stop loss hit",
                    "detail": f"Price ${current_price:.2f} hit stop at ${stop_hit:.2f}",
                    "severity": "high",
                    "current_price": current_price,
                    "entry_price": h["avg_cost"],
                    "pnl_pct": (current_price - h["avg_cost"]) / h["avg_cost"] * 100,
                })
                continue

            # Check max hold time
            if self.risk.should_exit_time(symbol):
                alerts.append({
                    "symbol": symbol,
                    "reason": "Max hold time reached",
                    "detail": (
                        f"Held for {self.config['strategy']['max_hold_days']}+ days"
                    ),
                    "severity": "medium",
                    "current_price": current_price,
                    "entry_price": h["avg_cost"],
                    "pnl_pct": (current_price - h["avg_cost"]) / h["avg_cost"] * 100,
                })
                continue

            # Check for sell signal
            try:
                df = await self.market_data.get_historical_data(symbol, period="30d")
                if df is not None and len(df) >= 35:
                    df = compute_indicators(df, self.config)
                    result = generate_signal(df, self.config)
                    if result.signal == Signal.SELL and result.strength >= 0.3:
                        alerts.append({
                            "symbol": symbol,
                            "reason": "Sell signal",
                            "detail": ", ".join(result.reasons),
                            "severity": "medium",
                            "current_price": current_price,
                            "entry_price": h["avg_cost"],
                            "pnl_pct": (
                                (current_price - h["avg_cost"]) / h["avg_cost"] * 100
                            ),
                        })
            except Exception:
                logger.exception("Error checking sell signal for %s", symbol)

        return alerts

    async def get_premarket_movers(self) -> list[dict[str, Any]]:
        """Get premarket movers for CDR symbols."""
        return await self.market_data.get_premarket_movers()

    async def _rank_holdings_to_sell(
        self, live_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Rank current holdings by desirability to sell (worst first).

        Considers: signal strength (sell signals rank higher), P&L %,
        sector over-concentration, and hold time.
        """
        ranked: list[dict[str, Any]] = []
        exposure = self.get_sector_exposure(live_prices)

        for symbol, h in self.portfolio.holdings.items():
            price = live_prices.get(symbol, h["avg_cost"])
            value = h["quantity"] * price
            pnl_pct = (
                (price - h["avg_cost"]) / h["avg_cost"] * 100
                if h["avg_cost"] > 0 else 0.0
            )
            sector = self.get_sector(symbol)
            sector_pct = exposure.get(sector, {}).get("pct", 0.0)

            # Run signal analysis on the held position
            sell_score = 0.0
            try:
                df = await self.market_data.get_historical_data(symbol, period="30d")
                if df is not None and len(df) >= 35:
                    df = compute_indicators(df, self.config)
                    result = generate_signal(df, self.config)
                    if result.signal == Signal.SELL:
                        sell_score = result.strength
                    elif result.signal == Signal.HOLD:
                        sell_score = 0.1  # neutral
            except Exception:
                pass

            # Higher score = more desirable to sell
            score = sell_score * 2.0  # strong sell signal is top priority
            if sector_pct > self.max_sector_pct:
                score += 0.5  # over-concentrated sector
            if self.risk.should_exit_time(symbol):
                score += 0.3  # held too long

            ranked.append({
                "symbol": symbol,
                "quantity": h["quantity"],
                "price": price,
                "value": value,
                "pnl_pct": pnl_pct,
                "sector": sector,
                "sector_pct": sector_pct,
                "sell_score": score,
                "has_sell_signal": sell_score >= 0.3,
            })

        ranked.sort(key=lambda x: x["sell_score"], reverse=True)
        return ranked

    async def get_top_recommendations(
        self, n: int = 5
    ) -> dict[str, Any]:
        """Get top recommendations with sell-to-fund suggestions and sector context.

        Returns:
            {
                "buys": [SignalResult, ...],
                "sells": [SignalResult, ...],
                "funding": [{"buy": symbol, "sell": {...holding info...}}, ...],
                "sector_exposure": {...},
            }
        """
        all_signals = await self.scan_universe()

        buys = [s for s in all_signals if s.signal == Signal.BUY]
        sells = [s for s in all_signals if s.signal == Signal.SELL]

        # Get live prices for portfolio context
        held_symbols = list(self.portfolio.holdings.keys())
        prices = (
            await self.market_data.get_batch_prices(held_symbols)
            if held_symbols else {}
        )
        exposure = self.get_sector_exposure(prices)

        # Filter buys: penalise signals that would over-concentrate a sector
        filtered_buys: list[SignalResult] = []
        for sig in buys:
            sector = self.get_sector(sig.symbol)
            sector_pct = exposure.get(sector, {}).get("pct", 0.0)
            if sector_pct >= self.max_sector_pct:
                sig.reasons.append(
                    f"Sector '{sector}' already at {sector_pct:.0%} of portfolio"
                )
                sig.strength *= 0.5  # demote but still show
            if sector != "unknown":
                sig.reasons.append(f"Sector: {sector}")
            filtered_buys.append(sig)

        # Re-sort after strength adjustment
        filtered_buys.sort(key=lambda r: r.strength, reverse=True)
        top_buys = filtered_buys[:n]
        top_sells = sells[:n]

        # Generate sell-to-fund suggestions if cash is low
        funding: list[dict[str, Any]] = []
        cash = self.portfolio.cash
        if top_buys and held_symbols and cash < 50.0:
            ranked_to_sell = await self._rank_holdings_to_sell(prices)
            if ranked_to_sell:
                # Pair each buy with the best holding to sell for funding
                for buy_sig in top_buys:
                    buy_sector = self.get_sector(buy_sig.symbol)
                    # Prefer selling from same sector (rebalance) or weakest
                    best = None
                    for candidate in ranked_to_sell:
                        # Don't suggest selling what we just recommended buying
                        if candidate["symbol"] == buy_sig.symbol:
                            continue
                        # Prefer same-sector swaps
                        if best is None:
                            best = candidate
                        elif (
                            candidate["sector"] == buy_sector
                            and best["sector"] != buy_sector
                        ):
                            best = candidate
                    if best:
                        funding.append({"buy": buy_sig.symbol, "sell": best})

        return {
            "buys": top_buys,
            "sells": top_sells,
            "funding": funding,
            "sector_exposure": exposure,
        }
