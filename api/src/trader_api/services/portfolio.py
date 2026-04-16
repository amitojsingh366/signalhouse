"""PostgreSQL-backed portfolio tracking — records trades, holdings, and P&L."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.models import DailySnapshot, Holding, PortfolioMeta, Trade
from trader_api.services.risk import RiskManager

logger = logging.getLogger(__name__)


class Portfolio:
    """Portfolio manager backed by PostgreSQL."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._meta_cache: PortfolioMeta | None = None

    async def close(self) -> None:
        """Close the underlying DB session."""
        await self.db.close()

    async def _get_meta(self) -> PortfolioMeta:
        if self._meta_cache is not None:
            return self._meta_cache
        result = await self.db.execute(select(PortfolioMeta))
        meta = result.scalar_one_or_none()
        if meta is None:
            meta = PortfolioMeta(cash=0.0, initial_capital=0.0)
            self.db.add(meta)
            await self.db.commit()
            await self.db.refresh(meta)
        self._meta_cache = meta
        return meta

    @property
    async def cash(self) -> float:
        meta = await self._get_meta()
        return meta.cash

    @property
    async def initial_capital(self) -> float:
        meta = await self._get_meta()
        return meta.initial_capital

    async def get_holdings_dict(self) -> dict[str, dict[str, Any]]:
        """Return holdings as a dict keyed by symbol (matches old JSON format)."""
        result = await self.db.execute(select(Holding))
        holdings = result.scalars().all()
        return {
            h.symbol: {
                "symbol": h.symbol,
                "quantity": h.quantity,
                "avg_cost": h.avg_cost,
                "entry_date": h.entry_date.isoformat() if h.entry_date else "",
            }
            for h in holdings
        }

    async def get_holdings_list(self) -> list[Holding]:
        result = await self.db.execute(select(Holding))
        return list(result.scalars().all())

    async def record_buy(
        self, symbol: str, quantity: float, price: float, risk: RiskManager | None = None
    ) -> dict[str, Any]:
        total = quantity * price

        result = await self.db.execute(select(Holding).where(Holding.symbol == symbol))
        existing = result.scalar_one_or_none()

        if existing:
            old_qty = existing.quantity
            old_cost = existing.avg_cost
            new_qty = old_qty + quantity
            existing.avg_cost = (old_cost * old_qty + price * quantity) / new_qty
            existing.quantity = new_qty
            avg_cost = existing.avg_cost
        else:
            holding = Holding(
                symbol=symbol,
                quantity=quantity,
                avg_cost=price,
                entry_date=datetime.now(UTC),
            )
            self.db.add(holding)
            avg_cost = price

        trade = Trade(
            symbol=symbol,
            action="BUY",
            quantity=quantity,
            price=price,
            total=total,
            timestamp=datetime.now(UTC),
        )
        self.db.add(trade)

        # Deduct cash
        meta = await self._get_meta()
        meta.cash -= total

        if risk is not None:
            risk.register_entry(symbol, price, quantity)

        await self.db.commit()
        self._meta_cache = None
        logger.info(
            "Recorded BUY: %.4f x %s @ $%.2f avg=$%.2f (cash now $%.2f)",
            quantity, symbol, price, avg_cost, meta.cash,
        )
        return {
            "symbol": symbol,
            "action": "BUY",
            "quantity": quantity,
            "price": price,
            "total": total,
            "avg_cost": avg_cost,
            "timestamp": trade.timestamp.isoformat() if trade.timestamp else "",
        }

    async def record_sell(
        self, symbol: str, quantity: float, price: float, risk: RiskManager | None = None
    ) -> dict[str, Any] | None:
        result = await self.db.execute(select(Holding).where(Holding.symbol == symbol))
        h = result.scalar_one_or_none()

        if h is None:
            logger.warning("Cannot sell %s — not in holdings", symbol)
            return None

        if quantity > h.quantity + 0.0001:
            logger.warning("Cannot sell %.4f %s — only hold %.4f", quantity, symbol, h.quantity)
            return None

        total = quantity * price
        avg_cost = h.avg_cost
        pnl = (price - avg_cost) * quantity
        pnl_pct = (price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0.0

        remaining = h.quantity - quantity
        if remaining < 0.0001:
            await self.db.delete(h)
        else:
            h.quantity = remaining

        trade = Trade(
            symbol=symbol,
            action="SELL",
            quantity=quantity,
            price=price,
            total=total,
            pnl=pnl,
            pnl_pct=pnl_pct,
            timestamp=datetime.now(UTC),
        )
        self.db.add(trade)

        # Add proceeds to cash
        meta = await self._get_meta()
        meta.cash += total

        if risk is not None:
            if remaining < 0.0001:
                risk.register_exit(symbol)

        await self.db.commit()
        self._meta_cache = None
        logger.info(
            "Recorded SELL: %.4f x %s @ $%.2f — P&L: $%.2f (%.1f%%) (cash now $%.2f)",
            quantity, symbol, price, pnl, pnl_pct, meta.cash,
        )
        return {
            "symbol": symbol,
            "action": "SELL",
            "quantity": quantity,
            "price": price,
            "total": total,
            "avg_cost": avg_cost,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "timestamp": trade.timestamp.isoformat() if trade.timestamp else "",
        }

    async def sync_from_snapshot(
        self, parsed_holdings: list[dict[str, Any]], risk: RiskManager | None = None
    ) -> None:
        if risk is not None:
            for sym in list(risk.open_trades.keys()):
                risk.register_exit(sym)

        # Delete all existing holdings
        result = await self.db.execute(select(Holding))
        for h in result.scalars().all():
            await self.db.delete(h)

        total_value = 0.0
        for h in parsed_holdings:
            symbol = h["symbol"]
            quantity = h["quantity"]
            value = h["market_value_cad"]
            avg_cost = value / quantity if quantity > 0 else 0.0

            holding = Holding(
                symbol=symbol,
                quantity=quantity,
                avg_cost=avg_cost,
                entry_date=datetime.now(UTC),
            )
            self.db.add(holding)
            total_value += value

            if risk is not None:
                risk.register_entry(symbol, avg_cost, quantity)

        meta = await self._get_meta()
        if meta.initial_capital == 0:
            meta.initial_capital = total_value + meta.cash

        await self.db.commit()
        self._meta_cache = None
        logger.info(
            "Synced %d holdings from snapshot (total value: $%.2f)",
            len(parsed_holdings), total_value,
        )

    async def update_holding(
        self, symbol: str, quantity: float | None = None, avg_cost: float | None = None
    ) -> dict[str, Any] | None:
        """Update quantity and/or avg_cost for an existing holding."""
        result = await self.db.execute(select(Holding).where(Holding.symbol == symbol))
        h = result.scalar_one_or_none()
        if h is None:
            return None

        if quantity is not None:
            h.quantity = quantity
        if avg_cost is not None:
            h.avg_cost = avg_cost

        await self.db.commit()
        await self.db.refresh(h)
        logger.info("Updated holding %s: qty=%.4f avg_cost=%.2f", symbol, h.quantity, h.avg_cost)
        return {
            "symbol": h.symbol,
            "quantity": h.quantity,
            "avg_cost": h.avg_cost,
            "entry_date": h.entry_date.isoformat() if h.entry_date else "",
        }

    async def delete_holding(self, symbol: str) -> bool:
        """Delete a holding entirely."""
        result = await self.db.execute(select(Holding).where(Holding.symbol == symbol))
        h = result.scalar_one_or_none()
        if h is None:
            return False
        await self.db.delete(h)
        await self.db.commit()
        logger.info("Deleted holding %s", symbol)
        return True

    async def update_cash(self, cash: float) -> float:
        """Set the cash balance directly."""
        meta = await self._get_meta()
        meta.cash = cash
        await self.db.commit()
        self._meta_cache = None
        logger.info("Updated cash to $%.2f", cash)
        return cash

    async def get_realized_pnl(self) -> float:
        """Sum of P&L from all completed sell trades."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
                Trade.action == "SELL", Trade.pnl.isnot(None)
            )
        )
        return float(result.scalar_one())

    async def get_portfolio_value(self, live_prices: dict[str, float]) -> float:
        meta = await self._get_meta()
        value = meta.cash
        holdings = await self.get_holdings_dict()
        for symbol, h in holdings.items():
            price = live_prices.get(symbol, h["avg_cost"])
            value += h["quantity"] * price
        return value

    async def get_holdings_with_pnl(
        self, live_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        holdings = await self.get_holdings_dict()
        result = []
        for symbol, h in holdings.items():
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

    async def get_daily_pnl(self, live_prices: dict[str, float]) -> dict[str, Any]:
        current_value = await self.get_portfolio_value(live_prices)
        meta = await self._get_meta()

        # Unrealized P&L: market value of current holdings - cost basis
        holdings = await self.get_holdings_dict()
        positions_value = 0.0
        total_cost = 0.0
        for symbol, h in holdings.items():
            price = live_prices.get(symbol, h["avg_cost"])
            positions_value += h["quantity"] * price
            total_cost += h["quantity"] * h["avg_cost"]
        unrealized_pnl = positions_value - total_cost

        # Realized P&L: sum of profit/loss from all completed sell trades
        realized_pnl = await self.get_realized_pnl()
        total_pnl = unrealized_pnl + realized_pnl

        initial = meta.initial_capital or current_value

        # Find previous day's snapshot for daily P&L
        # Skip today's snapshot (if it exists) so we compare against yesterday
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        result = await self.db.execute(
            select(DailySnapshot)
            .where(DailySnapshot.date < today)
            .order_by(DailySnapshot.date.desc())
            .limit(1)
        )
        prev_snap = result.scalar_one_or_none()
        yesterday_value = prev_snap.portfolio_value if prev_snap else current_value

        return {
            "current_value": current_value,
            "initial_capital": initial,
            "total_pnl": total_pnl,
            "total_pnl_pct": (total_pnl / initial * 100) if initial > 0 else 0.0,
            "daily_pnl": current_value - yesterday_value,
            "daily_pnl_pct": (
                (current_value - yesterday_value) / yesterday_value * 100
                if yesterday_value > 0
                else 0.0
            ),
            "cash": meta.cash,
        }

    async def record_daily_snapshot(self, live_prices: dict[str, float]) -> None:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        current_value = await self.get_portfolio_value(live_prices)
        meta = await self._get_meta()
        positions_value = current_value - meta.cash

        result = await self.db.execute(
            select(DailySnapshot).where(DailySnapshot.date == today)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.portfolio_value = current_value
            existing.cash = meta.cash
            existing.positions_value = positions_value
        else:
            snap = DailySnapshot(
                date=today,
                portfolio_value=current_value,
                cash=meta.cash,
                positions_value=positions_value,
            )
            self.db.add(snap)

        await self.db.commit()

    def sync_risk_manager(
        self,
        risk: RiskManager,
        holdings: dict[str, dict[str, Any]],
        initial_capital: float,
        preserve_existing_state: bool = False,
    ) -> None:
        """Replay open holdings into the RiskManager.

        When preserve_existing_state=True, keep entry_time/highest_price/stop_price
        for symbols that are still present and only refresh fields that changed
        (entry price and quantity).
        """
        if not preserve_existing_state:
            risk.open_trades.clear()
            existing = {}
        else:
            existing = risk.open_trades
            # Remove symbols no longer held so deleted positions stop being tracked.
            for symbol in list(existing.keys()):
                if symbol not in holdings:
                    del existing[symbol]
        for symbol, h in holdings.items():
            if preserve_existing_state and symbol in existing:
                trade = existing[symbol]
                trade.entry_price = h["avg_cost"]
                trade.quantity = h["quantity"]
                continue
            risk.register_entry(symbol, h["avg_cost"], h["quantity"])

        if initial_capital > 0:
            risk.peak_portfolio_value = initial_capital

        logger.info("Synced %d holdings to risk manager", len(holdings))

    async def get_recent_trades(self, limit: int = 20) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Trade).order_by(Trade.timestamp.desc(), Trade.id.desc()).limit(limit)
        )
        trades = list(result.scalars().all())
        trades.reverse()  # oldest first
        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "action": t.action,
                "quantity": t.quantity,
                "price": t.price,
                "total": t.total,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "timestamp": t.timestamp.isoformat() if t.timestamp else "",
            }
            for t in trades
        ]

    async def get_all_snapshots(self) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(DailySnapshot).order_by(DailySnapshot.date)
        )
        return [
            {
                "date": s.date,
                "portfolio_value": s.portfolio_value,
                "cash": s.cash,
                "positions_value": s.positions_value,
            }
            for s in result.scalars().all()
        ]
