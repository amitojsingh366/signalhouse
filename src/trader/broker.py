"""Interactive Brokers connection and order management via ib_insync."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from ib_insync import IB, LimitOrder, MarketOrder, Order, Stock, Trade

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float
    unrealized_pnl: float


class Broker:
    """Wraps ib_insync to provide a clean interface for the strategy engine."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.ib = IB()
        self.host = config["broker"]["host"]
        self.port = config["broker"]["port"]
        self.client_id = config["broker"]["client_id"]
        self.account = config["broker"].get("account", "")

    async def connect(self) -> None:
        """Connect to IB Gateway / TWS."""
        await self.ib.connectAsync(
            host=self.host,
            port=self.port,
            clientId=self.client_id,
            account=self.account,
            readonly=False,
        )
        logger.info("Connected to IBKR — account: %s", self.ib.managedAccounts())

    def disconnect(self) -> None:
        self.ib.disconnect()

    @property
    def is_connected(self) -> bool:
        return self.ib.isConnected()

    def get_account_value(self) -> float:
        """Get total account net liquidation value in CAD."""
        for item in self.ib.accountValues():
            if item.tag == "NetLiquidation" and item.currency == "CAD":
                return float(item.value)
        # Fallback: try base currency
        for item in self.ib.accountValues():
            if item.tag == "NetLiquidation":
                return float(item.value)
        return 0.0

    def get_cash(self) -> float:
        """Get available cash in CAD."""
        for item in self.ib.accountValues():
            if item.tag == "AvailableFunds" and item.currency == "CAD":
                return float(item.value)
        return 0.0

    async def get_positions(self) -> list[Position]:
        """Get all current positions."""
        positions = []
        for pos in self.ib.positions():
            contract = pos.contract
            ticker = self.ib.reqMktData(contract)
            await asyncio.sleep(1)  # Wait for market data
            current_price = ticker.marketPrice()
            if current_price != current_price:  # NaN check
                current_price = pos.avgCost

            positions.append(Position(
                symbol=f"{contract.symbol}.{contract.exchange or 'TO'}",
                quantity=pos.position,
                avg_cost=pos.avgCost,
                current_price=current_price,
                unrealized_pnl=(current_price - pos.avgCost) * pos.position,
            ))
        return positions

    def make_contract(self, symbol: str) -> Stock:
        """Create a Stock contract for a Canadian-listed security.

        Accepts symbols like 'RY.TO' (TSX) or 'AAPL.NE' (CBOE Canada CDR).
        Routes TSX stocks via TSE, CDRs via SMART with no primaryExchange.
        """
        if symbol.endswith(".NE"):
            clean = symbol.replace(".NE", "")
            return Stock(clean, "SMART", "CAD")
        clean = symbol.replace(".TO", "")
        return Stock(clean, "TSE", "CAD")

    async def get_historical_data(
        self,
        symbol: str,
        duration: str = "60 D",
        bar_size: str = "1 day",
    ) -> list[Any]:
        """Fetch historical bars for a symbol."""
        contract = self.make_contract(symbol)
        await self.ib.qualifyContractsAsync(contract)
        bars = await self.ib.reqHistoricalDataAsync(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="ADJUSTED_LAST",
            useRTH=True,
            formatDate=1,
        )
        return bars

    async def _wait_for_fill(self, trade: Trade, timeout: float = 30) -> Trade:
        """Wait for a trade to fill or fail. Raises on rejection/cancellation."""
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            status = trade.orderStatus.status
            if status == "Filled":
                return trade
            if status in ("Cancelled", "Inactive", "ApiCancelled"):
                last_log = trade.log[-1].message if trade.log else "unknown reason"
                raise RuntimeError(f"Order {status}: {last_log}")
            await asyncio.sleep(0.5)
        raise RuntimeError(f"Order timed out after {timeout}s (status: {trade.orderStatus.status})")

    async def buy(self, symbol: str, quantity: int, order_type: str = "market") -> Trade:
        """Place a buy order and wait for fill confirmation."""
        contract = self.make_contract(symbol)
        await self.ib.qualifyContractsAsync(contract)

        order: Order
        if order_type == "market":
            order = MarketOrder("BUY", quantity)
        else:
            ticker = self.ib.reqMktData(contract)
            await asyncio.sleep(1)
            price = ticker.marketPrice()
            order = LimitOrder("BUY", quantity, price)

        trade = self.ib.placeOrder(contract, order)
        logger.info("BUY %d x %s — order ID %s", quantity, symbol, trade.order.orderId)
        return await self._wait_for_fill(trade)

    async def sell(self, symbol: str, quantity: int, order_type: str = "market") -> Trade:
        """Place a sell order and wait for fill confirmation."""
        contract = self.make_contract(symbol)
        await self.ib.qualifyContractsAsync(contract)

        order: Order
        if order_type == "market":
            order = MarketOrder("SELL", quantity)
        else:
            ticker = self.ib.reqMktData(contract)
            await asyncio.sleep(1)
            price = ticker.marketPrice()
            order = LimitOrder("SELL", quantity, price)

        trade = self.ib.placeOrder(contract, order)
        logger.info("SELL %d x %s — order ID %s", quantity, symbol, trade.order.orderId)
        return await self._wait_for_fill(trade)
