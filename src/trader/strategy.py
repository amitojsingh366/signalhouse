"""Recommendation engine — scans universe, generates signals, checks exits. No execution."""

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
        self.symbols: list[str] = config["strategy"]["symbols"]

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

        return result

    async def scan_universe(self) -> list[SignalResult]:
        """Scan all symbols and return BUY/SELL signals sorted by strength.

        Does NOT execute any trades — only returns recommendations.
        """
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

        # Sort by strength descending
        results.sort(key=lambda r: r.strength, reverse=True)
        logger.info(
            "Scan complete: %d actionable signals, %d errors", len(results), errors
        )
        return results

    async def get_exit_alerts(
        self, live_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Check current holdings for exit conditions.

        Returns alert dicts for positions that hit stops, max hold, or sell signals.
        Does NOT sell — just warns.
        """
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
                    "detail": f"Held for {self.config['strategy']['max_hold_days']}+ days",
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
                            "pnl_pct": (current_price - h["avg_cost"]) / h["avg_cost"] * 100,
                        })
            except Exception:
                logger.exception("Error checking sell signal for %s", symbol)

        return alerts

    async def get_premarket_movers(self) -> list[dict[str, Any]]:
        """Get premarket movers for CDR symbols."""
        return await self.market_data.get_premarket_movers()

    async def get_top_recommendations(self, n: int = 5) -> dict[str, list[SignalResult]]:
        """Get top N buy and sell recommendations."""
        all_signals = await self.scan_universe()

        buys = [s for s in all_signals if s.signal == Signal.BUY][:n]
        sells = [s for s in all_signals if s.signal == Signal.SELL][:n]

        return {"buys": buys, "sells": sells}
