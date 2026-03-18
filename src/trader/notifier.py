"""Discord webhook notifications for trade alerts and status updates."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: dict[str, Any]) -> None:
        self.webhook_url = config["notifications"]["discord_webhook_url"]
        self.enabled = bool(self.webhook_url)

    async def send(self, content: str) -> None:
        """Send a message to Discord."""
        if not self.enabled:
            logger.info("Discord disabled — message: %s", content)
            return

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.webhook_url,
                    json={"content": content},
                )
        except Exception:
            logger.exception("Failed to send Discord notification")

    async def trade_alert(
        self,
        action: str,
        symbol: str,
        quantity: int,
        price: float,
        reasons: list[str],
    ) -> None:
        """Send a formatted trade notification."""
        emoji = {"BUY": ":chart_with_upwards_trend:", "SELL": ":chart_with_downwards_trend:"}
        msg = (
            f"**{emoji.get(action, '')} {action}: {symbol}**\n"
            f"Qty: {quantity} @ ${price:.2f} = ${quantity * price:.2f}\n"
            f"Reasons: {', '.join(reasons)}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M ET')}"
        )
        await self.send(msg)

    async def status_update(
        self,
        portfolio_value: float,
        cash: float,
        positions: list[dict],
        pnl_pct: float,
    ) -> None:
        """Send daily portfolio status."""
        pos_lines = []
        for p in positions:
            pos_lines.append(
                f"  {p['symbol']}: {p['quantity']} shares @ ${p['avg_cost']:.2f} "
                f"(now ${p['current_price']:.2f}, {p['pnl_pct']:+.1f}%)"
            )
        pos_text = "\n".join(pos_lines) if pos_lines else "  (none)"

        msg = (
            f"**Daily Status**\n"
            f"Portfolio: ${portfolio_value:.2f} ({pnl_pct:+.1f}% total)\n"
            f"Cash: ${cash:.2f}\n"
            f"Positions:\n{pos_text}"
        )
        await self.send(msg)

    async def error_alert(self, error: str) -> None:
        """Send an error notification."""
        await self.send(f":warning: **Error:** {error}")

    async def halt_alert(self, reason: str) -> None:
        """Send a trading halt notification."""
        await self.send(f":octagonal_sign: **TRADING HALTED:** {reason}")
