"""Entry point — initializes database, loads config, starts the Discord bot."""

from __future__ import annotations

import asyncio
import logging
import sys

from trader_api.config import load_config
from trader_api.database import async_session, init_db
from trader_api.services.market_data import MarketData
from trader_api.services.portfolio import Portfolio
from trader_api.services.risk import RiskManager
from trader_api.services.sentiment import SentimentAnalyzer
from trader_api.services.strategy import Strategy

from trader_bot.bot import TraderBot


async def _run() -> None:
    """Initialize database, wire up components, and run the bot.

    Everything runs on a single event loop to avoid asyncpg connection
    issues (connections are bound to the loop they were created on).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logger = logging.getLogger(__name__)

    config = load_config()

    bot_token = config.get("discord", {}).get("bot_token", "")
    if not bot_token:
        logger.error("DISCORD_BOT_TOKEN not set.")
        sys.exit(1)

    channel_id = config.get("discord", {}).get("channel_id", "")
    if not channel_id:
        logger.error("DISCORD_CHANNEL_ID not set.")
        sys.exit(1)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Create components
    market_data = MarketData(config)
    risk = RiskManager(config)

    # Create initial portfolio from DB to sync risk manager
    async with async_session() as session:
        portfolio = Portfolio(session)
        holdings = await portfolio.get_holdings_dict()
        meta = await portfolio._get_meta()
        portfolio.sync_risk_manager(risk, holdings, meta.initial_capital)

    sentiment = SentimentAnalyzer(cdr_to_us=market_data.cdr_to_us)

    # Create strategy with a session (for startup only)
    async with async_session() as session:
        init_portfolio = Portfolio(session)
        strategy = Strategy(market_data, risk, init_portfolio, config, sentiment=sentiment)

    logger.info(
        "Starting bot — tracking %d symbols, %d holdings loaded",
        len(strategy.symbols),
        len(holdings),
    )

    bot = TraderBot(config, strategy, init_portfolio, market_data, risk, async_session)

    async with bot:
        await bot.start(bot_token, reconnect=True)


def main() -> None:
    """Single entry point — runs init + bot on one event loop."""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
