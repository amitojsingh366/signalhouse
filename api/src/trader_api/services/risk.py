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
    highest_price: float
    stop_price: float


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
        self.daily_start_value = portfolio_value
        self.peak_portfolio_value = max(self.peak_portfolio_value, portfolio_value)

    def check_drawdown(self, current_value: float) -> bool:
        if self.halted:
            return True

        if self.daily_start_value > 0:
            daily_loss = (self.daily_start_value - current_value) / self.daily_start_value
            if daily_loss >= self.risk["max_daily_loss_pct"]:
                self.halted = True
                self.halt_reason = f"Daily drawdown limit hit: {daily_loss:.1%}"
                logger.warning("HALT: %s", self.halt_reason)
                return True

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
        if self.halted:
            return False
        return len(self.open_trades) < self.risk["max_positions"]

    def calculate_position_size(self, portfolio_value: float, price: float, atr: float) -> float:
        if price <= 0 or portfolio_value <= 0:
            return 0

        max_dollars = portfolio_value * self.risk["max_position_pct"]
        risk_per_trade = portfolio_value * 0.02
        if atr > 0:
            atr_shares = int(risk_per_trade / (2 * atr))
        else:
            atr_shares = int(max_dollars / price)

        max_shares = int(max_dollars / price)
        shares = min(atr_shares, max_shares)

        return max(shares, 1) if max_dollars >= price else 0

    def register_entry(self, symbol: str, price: float, quantity: float) -> None:
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
        if symbol in self.open_trades:
            del self.open_trades[symbol]
            logger.info("Registered exit: %s", symbol)

    def update_stops(self, symbol: str, current_price: float) -> float | None:
        trade = self.open_trades.get(symbol)
        if trade is None:
            return None

        if current_price > trade.highest_price:
            trade.highest_price = current_price
            # Tighten trailing stop once gain exceeds threshold
            tighten_at = self.risk.get("tighten_stop_at_pct", 0.05)
            gain_from_entry = (
                (trade.highest_price - trade.entry_price) / trade.entry_price
            )
            if gain_from_entry >= tighten_at:
                trail_pct = self.risk.get("tightened_trail_pct", 0.015)
            else:
                trail_pct = self.risk["trailing_stop_pct"]
            new_stop = current_price * (1 - trail_pct)
            if new_stop > trade.stop_price:
                trade.stop_price = new_stop

        if current_price <= trade.stop_price:
            logger.warning(
                "STOP HIT: %s — price $%.2f <= stop $%.2f",
                symbol, current_price, trade.stop_price,
            )
            return trade.stop_price

        return None

    def should_take_profit(self, symbol: str, current_price: float) -> bool:
        """Check if a position has hit the take-profit threshold."""
        trade = self.open_trades.get(symbol)
        if trade is None:
            return False
        take_profit_pct = self.risk.get("take_profit_pct", 0.08)
        gain = (current_price - trade.entry_price) / trade.entry_price
        return gain >= take_profit_pct

    def get_gain_pct(self, symbol: str, current_price: float) -> float | None:
        """Return current gain % from entry, or None if not tracked."""
        trade = self.open_trades.get(symbol)
        if trade is None:
            return None
        return (current_price - trade.entry_price) / trade.entry_price

    def should_exit_time(self, symbol: str) -> bool:
        trade = self.open_trades.get(symbol)
        if trade is None:
            return False
        days_held = (datetime.now() - trade.entry_time).days
        return days_held >= self.config["strategy"]["max_hold_days"]
