"""Risk management: position sizing, stop losses, drawdown circuit breakers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OpenTrade:
    symbol: str
    entry_price: float
    quantity: float
    entry_time: datetime
    highest_price: float  # For trailing stop
    stop_price: float  # Current stop loss price


@dataclass
class RiskManager:
    config: dict[str, Any]
    open_trades: dict[str, OpenTrade] = field(default_factory=dict)
    peak_portfolio_value: float = 0.0
    daily_start_value: float = 0.0
    halted: bool = False
    halt_reason: str = ""

    def __post_init__(self) -> None:
        self.risk = self.config["risk"]

    def reset_daily(self, portfolio_value: float) -> None:
        """Call at market open each day."""
        self.daily_start_value = portfolio_value
        self.peak_portfolio_value = max(self.peak_portfolio_value, portfolio_value)

    def check_drawdown(self, current_value: float) -> bool:
        """Check if drawdown limits are breached. Returns True if trading should halt."""
        if self.halted:
            return True

        # Daily drawdown
        if self.daily_start_value > 0:
            daily_loss = (self.daily_start_value - current_value) / self.daily_start_value
            if daily_loss >= self.risk["max_daily_loss_pct"]:
                self.halted = True
                self.halt_reason = f"Daily drawdown limit hit: {daily_loss:.1%}"
                logger.warning("HALT: %s", self.halt_reason)
                return True

        # Total drawdown from peak
        if self.peak_portfolio_value > 0:
            total_dd = (self.peak_portfolio_value - current_value) / self.peak_portfolio_value
            if total_dd >= self.risk["max_total_drawdown_pct"]:
                self.halted = True
                self.halt_reason = f"Total drawdown limit hit: {total_dd:.1%}"
                logger.warning("HALT: %s", self.halt_reason)
                return True

        self.peak_portfolio_value = max(self.peak_portfolio_value, current_value)
        return False

    def can_open_position(self) -> bool:
        """Check if we're allowed to open a new position."""
        if self.halted:
            return False
        return len(self.open_trades) < self.risk["max_positions"]

    def calculate_position_size(self, portfolio_value: float, price: float, atr: float) -> float:
        """Calculate number of shares to buy.

        Uses ATR-based sizing: risk a fixed % of portfolio per trade,
        with the stop distance set by ATR. Also respects max position %.
        """
        if price <= 0 or portfolio_value <= 0:
            return 0

        # Max dollar amount for this position
        max_dollars = portfolio_value * self.risk["max_position_pct"]

        # ATR-based sizing: risk 2% of portfolio with stop at 2*ATR
        risk_per_trade = portfolio_value * 0.02
        if atr > 0:
            atr_shares = int(risk_per_trade / (2 * atr))
        else:
            atr_shares = int(max_dollars / price)

        # Cap by max position size
        max_shares = int(max_dollars / price)
        shares = min(atr_shares, max_shares)

        # Must buy at least 1 share
        return max(shares, 1) if max_dollars >= price else 0

    def register_entry(self, symbol: str, price: float, quantity: float) -> None:
        """Record a new position entry."""
        stop = price * (1 - self.risk["stop_loss_pct"])
        self.open_trades[symbol] = OpenTrade(
            symbol=symbol,
            entry_price=price,
            quantity=quantity,
            entry_time=datetime.now(),
            highest_price=price,
            stop_price=stop,
        )
        logger.info("Registered entry: %s @ $%.2f, stop @ $%.2f", symbol, price, stop)

    def register_exit(self, symbol: str) -> None:
        """Record a position exit."""
        if symbol in self.open_trades:
            del self.open_trades[symbol]
            logger.info("Registered exit: %s", symbol)

    def update_stops(self, symbol: str, current_price: float) -> float | None:
        """Update trailing stop. Returns stop price if stop is hit, None otherwise."""
        trade = self.open_trades.get(symbol)
        if trade is None:
            return None

        # Update highest price
        if current_price > trade.highest_price:
            trade.highest_price = current_price
            # Trail the stop up
            new_stop = current_price * (1 - self.risk["trailing_stop_pct"])
            if new_stop > trade.stop_price:
                trade.stop_price = new_stop

        # Check if stop hit
        if current_price <= trade.stop_price:
            logger.warning(
                "STOP HIT: %s — price $%.2f <= stop $%.2f",
                symbol, current_price, trade.stop_price,
            )
            return trade.stop_price

        return None

    def should_exit_time(self, symbol: str) -> bool:
        """Check if position has exceeded max hold time."""
        trade = self.open_trades.get(symbol)
        if trade is None:
            return False
        days_held = (datetime.now() - trade.entry_time).days
        return days_held >= self.config["strategy"]["max_hold_days"]
