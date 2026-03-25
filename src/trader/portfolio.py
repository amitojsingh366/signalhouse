"""JSON-backed portfolio tracking — records trades, holdings, and P&L."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trader.risk import RiskManager

logger = logging.getLogger(__name__)


class Portfolio:
    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = {
            "cash": 0.0,
            "initial_capital": 0.0,
            "holdings": {},
            "trade_history": [],
            "daily_snapshots": {},
        }

    def load(self) -> None:
        """Load portfolio state from disk."""
        if self.data_path.exists():
            with open(self.data_path) as f:
                self._data = json.load(f)
            logger.info(
                "Loaded portfolio: $%.2f cash, %d holdings",
                self._data["cash"],
                len(self._data["holdings"]),
            )
        else:
            logger.info("No portfolio file found, starting fresh")

    def save(self) -> None:
        """Persist portfolio state to disk."""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w") as f:
            json.dump(self._data, f, indent=2, default=str)

    @property
    def cash(self) -> float:
        return self._data["cash"]

    @property
    def initial_capital(self) -> float:
        return self._data["initial_capital"]

    @property
    def holdings(self) -> dict[str, dict[str, Any]]:
        return self._data["holdings"]

    @property
    def trade_history(self) -> list[dict[str, Any]]:
        return self._data["trade_history"]

    async def record_buy(
        self, symbol: str, quantity: float, price: float, risk: RiskManager | None = None
    ) -> dict[str, Any]:
        """Record a buy trade. Returns the trade record."""
        async with self._lock:
            total = quantity * price

            # Update or create holding
            if symbol in self._data["holdings"]:
                h = self._data["holdings"][symbol]
                old_qty = h["quantity"]
                old_cost = h["avg_cost"]
                new_qty = old_qty + quantity
                # Weighted average cost
                h["avg_cost"] = (old_cost * old_qty + price * quantity) / new_qty
                h["quantity"] = new_qty
            else:
                self._data["holdings"][symbol] = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "avg_cost": price,
                    "entry_date": datetime.now(UTC).isoformat(),
                }

            trade = {
                "symbol": symbol,
                "action": "BUY",
                "quantity": quantity,
                "price": price,
                "total": total,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            self._data["trade_history"].append(trade)

            # Register with risk manager if provided
            if risk is not None:
                risk.register_entry(symbol, price, quantity)

            self.save()
            logger.info("Recorded BUY: %.4f x %s @ $%.2f", quantity, symbol, price)
            return trade

    async def record_sell(
        self, symbol: str, quantity: float, price: float, risk: RiskManager | None = None
    ) -> dict[str, Any] | None:
        """Record a sell trade. Returns the trade record, or None if not enough shares."""
        async with self._lock:
            h = self._data["holdings"].get(symbol)
            if h is None:
                logger.warning("Cannot sell %s — not in holdings", symbol)
                return None

            if quantity > h["quantity"] + 0.0001:  # small tolerance for float comparison
                logger.warning(
                    "Cannot sell %.4f %s — only hold %.4f",
                    quantity, symbol, h["quantity"],
                )
                return None

            total = quantity * price
            pnl = (price - h["avg_cost"]) * quantity
            pnl_pct = (price - h["avg_cost"]) / h["avg_cost"] * 100 if h["avg_cost"] > 0 else 0.0

            # Update holding
            remaining = h["quantity"] - quantity
            if remaining < 0.0001:  # effectively zero
                del self._data["holdings"][symbol]
            else:
                h["quantity"] = remaining

            trade = {
                "symbol": symbol,
                "action": "SELL",
                "quantity": quantity,
                "price": price,
                "total": total,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            self._data["trade_history"].append(trade)

            # Register with risk manager if provided
            if risk is not None:
                if symbol not in self._data["holdings"]:
                    risk.register_exit(symbol)

            self.save()
            logger.info(
                "Recorded SELL: %.4f x %s @ $%.2f — P&L: $%.2f (%.1f%%)",
                quantity, symbol, price, pnl, pnl_pct,
            )
            return trade

    async def sync_from_snapshot(
        self, parsed_holdings: list[dict[str, Any]], risk: RiskManager | None = None
    ) -> None:
        """Replace all holdings with parsed screenshot data.

        Each item in parsed_holdings should have: symbol, quantity, market_value_cad.
        """
        async with self._lock:
            # Clear existing holdings and risk trades
            if risk is not None:
                for sym in list(risk.open_trades.keys()):
                    risk.register_exit(sym)
            self._data["holdings"] = {}

            total_value = 0.0
            for h in parsed_holdings:
                symbol = h["symbol"]
                quantity = h["quantity"]
                value = h["market_value_cad"]
                avg_cost = value / quantity if quantity > 0 else 0.0

                self._data["holdings"][symbol] = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "avg_cost": avg_cost,
                    "entry_date": datetime.now(UTC).isoformat(),
                }
                total_value += value

                if risk is not None:
                    risk.register_entry(symbol, avg_cost, quantity)

            # Set initial capital if not set yet
            if self._data["initial_capital"] == 0:
                self._data["initial_capital"] = total_value + self._data["cash"]

            self.save()
            logger.info(
                "Synced %d holdings from screenshot (total value: $%.2f)",
                len(parsed_holdings), total_value,
            )

    def get_portfolio_value(self, live_prices: dict[str, float]) -> float:
        """Calculate total portfolio value using live prices."""
        value = self._data["cash"]
        for symbol, h in self._data["holdings"].items():
            price = live_prices.get(symbol, h["avg_cost"])
            value += h["quantity"] * price
        return value

    def get_holdings_with_pnl(
        self, live_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Return all holdings with current price and P&L."""
        result = []
        for symbol, h in self._data["holdings"].items():
            current_price = live_prices.get(symbol, h["avg_cost"])
            market_value = h["quantity"] * current_price
            cost_basis = h["quantity"] * h["avg_cost"]
            pnl = market_value - cost_basis
            pnl_pct = (
                (current_price - h["avg_cost"]) / h["avg_cost"] * 100
                if h["avg_cost"] > 0 else 0.0
            )

            result.append({
                "symbol": symbol,
                "quantity": h["quantity"],
                "avg_cost": h["avg_cost"],
                "current_price": current_price,
                "market_value": market_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "entry_date": h.get("entry_date", ""),
            })
        return result

    def get_daily_pnl(self, live_prices: dict[str, float]) -> dict[str, Any]:
        """Calculate daily and total P&L."""
        current_value = self.get_portfolio_value(live_prices)
        initial = self._data["initial_capital"] or current_value

        # Find yesterday's snapshot for daily P&L
        snapshots = self._data.get("daily_snapshots", {})
        dates = sorted(snapshots.keys())
        yesterday_value = dates and snapshots[dates[-1]].get("portfolio_value", initial) or initial

        return {
            "current_value": current_value,
            "initial_capital": initial,
            "total_pnl": current_value - initial,
            "total_pnl_pct": (current_value - initial) / initial * 100 if initial > 0 else 0.0,
            "daily_pnl": current_value - yesterday_value,
            "daily_pnl_pct": (
                (current_value - yesterday_value) / yesterday_value * 100
                if yesterday_value > 0
                else 0.0
            ),
            "cash": self._data["cash"],
        }

    def record_daily_snapshot(self, live_prices: dict[str, float]) -> None:
        """Record end-of-day portfolio snapshot."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        current_value = self.get_portfolio_value(live_prices)
        positions_value = current_value - self._data["cash"]

        if "daily_snapshots" not in self._data:
            self._data["daily_snapshots"] = {}

        self._data["daily_snapshots"][today] = {
            "portfolio_value": current_value,
            "cash": self._data["cash"],
            "positions_value": positions_value,
        }
        self.save()

    def sync_risk_manager(self, risk: RiskManager) -> None:
        """On startup, replay open holdings into the RiskManager."""
        for symbol, h in self._data["holdings"].items():
            risk.register_entry(symbol, h["avg_cost"], h["quantity"])

        # Set peak portfolio value if we have initial capital
        if self._data["initial_capital"] > 0:
            risk.peak_portfolio_value = self._data["initial_capital"]

        logger.info(
            "Synced %d holdings to risk manager", len(self._data["holdings"])
        )

    def get_recent_trades(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent trades."""
        return self._data["trade_history"][-limit:]
