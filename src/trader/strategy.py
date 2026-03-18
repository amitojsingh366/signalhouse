"""Core strategy engine — scans universe, generates signals, executes trades."""

from __future__ import annotations

import logging
from typing import Any

from trader.broker import Broker
from trader.notifier import Notifier
from trader.risk import RiskManager
from trader.signals import Signal, bars_to_dataframe, compute_indicators, generate_signal

logger = logging.getLogger(__name__)


class Strategy:
    def __init__(
        self,
        broker: Broker,
        risk: RiskManager,
        notifier: Notifier,
        config: dict[str, Any],
    ) -> None:
        self.broker = broker
        self.risk = risk
        self.notifier = notifier
        self.config = config
        self.symbols: list[str] = config["strategy"]["symbols"]
        self.initial_capital = 0.0

    async def initialize(self) -> None:
        """Set initial capital tracking."""
        self.initial_capital = self.broker.get_account_value()
        self.risk.peak_portfolio_value = self.initial_capital
        logger.info("Strategy initialized — capital: $%.2f", self.initial_capital)

    async def scan_and_trade(self) -> None:
        """Main loop iteration: scan all symbols for signals, manage positions."""
        if not self.broker.is_connected:
            logger.warning("Broker disconnected, skipping scan")
            return

        portfolio_value = self.broker.get_account_value()

        # Check drawdown limits
        if self.risk.check_drawdown(portfolio_value):
            await self.notifier.halt_alert(self.risk.halt_reason)
            return

        # 1. Check existing positions for exits
        await self._check_exits()

        # 2. Scan for new entries
        await self._scan_entries(portfolio_value)

    async def _check_exits(self) -> None:
        """Check if any open positions should be closed."""
        for symbol in list(self.risk.open_trades.keys()):
            try:
                bars = await self.broker.get_historical_data(symbol, duration="30 D")
                if not bars:
                    continue

                df = bars_to_dataframe(bars)
                current_price = df["close"].iloc[-1]

                # Check stop loss / trailing stop
                stop_hit = self.risk.update_stops(symbol, current_price)
                if stop_hit is not None:
                    await self._execute_sell(symbol, "Stop loss hit")
                    continue

                # Check max hold time
                if self.risk.should_exit_time(symbol):
                    await self._execute_sell(symbol, "Max hold time reached")
                    continue

                # Check for sell signal
                df = compute_indicators(df, self.config)
                result = generate_signal(df, self.config)
                if result.signal == Signal.SELL and result.strength >= 0.3:
                    await self._execute_sell(symbol, ", ".join(result.reasons))

            except Exception:
                logger.exception("Error checking exit for %s", symbol)

    async def _scan_entries(self, portfolio_value: float) -> None:
        """Scan universe for buy signals."""
        if not self.risk.can_open_position():
            return

        candidates: list[tuple[str, float, list[str], float]] = []  # symbol, strength, reasons, atr

        for symbol in self.symbols:
            # Skip if already holding
            if symbol in self.risk.open_trades:
                continue

            try:
                bars = await self.broker.get_historical_data(symbol, duration="60 D")
                if not bars:
                    continue

                df = bars_to_dataframe(bars)
                df = compute_indicators(df, self.config)
                result = generate_signal(df, self.config)
                result.symbol = symbol

                if result.signal == Signal.BUY and result.strength >= 0.4:
                    atr = df["atr"].iloc[-1]
                    candidates.append((symbol, result.strength, result.reasons, atr))

            except Exception:
                logger.exception("Error scanning %s", symbol)

        if not candidates:
            return

        # Sort by signal strength, take the best one
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_symbol, _, reasons, atr = candidates[0]

        # Get current price
        bars = await self.broker.get_historical_data(best_symbol, duration="5 D")
        if not bars:
            return
        price = bars_to_dataframe(bars)["close"].iloc[-1]

        # Calculate position size
        shares = self.risk.calculate_position_size(portfolio_value, price, atr)
        if shares <= 0:
            return

        await self._execute_buy(best_symbol, shares, price, reasons)

    async def _execute_buy(
        self, symbol: str, quantity: int, price: float, reasons: list[str]
    ) -> None:
        """Execute a buy order and notify."""
        try:
            await self.broker.buy(symbol, quantity)
            self.risk.register_entry(symbol, price, quantity)
            await self.notifier.trade_alert("BUY", symbol, quantity, price, reasons)
            logger.info("Bought %d x %s @ ~$%.2f", quantity, symbol, price)
        except Exception:
            logger.exception("Failed to buy %s", symbol)
            await self.notifier.error_alert(f"Failed to buy {symbol}")

    async def _execute_sell(self, symbol: str, reason: str) -> None:
        """Execute a sell order and notify."""
        trade_info = self.risk.open_trades.get(symbol)
        if trade_info is None:
            return

        try:
            await self.broker.sell(symbol, trade_info.quantity)
            # Get approximate exit price
            bars = await self.broker.get_historical_data(symbol, duration="5 D")
            exit_price = (
                bars_to_dataframe(bars)["close"].iloc[-1] if bars else trade_info.entry_price
            )

            pnl = (exit_price - trade_info.entry_price) * trade_info.quantity
            pnl_pct = (exit_price - trade_info.entry_price) / trade_info.entry_price * 100

            self.risk.register_exit(symbol)
            await self.notifier.trade_alert(
                "SELL", symbol, trade_info.quantity, exit_price,
                [reason, f"P&L: ${pnl:.2f} ({pnl_pct:+.1f}%)"],
            )
            logger.info(
                "Sold %d x %s @ ~$%.2f — P&L: $%.2f",
                trade_info.quantity, symbol, exit_price, pnl,
            )
        except Exception:
            logger.exception("Failed to sell %s", symbol)
            await self.notifier.error_alert(f"Failed to sell {symbol}")

    async def send_daily_status(self) -> None:
        """Send end-of-day portfolio summary to Discord."""
        portfolio_value = self.broker.get_account_value()
        cash = self.broker.get_cash()
        pnl_pct = 0.0
        if self.initial_capital > 0:
            pnl_pct = (portfolio_value - self.initial_capital) / self.initial_capital * 100

        positions = []
        for p in await self.broker.get_positions():
            pnl_pct_pos = 0.0
            if p.avg_cost > 0:
                pnl_pct_pos = (p.current_price - p.avg_cost) / p.avg_cost * 100
            positions.append({
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_cost": p.avg_cost,
                "current_price": p.current_price,
                "pnl_pct": pnl_pct_pos,
            })

        await self.notifier.status_update(portfolio_value, cash, positions, pnl_pct)
