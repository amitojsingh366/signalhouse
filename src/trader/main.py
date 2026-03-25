"""Entry point — starts the Discord bot with scheduled market scanning."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from trader.bot import TraderBot
from trader.config import load_config
from trader.market_data import MarketData
from trader.portfolio import Portfolio
from trader.risk import RiskManager
from trader.strategy import Strategy


def main() -> None:
    """Wire up components and start the Discord bot."""
    # Create directories first
    Path("logs").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/trader.log", mode="a"),
        ],
    )
    logger = logging.getLogger(__name__)

    config = load_config()

    # Validate required config
    bot_token = config.get("discord", {}).get("bot_token", "")
    if not bot_token:
        logger.error("DISCORD_BOT_TOKEN not set. Set it in .env or settings.local.yaml.")
        sys.exit(1)

    channel_id = config.get("discord", {}).get("channel_id", "")
    if not channel_id:
        logger.error("DISCORD_CHANNEL_ID not set. Set it in .env or settings.local.yaml.")
        sys.exit(1)

    # Initialize components
    market_data = MarketData(config)
    risk = RiskManager(config)

    portfolio = Portfolio(Path("data") / "portfolio.json")
    portfolio.load()
    portfolio.sync_risk_manager(risk)

    strategy = Strategy(market_data, risk, portfolio, config)

    logger.info(
        "Starting bot — tracking %d symbols, %d holdings loaded",
        len(strategy.symbols),
        len(portfolio.holdings),
    )

    bot = TraderBot(config, strategy, portfolio, market_data, risk)
    bot.run(bot_token, log_handler=None)  # We already configured logging


if __name__ == "__main__":
    main()
