"""Discord bot — core TraderBot class and shared helpers."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

from trader_api.services.market_data import MarketData
from trader_api.services.portfolio import Portfolio
from trader_api.services.risk import RiskManager
from trader_api.services.strategy import Strategy
from trader_bot.cogs import EXTENSIONS

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


def is_market_hours(config: dict) -> bool:
    """Check if current time is within market hours (ET), weekday only."""
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    market_open = datetime.strptime(config["schedule"]["market_open"], "%H:%M").time()
    market_close = datetime.strptime(config["schedule"]["market_close"], "%H:%M").time()
    return market_open <= now.time() <= market_close


class TraderBot(commands.Bot):
    def __init__(
        self,
        config: dict[str, Any],
        strategy: Strategy,
        portfolio: Portfolio,
        market_data: MarketData,
        risk: RiskManager,
        db_session_factory: Any,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.strategy = strategy
        self.portfolio = portfolio
        self.market_data = market_data
        self.risk = risk
        self.db_session_factory = db_session_factory
        self.channel_id = int(config["discord"]["channel_id"])
        self.start_time = datetime.now(ET)

    async def setup_hook(self) -> None:
        for ext in EXTENSIONS:
            await self.load_extension(ext)
            logger.info("Loaded extension: %s", ext)

        guild_id = self.config["discord"].get("guild_id")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        logger.info("Bot ready as %s", self.user)
        channel = self.get_channel(self.channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(
                f"**Bot started** — tracking {len(self.strategy.symbols)} symbols. "
                f"Use `/recommend` for signals, `/holdings` to view portfolio."
            )

    async def get_fresh_portfolio(self) -> Portfolio:
        """Get a portfolio with a fresh DB session (for use in cogs)."""
        session = self.db_session_factory()
        return Portfolio(session)

    async def get_fresh_strategy(self) -> Strategy:
        """Get a strategy with a fresh DB session."""
        portfolio = await self.get_fresh_portfolio()
        return Strategy(
            market_data=self.market_data,
            risk=self.risk,
            portfolio=portfolio,
            config=self.config,
            sentiment=self.strategy.sentiment,
        )
